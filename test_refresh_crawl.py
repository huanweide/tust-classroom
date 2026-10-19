"""refresh_crawl.py 自校验能力的测试（不动真实数据）

场景：爬虫"成功"返回但实际插入 0 行（登录态失效的典型表现）。
期望：verify_after_crawl 必须报警，退出码非 0，并提示别直接导出。
"""
import os
import shutil
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
import refresh_crawl as rc

PASS = FAIL = 0
def chk(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1; print(f"  PASS  {name}")
    else:
        FAIL += 1; print(f"  FAIL  {name}" + (f"\n         {extra}" if extra else ""))

# 用临时 DB，绝不碰真实数据
tmp = tempfile.mkdtemp()
db = os.path.join(tmp, "test.db")
orig = config.DB_PATH
config.DB_PATH = db
try:
    with sqlite3.connect(db) as c:
        c.execute("""CREATE TABLE free_rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campus_name TEXT NOT NULL, building_name TEXT NOT NULL,
            classroom_name TEXT NOT NULL, period INTEGER NOT NULL,
            date TEXT NOT NULL, scraped_at TEXT NOT NULL,
            UNIQUE(campus_name, building_name, classroom_name, period, date))""")
        # 造 60 行假数据，模拟"健康"的一天
        c.executemany(
            "INSERT INTO free_rooms (campus_name,building_name,classroom_name,"
            "period,date,scraped_at) VALUES (?,?,?,?,?,?)",
            [("泰达", "9-", f"{i}阶梯(d)", i % 13 + 1, "2026-10-20", "now")
             for i in range(60)])

    print("[1] 健康数据不应报警")
    chk("60 行 → 无问题", rc.verify_after_crawl(["2026-10-20"]) == [])

    print("[2] 空日期必须报警")
    chk("0 行 → 报出问题",
        len(rc.verify_after_crawl(["2026-10-21"])) == 1)

    print("[3] 低于阈值必须报警")
    with sqlite3.connect(db) as c:
        c.execute("DELETE FROM free_rooms WHERE date='2026-10-20' AND id > 10")
    probs = rc.verify_after_crawl(["2026-10-20"])
    chk("10 行 < 50 阈值 → 报警", len(probs) == 1, str(probs))

    print("[4] 只读体检不能写库")
    st = rc.inspect_db(verbose=False)
    chk("体检返回行数正确", st["rows"] == 10, str(st))
    chk("体检后行数未被改", st["rows"] == 10)

    print("[5] 覆盖清理只删指定日期")
    rc.clear_dates(["2026-10-20"])
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as c:
        left = c.execute("SELECT COUNT(*) FROM free_rooms").fetchone()[0]
    chk("清理后剩 0 行", left == 0, str(left))

    print("[6] 日期计划正确")
    plan = rc.build_date_plan(7, 0, 0)
    chk("默认爬 7 天", len(plan["crawl"]) == 7, str(plan["crawl"]))
    chk("不含过去日期", all(d.strftime("%Y-%m-%d") >= plan["today"]
                          for d in plan["crawl"]))
    plan2 = rc.build_date_plan(1, 3, 0)
    chk("--repast 3 会含过去 3 天", len(plan2["crawl"]) == 4, str(plan2["crawl"]))
    plan3 = rc.build_date_plan(1, 0, 180)
    chk("--prune-days 180 生成清理截止日", plan3["prune"] != "")

    print(f"\n结果：{PASS} 通过 / {FAIL} 失败")
finally:
    config.DB_PATH = orig
    shutil.rmtree(tmp, ignore_errors=True)
sys.exit(1 if FAIL else 0)