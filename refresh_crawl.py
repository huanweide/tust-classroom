"""固定刷新爬取 —— 确保拿到最新数据、覆盖旧数据、只读模式安全

## 背景：为什么需要这个脚本（2026-10-19 实测）

原 crawler_playwright.py 的写入策略是 `INSERT OR IGNORE`，配合
`clear_today_cache()` 只删「当天」。带来两个真实问题：

1. **重复爬同一天不会更新数据** —— UNIQUE 约束命中后 IGNORE 直接跳过，
   旧值永久留着。教务系统调整了课表你也看不出来。
2. **`DELETE FROM free_rooms WHERE date < ?`** 会按爬取日删历史，
   本地库于是越爬越短（实测本地只剩 40 天，线上有 130 天）。

所以「覆盖旧数据」不是加个参数就行，得先想清楚**哪些该覆盖、哪些不该**。

## 覆盖策略（本脚本的核心决策）

| 场景 | 动作 | 理由 |
|---|---|---|
| 重爬同一天 | 先 DELETE 该日期全部行，再插入新值 | 教务可能改过课表，必须以最新为准 |
| 今天/未来日期 | 每次刷新都重爬 | 空闲教室是当天状态，旧的没意义 |
| 已过去的日期 | 默认跳过，`--repast` 才重爬 | 历史数据不变，重爬纯浪费且可能引入噪声 |
| 早于今天的旧数据 | 默认保留，`--prune-days N` 才清理 | 线上 130 天数据是资产，不能因本地爬取而缩短 |

## 三种模式

  refresh（默认）  重爬「今天起未来 N 天」，覆盖旧值
  repast           额外重爬过去 N 天（用于修正历史数据）
  dry-run（只读）  只统计与体检，不写库、不请求教务系统

## 用法

    python refresh_crawl.py                    # 刷新今天起 7 天
    python refresh_crawl.py --days 3           # 只刷今天起 3 天
    python refresh_crawl.py --repast 7         # 顺带重爬过去 7 天
    python refresh_crawl.py --dry-run          # 只读体检（不动任何数据）
    python refresh_crawl.py --prune-days 180  # 清理 180 天前的数据

## 前置条件

爬虫本身依赖 CDP 连 Edge 复用 URP 登录态（见 crawler_playwright.py 头部），
本脚本不重复实现那套，只负责「何时爬、爬哪些、怎么覆盖、爬完怎么校验」。
"""
import argparse
import os
import sqlite3
import sys
from datetime import datetime, timedelta

import config


# ── 只读体检：不动任何数据 ──────────────────────────────────────
def inspect_db(verbose=True):
    """体检数据库，返回统计 dict。全程只读，绝不写。"""
    if not os.path.exists(config.DB_PATH):
        return {"exists": False}
    with sqlite3.connect(f"file:{config.DB_PATH}?mode=ro", uri=True) as conn:
        cur = conn.execute(
            "SELECT COUNT(*), COUNT(DISTINCT date), MIN(date), MAX(date) "
            "FROM free_rooms")
        total, days, mind, maxd = cur.fetchone()
        # 每天行数分布（找出异常稀少的日期）
        per_day = dict(conn.execute(
            "SELECT date, COUNT(*) FROM free_rooms GROUP BY date "
            "ORDER BY date").fetchall())
        # 校区分布
        by_campus = dict(conn.execute(
            "SELECT campus_name, COUNT(*) FROM free_rooms "
            "GROUP BY campus_name").fetchall())
    stats = {
        "exists": True, "rows": total, "days": days,
        "min_date": mind, "max_date": maxd,
        "by_campus": by_campus,
        "thin_days": [d for d, n in per_day.items() if n < 100],
        "today": datetime.now().strftime("%Y-%m-%d"),
    }
    if verbose:
        print(f"  数据库：{config.DB_PATH}")
        print(f"  总行数：{stats['rows']:,}　日期数：{stats['days']}"
              f"　范围：{stats['min_date']} ~ {stats['max_date']}")
        print(f"  校区分布：{stats['by_campus']}")
        if stats["thin_days"]:
            print(f"  [注意] 数据稀少的日期（<100 行）：{stats['thin_days']}")
        if stats["max_date"] and stats["max_date"] < stats["today"]:
            print(f"  [注意] 最新数据 {stats['max_date']} 早于今天 {stats['today']}，"
                  f"站点会提示「未覆盖今天」")
    return stats


# ── 覆盖式重爬：先删后插 ────────────────────────────────────────
def clear_dates(dates):
    """删除指定日期的全部行 —— 这是「覆盖旧数据」的关键一步。

    原爬虫用 INSERT OR IGNORE，命中 UNIQUE 就跳过，旧值永远留着。
    必须先 DELETE 再让爬虫插入，才能保证以最新抓取为准。
    """
    if not dates:
        return 0
    with sqlite3.connect(config.DB_PATH) as conn:
        n = 0
        for d in dates:
            cur = conn.execute("DELETE FROM free_rooms WHERE date = ?", (d,))
            n += cur.rowcount if cur.rowcount > 0 else 0
    return n


