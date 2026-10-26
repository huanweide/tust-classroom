"""名称归一化 —— 显示名与数据键的唯一真相源

背景（实测得出，勿推翻）：
- 教务系统楼名脏：泰达有 `9-`、`13号楼`、`8-`，河西有 `A`、`B`、`C`、`16-`、`阶梯`。
  同一种楼两种写法，用户口中的「9号楼」在库里叫 `9-`。
- 阶梯教室真名是 `16阶梯(d)`，用户习惯叫「9-16」= 9号楼16阶梯。
  这个映射原本不存在，是搜索老打不开的根因。
- 存在真名 `9-516`（确实是一间房），所以不能靠前缀硬猜。

本模块提供三个能力，静态站与 Flask 后端共用：
1. normalize_building —— 楼名归一化 + 友好显示名
2. parse_room_query  —— 任意写法解析成 (楼栋, 教室) 候选，带可信度
3. room_key          —— 教室唯一键（跨校区跨楼防撞）

配套 export_static.py 会把归一化结果写进 index.json，
前端只读产物，不再自己猜 —— 避免前后端两套正则再次漂移。
"""

import re

# ── 1. 楼名归一化 ────────────────────────────────────────────────
# 教务楼名 → (标准键, 显示名)
# 标准键仍用原始名，确保能命中静态 JSON 的字段（不改动数据源，只加显示层）

# 实验楼 / 场地 / 虚拟类：显示名直接沿用，但打上标签供前端分组
_VENUE_TAGS = {
    "实验室": "实验室",
    "实验室1": "实验室",
    "网络": "线上",
    "在线": "线上",
    "田径场": "场地",
    "运动场": "场地",
    "体育馆": "场地",
    "大活": "场地",
    "表演厅": "场地",
    "虚拟": "虚拟",
}

# 纯数字前缀的楼：9- / 13号楼 / 8- / 16- / 21- / 2- / 3- ...
_BLD_NUM = re.compile(r"^(\d+)\s*-?\s*(号楼)?$")


def normalize_building(raw):
    """楼名归一化。

    返回 dict:
      key     标准键（== 静态 JSON 里的 building_name，用于查数据）
      display 友好显示名（用户看到的）
      num     楼号数字（能解析出来时，否则 None）
      kind    分类：teaching 教学楼 / lab 实验室 / venue 场地 / virtual 虚拟
      tag     细分标签，用于前端折叠分组
    """
    raw = (raw or "").strip()
    num = None
    kind = "teaching"
    tag = ""

    m = _BLD_NUM.match(raw)
    if m:
        num = int(m.group(1))
        display = f"{num}号楼"
    else:
        display = raw
        # 按名称特征分类
        if "实验室" in raw or "实训" in raw:
            kind = "lab"
        elif raw in _VENUE_TAGS:
            kind = "venue"
            tag = _VENUE_TAGS[raw]
        elif "虚拟" in raw:
            kind = "virtual"
        elif "阶梯" in raw:
            kind = "teaching"
            tag = "阶梯"

    # 阶梯教室所在楼（河西的 `阶梯`、泰达的 `9-`）单独标记，供前端置顶
    is_step_bld = ("阶梯" in raw) or (raw == "9-")

    return {
        "key": raw,
        "display": display,
        "num": num,
        "kind": kind,
        "tag": tag,
        "is_step_bld": is_step_bld,
    }


# ── 2. 教室名解析 ────────────────────────────────────────────────
# 阶梯教室：1阶梯(d) ~ 17阶梯(d)
_STEP_ROOM = re.compile(r"^(\d+)\s*阶梯\s*(\(.*\))?$")
# 机房/普通房：316机房、503机、610
_PLAIN_ROOM = re.compile(r"^(\d+)(.*)$")


def normalize_room(raw):
    """教室名归一化。

    返回 dict:
      raw      原始名
      key      标准键（== 静态 JSON 里的 classroom_name）
      display  友好显示名（去 (d) 尾巴，阶梯补楼号）
      num      房号数字，阶梯取阶梯序号，普通房取数字前缀
      is_step  是否阶梯教室
      step_no  阶梯序号（1~17），非阶梯为 None
    """
    raw = (raw or "").strip()
    m = _STEP_ROOM.match(raw)
    if m:
        no = int(m.group(1))
        return {
            "raw": raw,
            "key": raw,
            "display": f"{no}阶梯",
            "num": no,
            "is_step": True,
            "step_no": no,
        }
    m = _PLAIN_ROOM.match(raw)
    num = int(m.group(1)) if m else None
    return {
        "raw": raw,
        "key": raw,
        "display": raw,
        "num": num,
        "is_step": False,
        "step_no": None,
    }


