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
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List

from .model import SchoolProfile
from .store import RoomStore


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

        search_index = [
            {"c": r["campus_name"], "b": r["building_name"], "r": r["classroom_name"]}
            for r in self.store.iter_distinct_rooms()
        ]
        self._write_json("search.json", search_index, pretty=False)
        if verbose:
            print(f"[search] {len(search_index)} 条教室索引")

        stats = self._size_stats(verbose=verbose)
        stats.update({
            "campuses": len(campuses),
            "dates": len(dates),
            "rooms": len(search_index),
            "out_dir": self.out_dir,
        })
        return stats

    # ── 内部步骤 ──

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
        return idx

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
