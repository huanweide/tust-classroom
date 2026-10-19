"""静态导出层 —— SQLite → GitHub Pages 可直接托管的 JSON

导出的东西（全部是纯静态文件，丢到任何 CDN / Pages 都能跑）：
    index.json        元数据：校区、日期、各校区教学楼、节次表、更新时间
    YYYY-MM-DD.json   当天数据，按「校区 → 教学楼 → 教室 → 节次数组」压缩
    search.json       教室名搜索索引（前端做自动补全用）

为什么要压缩成「教室 → 节次数组」：
    一天 13 节 × 每栋楼几十间教室，如果一条一节地存，文件会大 10 倍以上。
    手机上打开要省流量，所以同一间教室的空闲节次合并成一个数组。
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List

from .model import SchoolProfile
from .store import RoomStore

# M1 归一化：楼名/教室名归一化 + 楼栋分层策略。
# 这两个模块与学校无关（纯字符串与统计逻辑），故放在仓库根目录，
# 由导出层调用、前端只读产物 —— 严禁前端另写一套楼名映射表（漂移坑）。
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
import building_policy  # noqa: E402
import normalize  # noqa: E402


class StaticExporter:
    """把仓库里的数据导出成静态站所需的一堆 JSON"""

    def __init__(self, store: RoomStore, profile: SchoolProfile, out_dir: str) -> None:
        self.store = store
        self.profile = profile
        self.out_dir = out_dir

    # ── 对外主入口 ──

    def export(self, verbose: bool = True) -> Dict[str, Any]:
        """执行导出，返回统计信息"""
        os.makedirs(self.out_dir, exist_ok=True)

        # ── 安全闸门：禁止用残缺数据库覆盖线上完整数据 ──
        # 实测踩坑（2026-10-19）：本地 classrooms.db 只存了 40 天，
        # 而 static/data 里是 130 天。「删旧留新」的老逻辑会静默删掉
        # 90 天线上数据，用户直接损失一整个学期的查询能力。
        # 所以：本地天数明显少于线上时必须停下，除非显式传 force=True。
        if not self._guard_data_loss():
            raise SystemExit(2)

        self._clean_old_json()

        campuses = self._ordered_campuses()
        dates = self.store.distinct_dates()
        buildings = {c: self.store.distinct_buildings(c) for c in campuses}

        index = self._build_index(campuses, dates, buildings)
        self._write_json("index.json", index, pretty=True)
        if verbose:
            print(
                f"[index] {len(campuses)} 校区, {len(dates)} 天, "
                f"{sum(len(v) for v in buildings.values())} 栋楼"
            )

        for date_str in dates:
            self._write_json(f"{date_str}.json", self._build_day(date_str), pretty=False)
        if verbose:
            print(f"[dates] {len(dates)} 天数据已导出")

        search_index = self._build_search_index()
        self._write_json("search.json", search_index, pretty=False)
        if verbose:
            n_step = sum(1 for r in search_index if r.get("st"))
            print(f"[search] {len(search_index)} 条教室索引（阶梯 {n_step} 间）")

        stats = self._size_stats(verbose=verbose)
        stats.update({
            "campuses": len(campuses),
            "dates": len(dates),
            "rooms": len(search_index),
            "out_dir": self.out_dir,
        })
        return stats

    # ── 内部步骤 ──

    def _guard_data_loss(self) -> bool:
        """本地数据天数 < 线上已有天数时，拒绝覆盖。

        返回 True 才允许继续导出。force 参数由环境变量
        CAMPUSFREE_EXPORT_FORCE=1 显式开启（默认关）。
        """
        if os.environ.get("CAMPUSFREE_EXPORT_FORCE") == "1":
            return True
        prev_path = os.path.join(self.out_dir, "index.json")
        if not os.path.exists(prev_path):
            return True
        try:
            with open(prev_path, encoding="utf-8") as f:
                prev_days = len(json.load(f).get("dates", []))
        except (OSError, ValueError):
            return True
        db_days = len(self.store.distinct_dates())
        if prev_days and db_days < prev_days:
            print(
                f"[FATAL] 本地数据库只有 {db_days} 天数据，"
                f"但 static/data 现有 {prev_days} 天。",
                file=sys.stderr,
            )
            print("        直接导出会删掉线上已有数据，已中止。", file=sys.stderr)
            print("        确认要覆盖请设 CAMPUSFREE_EXPORT_FORCE=1，"
                  "或先补爬数据。", file=sys.stderr)
            return False
        return True

    def _clean_old_json(self) -> None:
        """删掉上一次导出的 json，只留本次的（避免过期日期文件堆积）"""
        if not os.path.isdir(self.out_dir):
            return
        for name in os.listdir(self.out_dir):
            if name.endswith(".json"):
                try:
                    os.remove(os.path.join(self.out_dir, name))
                except OSError:
                    pass

    def _ordered_campuses(self) -> List[str]:
        """校区展示顺序：适配器指定的 campus_order 优先，其余按名字排"""
        campuses = self.store.distinct_campuses()
        order = [c for c in (self.profile.campus_order or []) if c in campuses]
        rest = sorted(c for c in campuses if c not in order)
        return order + rest

    def _build_index(
        self, campuses: List[str], dates: List[str], buildings: Dict[str, List[str]]
    ) -> Dict[str, Any]:
        idx: Dict[str, Any] = {
            "campuses": campuses,
            "dates": dates,
            "buildings": buildings,
            "periods": {str(k): v for k, v in sorted(self.profile.periods.items())},
            # ⚠ 注意语义：updated = 数据覆盖到的最后一天，不是抓取时间
            "updated": max(dates) if dates else "",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        }
        # 默认校区：前端打开时先选中它
        default = self.profile.default_campus
        if not default and campuses:
            default = campuses[0]
        if default:
            idx["default_campus"] = default
        if self.profile.school_name:
            idx["school"] = self.profile.school_name
        if self.profile.source_note:
            idx["source"] = self.profile.source_note
        # M1 归一化元数据：前端不再自己猜楼名/阶梯，一律读这里算好的结果。
        idx["buildingMeta"] = self._build_building_meta(campuses, buildings)
        return idx

    def _build_building_meta(
        self, campuses: List[str], buildings: Dict[str, List[str]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """楼栋归一化 + 分层 + 排序（M1 成果，前端唯一真相源）。

        排序规则（用户明确要求，勿改）：
          1. 阶梯教室楼永远最前
          2. 其余按房间数降序 —— 信息多的楼排上面
          3. 同名按名称
        一律不折叠：「什么楼都可选再跳转」是硬要求。
        """
        counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for r in self.store.iter_distinct_rooms():
            counts[r["campus_name"]][r["building_name"]] += 1

        out: Dict[str, List[Dict[str, Any]]] = {}
        for c in campuses:
            rows = []
            for b in buildings.get(c, []):
                nb = normalize.normalize_building(b)
                pol = building_policy.classify_building(nb, counts[c][b])
                rows.append({
                    "key": b,
                    "display": pol["display"],
                    "tier": pol["tier"],
                    "sort": pol["sort"],
                    "roomCount": pol["room_count"],
                    # 单间房楼：点进去直接看教室，不需要中间列表
                    "skipList": pol["skip_list"],
                    "isStepBld": nb["is_step_bld"],
                })
            rows.sort(key=lambda x: (x["sort"], x["display"]))
            out[c] = rows
        return out

    def _build_search_index(self) -> List[Dict[str, Any]]:
        """搜索索引 + 归一化字段（前端不必再猜 16阶梯(d) 怎么显示）。"""
        rows = []
        for r in self.store.iter_distinct_rooms():
            nr = normalize.normalize_room(r["classroom_name"])
            nb = normalize.normalize_building(r["building_name"])
            rows.append({
                "c": r["campus_name"], "b": r["building_name"],
                "r": r["classroom_name"],
                "d": nr["display"], "sd": nb["display"],
                "st": 1 if nr["is_step"] else 0,
                "sn": nr["step_no"] if nr["is_step"] else 0,
            })
        return rows

    def _build_day(self, date_str: str) -> Dict[str, Any]:
        """某一天的数据：{校区: {楼: {教室: [节次]}}}"""
        compressed: Dict[str, Dict[str, Dict[str, List[int]]]] = defaultdict(
            lambda: defaultdict(dict)
        )
        for r in self.store.iter_day_rows(date_str):
            compressed[r["campus_name"]][r["building_name"]].setdefault(
                r["classroom_name"], []
            ).append(r["period"])

        # 节次排序，前端展示才不会乱序
        return {
            campus: {
                bld: {room: sorted(periods) for room, periods in rooms.items()}
                for bld, rooms in buildings.items()
            }
            for campus, buildings in compressed.items()
        }

    def _write_json(self, filename: str, payload: Any, pretty: bool) -> None:
        path = os.path.join(self.out_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            if pretty:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            else:
                json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))

    def _size_stats(self, verbose: bool = True) -> Dict[str, Any]:
        total = 0
        big: List[str] = []
        for name in sorted(os.listdir(self.out_dir)):
            size = os.path.getsize(os.path.join(self.out_dir, name))
            total += size
            if name.endswith(".json"):
                kb = size / 1024
                if verbose:
                    mark = " ⚠ 偏大" if kb > 500 else ""
                    print(f"  {name:30s} {kb:7.1f} KB{mark}")
                if kb > 500:
                    big.append(name)
        if verbose:
            print(f"\n总计: {total / 1024:.0f} KB ({total / 1024 / 1024:.1f} MB)")
        return {"total_bytes": total, "oversized_files": big}


def export_static(
    store: RoomStore, profile: SchoolProfile, out_dir: str, verbose: bool = True
) -> Dict[str, Any]:
    """一行调用的便捷函数"""
    return StaticExporter(store, profile, out_dir).export(verbose=verbose)
