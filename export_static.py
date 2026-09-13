"""SQLite → 静态 JSON 导出脚本

把 classrooms.db 导出为 GitHub Pages 可用的 JSON 文件：
  data/index.json         元数据（校区、日期、教学楼）
  data/YYYY-MM-DD.json    每日教室数据（按日期分文件）
  data/search.json        教室名搜索索引

用法: python export_static.py
"""
import json
import os
import sqlite3
import sys
from collections import defaultdict

import config

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "data")


def export():
    os.makedirs(OUT_DIR, exist_ok=True)
    # 清理旧的每日 JSON，只保留本次导出的数据（删旧留新）
    for _f in os.listdir(OUT_DIR):
        if _f.endswith(".json"):
            try:
                os.remove(os.path.join(OUT_DIR, _f))
            except OSError:
                pass
    with sqlite3.connect(config.DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        # ── 1. 元数据索引 ──
        # 泰达校区默认排第一（用户要求默认校区为泰达）
        campuses = [r[0] for r in conn.execute(
            "SELECT DISTINCT campus_name FROM free_rooms "
            "ORDER BY CASE WHEN campus_name='泰达' THEN 0 ELSE 1 END, campus_name"
        )]
        dates = [r[0] for r in conn.execute(
            "SELECT DISTINCT date FROM free_rooms ORDER BY date"
        )]
        buildings_by_campus = {}
        for c in campuses:
            buildings_by_campus[c] = [r[0] for r in conn.execute(
                "SELECT DISTINCT building_name FROM free_rooms "
                "WHERE campus_name = ? ORDER BY building_name", (c,)
            )]

        index = {
            "campuses": campuses,
            "dates": dates,
            "buildings": buildings_by_campus,
            "periods": {str(k): v for k, v in sorted(config.PERIODS.items())},
            "updated": max(dates) if dates else "",
        }
        with open(os.path.join(OUT_DIR, "index.json"), "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
        print(f"[index] {len(campuses)} 校区, {len(dates)} 天, {sum(len(v) for v in buildings_by_campus.values())} 栋楼")

        # ── 2. 按日期导出教室数据 ──
        date_count = 0
        for date_str in dates:
            rows = conn.execute("""
                SELECT campus_name, building_name, classroom_name, period
                FROM free_rooms WHERE date = ?
                ORDER BY campus_name, building_name, classroom_name, period
            """, (date_str,)).fetchall()

            # 按教学楼分组，压缩传输体积
            by_building = defaultdict(lambda: defaultdict(list))
            for r in rows:
                by_building[r["campus_name"]][r["building_name"]].append({
                    "r": r["classroom_name"],
                    "p": r["period"],
                })

            # 进一步压缩：每个教室一条记录，period 存为数组
            compressed = {}
            for campus, buildings in by_building.items():
                compressed[campus] = {}
                for bld, rooms in buildings.items():
                    # 聚合：同一教室的多个 period 合并
                    room_periods = defaultdict(list)
                    for item in rooms:
                        room_periods[item["r"]].append(item["p"])
                    compressed[campus][bld] = {
                        rn: sorted(ps) for rn, ps in room_periods.items()
                    }

            fpath = os.path.join(OUT_DIR, f"{date_str}.json")
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(compressed, f, ensure_ascii=False, separators=(",", ":"))
            date_count += 1

        print(f"[dates] {date_count} 天数据已导出")

        # ── 3. 搜索索引 ──
        search_rows = conn.execute("""
            SELECT DISTINCT campus_name, building_name, classroom_name
            FROM free_rooms ORDER BY campus_name, building_name, classroom_name
        """).fetchall()
        search_index = [
            {"c": r["campus_name"], "b": r["building_name"], "r": r["classroom_name"]}
            for r in search_rows
        ]
        with open(os.path.join(OUT_DIR, "search.json"), "w", encoding="utf-8") as f:
            json.dump(search_index, f, ensure_ascii=False, separators=(",", ":"))
        print(f"[search] {len(search_index)} 条教室索引")

    # ── 4. 文件大小统计 ──
    total_size = 0
    for fname in sorted(os.listdir(OUT_DIR)):
        size = os.path.getsize(os.path.join(OUT_DIR, fname))
        total_size += size
        if fname.endswith(".json"):
            kb = size / 1024
            marker = ""
            if kb > 500:
                marker = " ⚠ 偏大"
            print(f"  {fname:30s} {kb:7.1f} KB{marker}")

    print(f"\n总计: {total_size / 1024:.0f} KB ({total_size / 1024 / 1024:.1f} MB)")


if __name__ == "__main__":
    try:
        export()
    except Exception as e:
        print(f"[FATAL] 导出失败: {e}", file=__import__('sys').stderr)
        exit(1)