def room_key(campus, building, room):
    """教室唯一键。跨校区跨楼防撞（如两个校区都有 101）。"""
    return f"{campus}|{building}|{room}"


# ── 3. 查询词解析（搜索栏唯一入口）────────────────────────────────
# 支持写法：
#   9-16      9号楼16阶梯        916        9 16       16阶梯   16阶梯(d)   9号楼16阶梯
# 不支持（也不该支持）：拿房号去猜楼号 —— 316机房 不是 9-316阶梯

_SEP = r"[-—－_\s]*"

# 真实存在的阶梯教室序号（实测：1~8、10~17，没有 9）
_STEP_NOS = {1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 14, 15, 16, 17}


def _split_bld_room(digits):
    """把连写数字穷举成 (楼号, 阶梯号) 所有合法切法。

    `916` → [(9,16), (91,6)]；非法切法直接丢弃。
    穷举而非正则匹配的理由：正则贪婪/非贪婪都只能给出一种切法，
    而真实楼号是 1~2 位、阶梯号 1~2 位，必须全试一遍才能不漏。
    """
    out = []
    for split in range(1, len(digits)):
        bld_s, no_s = digits[:split], digits[split:]
        if not (bld_s.isdigit() and no_s.isdigit()):
            continue
        bld, no = int(bld_s), int(no_s)
        if not (1 <= bld <= 40):
            continue
        if no not in _STEP_NOS:      # 阶梯号必须是真实存在的
            continue
        out.append((bld, no))
    return out