def build_date_plan(days, repast, prune_days):
    """算出「该爬哪些日期」与「该清理哪些日期」。"""
    today = datetime.now().date()
    future = [today + timedelta(days=i) for i in range(max(days, 0))]
    past = []
    if repast > 0:
        past = [today - timedelta(days=i) for i in range(1, repast + 1)]
    plan = {
        "crawl": sorted(future + past),
        "prune": [],
        "today": today.strftime("%Y-%m-%d"),
    }
    if prune_days and prune_days > 0:
        cutoff = (today - timedelta(days=prune_days)).strftime("%Y-%m-%d")
        plan["prune"] = cutoff
    return plan


def do_prune(cutoff):
    """清理早于 cutoff 的数据。默认不启用 —— 线上 130 天是资产。"""
    with sqlite3.connect(config.DB_PATH) as conn:
        cur = conn.execute("DELETE FROM free_rooms WHERE date < ?", (cutoff,))
        n = cur.rowcount if cur.rowcount > 0 else 0
    return n


# ── 爬完自校验：数据不能「看起来成功了其实是空的」 ──────────────
def verify_after_crawl(dates, min_rows_per_day=50):
    """爬完后核对行数，低于阈值就报警。

    为什么需要：CDP 复用登录态时，Cookie 失效会让教务接口返回空列表，
    爬虫不报错、DB 里被 DELETE 清空却插不进新值 —— 静默数据丢失。
    """
    problems = []
    with sqlite3.connect(f"file:{config.DB_PATH}?mode=ro", uri=True) as conn:
        for d in dates:
            n = conn.execute(
                "SELECT COUNT(*) FROM free_rooms WHERE date = ?", (d,)
            ).fetchone()[0]
            if n < min_rows_per_day:
                problems.append((d, n))
    return problems


def main():
    ap = argparse.ArgumentParser(
        description="固定刷新爬取：拿最新数据、覆盖旧值、只读模式安全")
    ap.add_argument("--days", type=int, default=7,
                    help="从今天起爬未来几天（默认 7）")
    ap.add_argument("--repast", type=int, default=0,
                    help="额外重爬过去几天（默认 0，历史数据通常不需重爬）")
    ap.add_argument("--dry-run", action="store_true",
                    help="只读体检：不写库、不请求教务系统")
    ap.add_argument("--prune-days", type=int, default=0,
                    help="清理早于 N 天前的数据（默认 0=不清理，保护线上 130 天资产）")
    ap.add_argument("--skip-crawl", action="store_true",
                    help="只做清理/校验，不启动爬虫（供测试与排障）")
    args = ap.parse_args()

    print("=" * 62)
    print("固定刷新爬取 · 覆盖旧数据 · 只读模式安全")
    print("=" * 62)

    print("\n[1/4] 爬取前体检（只读）")
    before = inspect_db()

    plan = build_date_plan(args.days, args.repast, args.prune_days)
    print(f"\n[2/4] 计划")
    print(f"  待爬日期：{len(plan['crawl'])} 天"
          f"（{plan['crawl'][0]} ~ {plan['crawl'][-1]}）")
    if args.repast:
        print(f"  含重爬过去 {args.repast} 天")
    if plan["prune"]:
        print(f"  将清理早于 {plan['prune']} 的数据")

    if args.dry_run:
        print("\n[dry-run] 只读模式，未写库、未启动爬虫。以上为体检结果。")
        return 0

    # 覆盖式清理：先删后爬，保证以最新抓取为准
    print(f"\n[3/4] 覆盖清理（DELETE 后重插，避免 INSERT OR IGNORE 留旧值）")
    removed = clear_dates([d.strftime("%Y-%m-%d") for d in plan["crawl"]])
    print(f"  已清除 {removed:,} 行旧数据")

    if plan["prune"]:
        pruned = do_prune(plan["prune"])
        print(f"  已清理 {pruned:,} 行早于 {plan['prune']} 的数据")

    if args.skip_crawl:
        print("\n[--skip-crawl] 未启动爬虫。")
    else:
        print(f"\n[4/4] 启动爬虫（CDP 复用 Edge 登录态）")
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        try:
            from crawler_playwright import TUSTCrawlerPW
        except ImportError as e:
            print(f"  [错误] 无法导入爬虫模块：{e}")
            print("  请确认已安装依赖：pip install -r requirements.txt")
            return 1

        crawler = TUSTCrawlerPW()
        # 逐日爬：一天失败不影响其他天，且便于定位问题
        failed = []
        for d in plan["crawl"]:
            offset = (d - datetime.now().date()).days
            try:
                crawler.run(date_str=d.strftime("%Y-%m-%d"),
                            dayoffset=max(offset, 0))
                print(f"  [OK] {d}")
            except Exception as e:
                print(f"  [FAIL] {d} → {e}")
                failed.append(d)

        print(f"\n爬取完成：{len(plan['crawl']) - len(failed)} 天成功，"
              f"{len(failed)} 天失败")

        # 自校验：抓不到数据要吼出来，不能静默
        problems = verify_after_crawl(
            [d.strftime("%Y-%m-%d") for d in plan["crawl"]])
        if problems:
            print("\n[警告] 以下日期数据量异常偏低，可能是登录态失效或接口变更：")
            for d, n in problems:
                print(f"  {d}：仅 {n} 行")
            print("  建议：先重新登录 URP，再重跑本脚本。")
            print("  注意：此时 DB 中这些日期已被清空，别直接导出发布！")
            return 2

    print("\n[收尾] 爬取后体检")
    inspect_db()
    print("\n下一步：python export_static.py --meta-only（或补爬满数据后全量导出）")
    return 0


if __name__ == "__main__":
    sys.exit(main())