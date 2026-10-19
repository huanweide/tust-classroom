"""整体校验：前后端配合全链路核对

跑法：python verify_all.py
覆盖：① 数据层 35 项 ② 导出契约 ③ 前后端字段对齐 ④ E2E 47 项（调 node）
铁律：任何一项 FAIL 都不算交付完成。
"""
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
NODE = "C:/Users/Administrator/.workbuddy/binaries/node/versions/22.22.2-6/node.exe"

PASS = FAIL = 0
def chk(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}" + (f"\n         {extra}" if extra else ""))


def main():
    print("=" * 66)
    print("tust-classroom 整体校验 · 前后端配合全链路")
    print("=" * 66)

    # ── ① 数据层回归 ──
    print("\n[①] 数据层归一化回归（35 项）")
    r = subprocess.run([PY, os.path.join(ROOT, "test_normalize.py")],
                       capture_output=True, text=True, encoding="utf-8")
    m = re.search(r"结果：(\d+) 通过 / (\d+) 失败", r.stdout)
    chk("test_normalize.py 全绿", m and int(m.group(2)) == 0,
        (r.stdout + r.stderr)[-400:] if not m else "")

    # ── ② 导出契约：静态 JSON 字段是否齐备 ──
    print("\n[②] 导出契约（前端依赖的字段必须存在）")
    idx_p = os.path.join(ROOT, "static", "data", "index.json")
    srch_p = os.path.join(ROOT, "static", "data", "search.json")
    chk("index.json 存在", os.path.exists(idx_p))
    chk("search.json 存在", os.path.exists(srch_p))
    if not (os.path.exists(idx_p) and os.path.exists(srch_p)):
        return 1

    idx = json.load(open(idx_p, encoding="utf-8"))
    srch = json.load(open(srch_p, encoding="utf-8"))

    for f in ["campuses", "dates", "buildings", "periods", "buildingMeta"]:
        chk(f"index.json 有 {f}", f in idx)
    chk("默认校区泰达在首位", idx["campuses"][:1] == ["泰达"], str(idx["campuses"]))
    chk("buildingMeta 覆盖所有校区",
        set(idx["buildingMeta"].keys()) == set(idx["campuses"]))

    # buildingMeta 每栋楼必须有前端用到的字段（与 export_static.build_meta 对齐）
    need = {"key", "display", "tier", "sort", "roomCount", "skipList", "isStepBld"}
    bad = [b["key"] for rows in idx["buildingMeta"].values() for b in rows
           if not need.issubset(b.keys())]
    chk("buildingMeta 字段完整", not bad, str(bad[:5]))
    # 反向：不能有多余字段（死字段会误导后来人）
    extra = [b["key"] for rows in idx["buildingMeta"].values() for b in rows
             if set(b.keys()) - need]
    chk("buildingMeta 无死字段", not extra, str(extra[:5]))

    # search.json 归一化字段
    bad = [r for r in srch if not {"c", "b", "r", "d", "sd", "st", "sn"}.issubset(r.keys())]
    chk("search.json 归一化字段完整", not bad, str(bad[:2]))

    # 阶梯标记自洽
    step_by_name = {r["r"] for r in srch if "阶梯" in r["r"]}
    step_by_flag = {r["r"] for r in srch if r["st"] == 1}
    chk("阶梯标记与名称自洽", step_by_name == step_by_flag,
        f"name={len(step_by_name)} flag={len(step_by_flag)}")

    # 楼栋显示名不能是数据键的裸拷贝（证明归一化真在干活）
    same = [b["key"] for rows in idx["buildingMeta"].values() for b in rows
            if b["key"] == b["display"] and re.match(r"^\d+-$", b["key"])]
    chk("数字楼已归一化显示名（9- → 9号楼）", not same, str(same))

    # 每日 JSON 与索引一致
    print("\n[③] 每日数据与索引一致性")
    missing = [d for d in idx["dates"]
               if not os.path.exists(os.path.join(ROOT, "static", "data", f"{d}.json"))]
    chk("每个索引日期都有对应 JSON", not missing, str(missing[:5]))
    chk("数据天数 >= 130（线上学期数据未丢）", len(idx["dates"]) >= 130,
        f"实际 {len(idx['dates'])} 天")

    # 抽样一份每日 JSON 验证结构
    if idx["dates"]:
        d = idx["dates"][-1]
        day = json.load(open(os.path.join(ROOT, "static", "data", f"{d}.json"),
                             encoding="utf-8"))
        chk(f"{d} 数据结构为 校区→楼→教室→节次数组",
            isinstance(day, dict) and all(isinstance(v, dict) for v in day.values()))
        # 教室必须能在 search 索引里找到（前后端键一致）
        keys = {(c, b) for c, bs in day.items() for b in bs}
        idx_keys = {(r["c"], r["b"]) for r in srch}
        orphan = keys - idx_keys
        chk("每日数据楼栋均在搜索索引中", not orphan, str(list(orphan)[:5]))

    # ── ④ 前端 HTML 与后端字段对齐 ──
    print("\n[④] 前后端字段对齐（前端读的字段后端必须产出）")
    html = open(os.path.join(ROOT, "static", "index.html"), encoding="utf-8").read()
    for f in ["buildingMeta", "roomCount", "isStepBld", "skipList",
              "tier", "sel-campus", "inp-global", "panel-browse"]:
        chk(f"前端引用 {f}", f in html)

    # 反向校验：后端产出但前端不用的字段 = 死字段，必须清掉（避免误导后来人）
    for f in ["stepRooms", "collapsible"]:
        chk(f"无死字段 {f}（后端不产出前端用不到的东西）", f not in html and f not in idx)

    # 深链参数前后端一致（注意前端用单引号，断言别写死引号风格）
    for p in ["campus", "bld", "room", "date"]:
        chk(f"深链参数 {p} 前端已消费",
            re.search(rf"\.get\(['\"]{p}['\"]\)", html) is not None)

    # ── ⑤ E2E（真浏览器）──
    print("\n[⑤] 端到端测试（Playwright 真浏览器）")
    e2e = os.path.join(ROOT, "test_e2e_browse.mjs")
    if not os.path.exists(e2e):
        chk("E2E 脚本存在", False)
    else:
        r = subprocess.run([NODE, e2e], capture_output=True, text=True,
                           encoding="utf-8", cwd=ROOT)
        m = re.search(r"结果：(\d+) 通过 / (\d+) 失败", r.stdout)
        chk("test_e2e_browse.mjs 全绿", m and int(m.group(2)) == 0,
            (r.stdout + r.stderr)[-600:] if not m else f"{m.group(1)} 项")

    # ── ⑥ 安全闸门 ──
    print("\n[⑥] 导出安全闸门")
    # 架构说明：导出逻辑已迁到 campusfree/exporter.py，
    # export_static.py 只是兼容薄壳，闸门必须在 exporter 里才拦得住。
    exp = open(os.path.join(ROOT, "campusfree", "exporter.py"),
               encoding="utf-8").read()
    chk("有天数变少中止保护", "_guard_data_loss" in exp and "FATAL" in exp)
    chk("有强制覆盖开关（CAMPUSFREE_EXPORT_FORCE）",
        "CAMPUSFREE_EXPORT_FORCE" in exp)
    chk("归一化元数据由导出层产出（buildingMeta）",
        "_build_building_meta" in exp and "buildingMeta" in exp)
    chk("元数据逻辑单一来源（不重复实现）",
        exp.count("def _build_building_meta") == 1)
    chk("meta_only.py 存在（本地数据不全时只补元数据）",
        os.path.exists(os.path.join(ROOT, "meta_only.py")))
    r = subprocess.run([PY, os.path.join(ROOT, "meta_only.py"), "--dry-run"],
                       capture_output=True, text=True, encoding="utf-8")
    chk("meta_only dry-run 可运行且不写盘",
        r.returncode == 0 and "dry-run" in r.stdout, (r.stdout + r.stderr)[-300:])
    r = subprocess.run([PY, "-m", "campusfree", "export", "--school", "tust"],
                       capture_output=True, text=True, encoding="utf-8", cwd=ROOT)
    chk("裸跑导出会被闸门拦下（本地库 40 天 < 线上 130 天）",
        r.returncode != 0 and "FATAL" in (r.stdout + r.stderr),
        f"rc={r.returncode}")

    # ── ⑧ 爬取运维脚本 ──
    print("\n[⑧] 爬取运维脚本（覆盖旧数据 / 只读模式）")
    rc = open(os.path.join(ROOT, "refresh_crawl.py"), encoding="utf-8").read()
    chk("refresh_crawl.py 存在", os.path.exists(os.path.join(ROOT, "refresh_crawl.py")))
    chk("覆盖策略：先 DELETE 后插入",
        "DELETE FROM free_rooms WHERE date = ?" in rc)
    chk("有 dry-run 只读模式", "--dry-run" in rc and "只读" in rc)
    chk("体检用只读连接（mode=ro）", "mode=ro" in rc)
    chk("爬完有自校验（防止静默数据丢失）", "verify_after_crawl" in rc)
    chk("默认不清理历史数据（保护线上资产）", "prune_days" in rc)
    r = subprocess.run([PY, os.path.join(ROOT, "refresh_crawl.py"), "--dry-run"],
                       capture_output=True, text=True, encoding="utf-8")
    chk("dry-run 可运行且不写库", r.returncode == 0 and "dry-run" in r.stdout,
        (r.stdout + r.stderr)[-300:])
    r = subprocess.run([PY, os.path.join(ROOT, "test_refresh_crawl.py")],
                       capture_output=True, text=True, encoding="utf-8")
    m = re.search(r"结果：(\d+) 通过 / (\d+) 失败", r.stdout)
    chk("test_refresh_crawl.py 全绿", m and int(m.group(2)) == 0,
        (r.stdout + r.stderr)[-400:] if not m else f"{m.group(1)} 项")

    # ── ⑩ 推送辅助脚本 ──
    print("\n[⑩] 推送辅助（DNS 不通时的通道）")
    ur = open(os.path.join(ROOT, "update_ref.py"), encoding="utf-8").read()
    chk("update_ref.py 存在", os.path.exists(os.path.join(ROOT, "update_ref.py")))
    chk("只从环境变量读 token", "GH_TOKEN" in ur and "ghp_" not in ur)
    chk("默认 dry-run（不显式 --commit 不动）", '"--commit" not in sys.argv' in ur)
    chk("有非快进保护（父提交校验）",
        "不是纯快进" in ur and "HEAD^" in ur)
    chk("push.bat 为 CRLF 行尾（cmd.exe 不执行 LF-only）",
        open(os.path.join(ROOT, "push.bat"), "rb").read().count(b"\r\n") > 10)

    # ── ⑨ 凭据扫描 ──
    print("\n[⑨] 凭据扫描")
    r = subprocess.run(["git", "diff", "--cached", "--name-only"],
                       capture_output=True, text=True, cwd=ROOT)
    staged = [f for f in r.stdout.split() if f]
    hit = []
    for f in staged:
        p = os.path.join(ROOT, f)
        if not os.path.exists(p) or os.path.isdir(p):
            continue
        try:
            t = open(p, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        if re.search(r"(TUST_PWD\s*=\s*['\"]\w|TUST_SID\s*=\s*['\"]\d|"
                     r"BEGIN [A-Z ]*PRIVATE KEY)", t):
            hit.append(f)
    chk("暂存区无硬编码凭据", not hit, str(hit))

    print("\n" + "=" * 66)
    print(f"总结果：{PASS} 通过 / {FAIL} 失败")
    print("=" * 66)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())