def parse_room_query(q):
    """解析搜索词，返回按可信度排序的候选。

    返回 list[dict]，每项:
      kind    room 教室 / building 楼栋
      score   可信度（越大越靠前）
      bld     楼栋 key（kind=room 时必有）
      room    教室 key（kind=room 时必有）
      display 显示文案
    """
    q = (q or "").strip()
    if not q:
        return []

    cands = []
    raw = q
    # 全角 → 半角，统一分隔符
    norm = re.sub(r"[—－]", "-", raw)
    norm = re.sub(r"\s+", "", norm)

    # ── A. 纯数字：歧义最大的一档 ──
    # 实测：库里 1~20 区间没有任何纯数字房名（101 起都是三位），
    # 但阶梯教室真实序号是 1~17 且【9 号阶梯不存在】（有 1-8、10-17）。
    # 因此纯数字一律先当「阶梯号」候选，再给「楼号」候选兜底，前端按真实存在性裁决。
    if re.fullmatch(r"\d{1,2}", norm):
        no = int(norm)
        if no in _STEP_NOS:      # 只认真实存在的阶梯号（没有 9 阶梯）
            cands.append({
                "kind": "room",
                "score": 110 - no,
                "room": f"{no}阶梯(d)",
                "step_no": no,
                "display": f"{no}阶梯",
                "hint": "阶梯教室",
            })
        cands.append({
            "kind": "building",
            "score": 30,
            "bld_num": no,
            "display": f"{no}号楼",
            "hint": "教学楼",
        })

    # ── B. 楼栋前缀：9-16 / 9-16阶梯 / 9号楼16 / 916阶梯 ──
    # 关键：楼号后必须有分隔符（- / 号楼），否则 16阶梯 会被切成 1号楼 + 6阶梯。
    # 所以 B 只吃「明确带 - 或 号楼」的写法；纯连写的 916 交给 D 用正则反解。
    m = re.match(r"^(\d{1,2})(?:-|号楼)(\d{1,3})(阶梯.*)?$", norm)
    if m:
        bld = int(m.group(1))
        no = int(m.group(2))
        cands.append({
            "kind": "room",
            "score": 130 - no,
            "bld_num": bld,
            "room": f"{no}阶梯(d)",
            "step_no": no,
            "display": f"{bld}号楼 {no}阶梯",
            "hint": "阶梯教室",
        })

    # ── B2. 连写楼号+阶梯号：916阶梯 / 915阶梯 ──
    # 实测铁律：库里 3 位纯数字（101/316/610/908…）全是真实房号，一个都不能拆。
    # 所以连写拆词只在「用户明确写了阶梯」时才允许，避免 610 → 6号楼10阶梯。
    #
    # 切词必须【穷举所有切法】而不是正则首个匹配：
    # `^(\d{1,2})(\d{1,2})阶梯$` 遇 916阶梯 会贪婪切成 91|6，
    # 但正确答案是 9|16。枚举优先取「楼号 1 位 + 房号 2 位」这种自然切法。
    if "阶梯" in norm:
        # 2~4 位都可能是「楼号+阶梯号」连写（91阶梯=9|1，916阶梯=9|16，6116阶梯）
        m = re.fullmatch(r"(\d{2,4})阶梯", norm)
        if m:
            digits = m.group(1)
            # 穷举全部合法切法后【全部保留】，不强行选一个。
            # 91阶梯 天然歧义（9|1 和 91|1 都成立），让前端列出来由用户点，
            # 比替用户猜一个更诚实。
            for bld, no in _split_bld_room(digits):
                cands.append({
                    "kind": "room",
                    "score": 122 - no,
                    "bld_num": bld,
                    "room": f"{no}阶梯(d)",
                    "step_no": no,
                    "display": f"{bld}号楼 {no}阶梯",
                    "hint": "阶梯教室",
                })
    elif re.fullmatch(r"\d{3,4}", norm):
        # 纯连写数字：只保留「真实存在该房号」这一条路（由前端用 search.json 校验），
        # 不再猜楼号 —— 猜错比不猜更糟。
        cands.append({
            "kind": "room_exact",
            "score": 60,
            "room": norm,
            "display": norm,
            "hint": "按房号精确匹配",
        })

    # ── C. 只给楼号 + 号楼：9号楼 ──
    m = re.fullmatch(r"(\d{1,2})号楼", norm)
    if m:
        bld = int(m.group(1))
        cands.append({
            "kind": "building",
            "score": 80,
            "bld_num": bld,
            "display": f"{bld}号楼",
            "hint": "教学楼",
        })

    # ── D. 教学楼关键字：9- / 阶梯 / 逸夫 ──
    # 注意：楼栋候选分数必须低于「具体教室」候选（E 段 98/82、C 段 80），
    # 否则搜「16阶梯」时“阶梯教学楼”会挤掉真正的 16 阶梯教室。
    if norm in ("9-", "9号楼"):
        cands.append({"kind": "building", "score": 95, "bld_key": "9-",
                      "display": "9号楼", "hint": "阶梯教室所在楼"})
    elif "阶梯" in norm or "阶" in norm:
            # 「9阶梯」「916阶梯」这类库里不存在的名字，不要退化成楼栋
            # —— 用户明确写了阶梯却看到一栋楼，比搜不到更困惑。
            if re.fullmatch(r"\d{1,4}阶梯(\(.*\))?", norm):
                pass  # E/B2 段已精确处理；解析不出真实教室就是真不存在
            else:
                cands.append({"kind": "building", "score": 70, "bld_key": "阶梯",
                              "display": "阶梯教室楼", "hint": "教学楼"})
    else:
        # 纯数字已在 A 段处理；这里只兜底「带文字的楼名」（逸夫楼、大活、9-16…）
        if not re.fullmatch(r"\d{1,2}", norm):
            cands.append({"kind": "building", "score": 40, "bld_key": norm,
                          "display": norm, "hint": "教学楼"})

    # ── E. 显式阶梯名：16阶梯 / 16阶梯(d) ──
    # 最高优先级：用户明确写了「阶梯」，就该直达教室，而不是先给一栋楼。
    m = _STEP_ROOM.match(norm)
    if m:
        no = int(m.group(1))
        cands.append({
            "kind": "room",
            "score": 200 - no,
            "room": f"{no}阶梯(d)",
            "step_no": no,
            "display": f"{no}阶梯",
            "hint": "阶梯教室",
        })

    # ── F. 精确真名兜底（分数封顶，永远排第一）──
    # 实测踩坑：`316机房` 被当成楼名丢掉，但它在库里真实存在（泰达9-）。
    # 任何输入都先拿原始串跟真实名做相等匹配，命中即封顶。
    for probe in {raw.strip(), norm}:
        cands.append({
            "kind": "room_exact",
            "score": 999,
            "room": probe,
            "display": probe,
            "hint": "精确匹配",
        })
        cands.append({
            "kind": "bld_exact",
            "score": 998,
            "bld_key": probe,
            "display": probe,
            "hint": "教学楼",
        })

    # 去重：同 kind + 同目标只留最高分
    best = {}
    for c in cands:
        k = (c["kind"], c.get("bld_key"), c.get("bld_num"), c.get("room"))
        if k not in best or c["score"] > best[k]["score"]:
            best[k] = c

    out = sorted(best.values(), key=lambda x: -x["score"])
    return out


