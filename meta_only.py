"""只重建元数据（不碰每日 JSON）—— 本地数据不全时的安全导出

场景：本地 classrooms.db 只有 40 天，但 static/data 有 130 天线上数据。
直接跑 campusfree export 会被安全闸门拦下（这是对的）。
但改了归一化逻辑时，我们只想更新 index.json 的 buildingMeta 和
search.json 的归一化字段，不想动 130 个每日文件。

本脚本做且只做这些：
  1. 读现有 index.json 的 dates / campuses / buildings（保持线上数据不动）
  2. 用当前 normalize / building_policy 重算 buildingMeta
  3. 重算 search.json 的归一化字段（d/sd/st/sn）
  4. 清理历史死字段（stepRooms 等）

绝不：删每日 JSON、改 dates、请求教务系统、写数据库。

用法：
    python meta_only.py            # 重建元数据
    python meta_only.py --dry-run  # 只预览不写盘
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import building_policy  # noqa: E402
import normalize  # noqa: E402

DATA_DIR = os.path.join(HERE, "static", "data")
INDEX = os.path.join(DATA_DIR, "index.json")
SEARCH = os.path.join(DATA_DIR, "search.json")

# M2 试产物，前端从未使用，必须清掉
DEAD_FIELDS = ("stepRooms", "collapsible")


def build_building_meta(index):
    """按当前排序规则重算 buildingMeta。

    房间数从现有 search.json 统计（那是线上真实数据），
    不依赖本地残缺 DB —— 这正是本脚本存在的意义。
    """
    rooms = {}
    if os.path.exists(SEARCH):
        for r in json.load(open(SEARCH, encoding="utf-8")):
            rooms.setdefault((r["c"], r["b"]), set()).add(r["r"])

    out = {}
    for campus, blds in index.get("buildings", {}).items():
        rows = []
        for b in blds:
            nb = normalize.normalize_building(b)
            pol = building_policy.classify_building(nb, len(rooms.get((campus, b), ())))
            rows.append({
                "key": b,
                "display": pol["display"],
                "tier": pol["tier"],
                "sort": pol["sort"],
                "roomCount": pol["room_count"],
                "skipList": pol["skip_list"],
                "isStepBld": nb["is_step_bld"],
            })
        rows.sort(key=lambda x: (x["sort"], x["display"]))
        out[campus] = rows
    return out


def build_search_index(index):
    """重算 search.json，补归一化字段。"""
    if not os.path.exists(SEARCH):
        return None
    rows = []
    for r in json.load(open(SEARCH, encoding="utf-8")):
        nr = normalize.normalize_room(r["r"])
        nb = normalize.normalize_building(r["b"])
        rows.append({
            "c": r["c"], "b": r["b"], "r": r["r"],
            "d": nr["display"], "sd": nb["display"],
            "st": 1 if nr["is_step"] else 0,
            "sn": nr["step_no"] if nr["is_step"] else 0,
        })
    return rows


def main():
    dry = "--dry-run" in sys.argv
    if not os.path.exists(INDEX):
        print(f"[错误] 找不到 {INDEX}")
        return 1
    if not os.path.exists(SEARCH):
        print(f"[错误] 找不到 {SEARCH}")
        return 1

    index = json.load(open(INDEX, encoding="utf-8"))

    meta = build_building_meta(index)
    sidx = build_search_index(index)

    n_step = sum(1 for rows in meta.values() for r in rows if r["tier"] == "step")
    n_main = sum(1 for rows in meta.values() for r in rows if r["tier"] == "main")
    n_all = sum(len(v) for v in meta.values())
    n_step_rooms = sum(1 for r in (sidx or []) if r["st"])

    print(f"[meta] {len(index.get('campuses', []))} 校区 · {n_all} 栋楼"
          f"（阶梯楼 {n_step} · 教学楼 {n_main}）")
    print(f"[meta] 搜索索引 {len(sidx or [])} 条（阶梯教室 {n_step_rooms} 间）")
    print(f"[meta] 每日数据 {len(index.get('dates', []))} 天，保持不动")

    for campus in index.get("campuses", []):
        top = meta.get(campus, [])[:3]
        print(f"  {campus} 前 3："
              + " → ".join(f"{m['display']}({m['roomCount']}间)" for m in top))

    if dry:
        print("\n[dry-run] 未写盘。")
        return 0

    # 只改这两个字段 + 清死字段，dates 等一概不碰
    for f in DEAD_FIELDS:
        index.pop(f, None)
    index["buildingMeta"] = meta
    with open(INDEX, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    with open(SEARCH, "w", encoding="utf-8") as f:
        json.dump(sidx, f, ensure_ascii=False, separators=(",", ":"))

    print("\n已写盘：index.json（buildingMeta）+ search.json（归一化字段）")
    print("每日 JSON 未被触碰。")
    return 0


if __name__ == "__main__":
    sys.exit(main())