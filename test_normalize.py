"""normalize.py 回归测试 —— 每次改解析逻辑必跑

跑法：python test_normalize.py
铁律：这些用例全部来自对真实 470 条索引的实测，改代码后不允许改动本文件的期望值；
      期望值要改必须先解释「为什么库里变了」。
"""
import json
import os
import sys

import normalize as N

HERE = os.path.dirname(os.path.abspath(__file__))
IDX = os.path.join(HERE, "static", "data", "search.json")

PASS, FAIL = 0, 0


def check(name, got, want):
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}\n          got  {got}\n          want {want}")


def rooms_of(res):
    return tuple(sorted((x["building"], x.get("room")) for x in res
                        if x["type"] == "room"))


def bld_of(res):
    return tuple(sorted((x["campus"], x["building"]) for x in res
                        if x["type"] == "building"))


def main():
    if not os.path.exists(IDX):
        print("找不到 search.json，先跑 export_static.py")
        return 1
    sidx = json.load(open(IDX, encoding="utf-8"))

    # ── 1. 核心：多种写法必须命中同一个教室 ──
    print("[1] 写法等价性（用户核心诉求：9-16 就是 16阶梯）")
    for bld, no in [(9, 16), (9, 15), (9, 1), (9, 17), (9, 8)]:
        forms = [f"{bld}-{no}", f"{no}阶梯", f"{no}阶梯(d)",
                 f"{bld}号楼{no}阶梯", f"{bld}{no}阶梯"]
        want = ((("9-", f"{no}阶梯(d)"),) if bld == 9 else None)
        if want is None:
            continue
        got = {rooms_of(N.resolve(f, sidx, "泰达")) for f in forms}
        check(f"{' / '.join(forms)} 全部等价", len(got), 1)
        check(f"  {bld}-{no} 命中真实键", list(got)[0], want)

    # ── 2. 库里不存在的名字必须拒绝，绝不编造 ──
    print("[2] 拒绝编造")
    for q in ["9阶梯", "20阶梯", "6116阶梯", "99阶梯", "不存在的教室xyz", ""]:
        check(f"「{q}」不产生结果", len(N.resolve(q, sidx, "泰达")), 0)

    # ── 3. 楼栋写法归一化（显示名 ≠ 数据键 是最大地雷）──
    print("[3] 楼栋显示名归一化")
    check("9- → 显示 9号楼", N.normalize_building("9-")["display"], "9号楼")
    check("13号楼 → 楼号 13", N.normalize_building("13号楼")["num"], 13)
    check("9- 标记为阶梯楼", N.normalize_building("9-")["is_step_bld"], True)
    check("阶梯(河西) 标记为阶梯楼",
          N.normalize_building("阶梯")["is_step_bld"], True)
    check("逸夫楼 非阶梯楼",
          N.normalize_building("逸夫楼")["is_step_bld"], False)
    check("resolve 9- → 真实键",
          bld_of(N.resolve("9-", sidx, "泰达")), (("泰达", "9-"),))
    check("resolve 9号楼 → 同 9-", bld_of(N.resolve("9号楼", sidx, "泰达")),
          (("泰达", "9-"),))
    check("resolve 9 → 同 9-", bld_of(N.resolve("9", sidx, "泰达")),
          (("泰达", "9-"),))

    # ── 4. 真实存在的奇形教室名不能被误当楼名丢掉 ──
    print("[4] 特殊真名保留")
    check("316机房 命中 9-",
          rooms_of(N.resolve("316机房", sidx, "泰达")),
          (("9-", "316机房"),))
    check("610 命中 13号楼（不被误拆成阶梯）",
          rooms_of(N.resolve("610", sidx, "泰达")),
          (("13号楼", "610"),))

    # ── 5. 楼栋结果必须带房间数（前端要靠它决定是否折叠）──
    print("[5] 楼栋元信息")
    r = N.resolve("9-", sidx, "泰达")[0]
    # 房间数必须等于「该楼在索引里真实出现的教室数」，不能写死 ——
    # 写死会在换数据源（本地 DB 40 天 vs 线上 130 天）时误报。
    real_rooms = len({x["r"] for x in sidx if x["c"] == "泰达" and x["b"] == "9-"})
    check("9号楼 房间数与索引一致", r["room_count"], real_rooms)
    check("9号楼 带阶梯标记", r["is_step_bld"], True)
    # 阶梯教室台账完整性：索引里标 st=1 的数量应与含「阶梯」字样的一致
    step_idx = {x["r"] for x in sidx if "阶梯" in x["r"]}
    step_flag = {x["r"] for x in sidx if x.get("st") == 1}
    check("阶梯标记无遗漏", step_flag, step_idx)

    # ── 6. 校区分流：泰达/河西 同名楼不能串 ──
    print("[6] 校区隔离")
    # 泰达校区没有名为「阶梯」的楼 → 在泰达上下文搜「阶梯」必须退回河西那条，
    # 而不是把河西楼伪装成泰达楼。
    r_td = N.resolve("阶梯", sidx, "泰达")
    check("泰达搜阶梯 → 退回河西真实楼",
          bld_of(r_td), (("河西", "阶梯"),))
    # 泰达真实的阶梯楼叫 9- ，河西的叫 阶梯，两者不能互相污染
    check("泰达阶梯楼 = 9-",
          bld_of(N.resolve("9-", sidx, "泰达")), (("泰达", "9-"),))
    check("河西阶梯楼 = 阶梯",
          bld_of(N.resolve("阶梯", sidx, "河西")), (("河西", "阶梯"),))
    # 同名教室跨楼：101 在河西 12- 与 18- 都有，必须都列出来让用户选，
    # 不能只给一个（这正是旧逻辑「搜不准」的根源之一）。
    got101 = rooms_of(N.resolve("101", sidx, None))
    check("101 列出全部所在楼（河西 12- / 18-）", got101,
          (("12-", "101"), ("18-", "101")))
    check("限定泰达时，泰达无 101 应退回河西而非空",
          {x["campus"] for x in N.resolve("101", sidx, "泰达")},
          {"河西"})
    check("泰达真实存在的 316 限定后落泰达",
          {x["campus"] for x in N.resolve("316", sidx, "泰达")},
          {"泰达"})

    print(f"\n结果：{PASS} 通过 / {FAIL} 失败")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