# ── 4. 结合真实索引裁决 ───────────────────────────────────────────
# 上面的解析只产生「意图」，最终哪个意图成立必须由真实数据说话。
# 铁律：宁可返回空，也不能返回一个库里不存在的教室 —— 编造比搜不到更伤信任。


def resolve(q, search_index, campus=None):
    """把搜索词解析 + 真实索引校验，产出最终可点击的结果列表。

    search_index: export_static 导出的 search.json 结构
                  [{"c": 校区, "b": 楼栋, "r": 教室}, ...]
    campus: 当前校区（None = 不限，但结果仍按当前校区优先）

    返回 list[dict]:
      type      room / building
      campus/building/room  真实键（用于查每日数据）
      display   显示文案
      sub       副标题（位置信息）
      score     可信度
    """
    cands = parse_room_query(q)
    if not cands or not search_index:
        return []

    by_room = {}    # (campus, room) -> [bld, ...]
    by_bld = {}     # (campus, bld) -> {room, ...}
    for r in search_index:
        c = r.get("c") if "c" in r else r.get("campus_name")
        b = r.get("b") if "b" in r else r.get("building_name")
        rn = r.get("r") if "r" in r else r.get("classroom_name")
        by_bld.setdefault((c, b), set()).add(rn)
        by_room.setdefault((c, rn), []).append(b)

    results = []
    for c in cands:
        kind = c["kind"]

        if kind in ("room", "room_exact") and c.get("room"):
            rn = c["room"]
            hits = []
            for (cc, rn2), bl in by_room.items():
                if rn2 == rn:
                    hits.extend((cc, bb) for bb in bl)
            # 带楼号的候选要校验楼号真实存在（91阶梯 应丢弃 91 楼、只留 9 楼）
            if c.get("bld_num") is not None:
                n = c["bld_num"]
                hits = [h for h in hits
                        if normalize_building(h[1])["num"] == n]
            if campus:
                pref = [h for h in hits if h[0] == campus]
                hits = pref + [h for h in hits if h[0] != campus]
            cap = 3 if kind == "room" else 6
            for cc, bb in hits[:cap]:
                results.append({
                    "type": "room",
                    "campus": cc,
                    "building": bb,
                    "room": rn,
                    "display": c["display"],
                    "sub": f"{_bld_display(bb)} · {cc}",
                    "score": c["score"],
                })

        elif kind in ("building", "bld_exact"):
            bk = c.get("bld_key")
            hits = [k for k in by_bld if k[1] == bk] if bk else []
            if not hits and c.get("bld_num") is not None:
                n = c["bld_num"]
                hits = [k for k in by_bld
                        if normalize_building(k[1])["num"] == n]
            if campus:
                pref = [h for h in hits if h[0] == campus]
                hits = pref + [h for h in hits if h[0] != campus]
            for cc, bb in hits[:4]:
                nb = normalize_building(bb)
                results.append({
                    "type": "building",
                    "campus": cc,
                    "building": bb,
                    "display": nb["display"],
                    "sub": f"{cc} · {c.get('hint', '')}".strip(" ·"),
                    "room_count": len(by_bld.get((cc, bb), ())),
                    "is_step_bld": nb["is_step_bld"],
                    "kind_tag": nb["kind"],
                    "score": c["score"],
                })

    # 去重
    seen, out = set(), []
    for r in results:
        k = (r["type"], r["campus"], r["building"], r.get("room"))
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out[:8]


def _bld_display(raw):
    return normalize_building(raw)["display"]


if __name__ == "__main__":
    # 冒烟测试
    tests = ["9-16", "16阶梯", "16阶梯(d)", "9号楼16阶梯", "916", "9-", "9", "阶梯", "316机房"]
    for t in tests:
        print(f"{t:14s} →", [(c["kind"], c["display"], c["score"]) for c in parse_room_query(t)])
