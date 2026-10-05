"""命令行入口 —— 一个命令管所有学校

    python -m campusfree schools                  # 看看现在支持哪些学校
    python -m campusfree check --school tust      # 体检某个适配器写得对不对
    python -m campusfree run --school tust --range 0-6
    python -m campusfree export --school tust
    python -m campusfree new-school nku           # 生成一个新学校适配器的骨架
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import List, Optional

from .adapter import validate_adapter
from .exporter import StaticExporter
from .model import SchoolProfile
from .registry import get_adapter, schools_summary
from .runner import CrawlRunner, RunOptions, parse_range
from .store import RoomStore, default_db_path

# 项目根目录（campusfree/ 的上一级）
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _db_path_for(school_id: str, legacy: bool = False) -> str:
    """数据库路径：老学校继续用 data/classrooms.db，新学校用 data/<id>.db"""
    if legacy or school_id == "tust":
        return os.path.join(ROOT, "data", "classrooms.db")
    return default_db_path(ROOT, school_id)


def _out_dir_for(school_id: str, legacy: bool = False) -> str:
    if legacy or school_id == "tust":
        return os.path.join(ROOT, "static", "data")
    return os.path.join(ROOT, "sites", school_id, "data")


# ── 子命令 ──

def cmd_schools(args) -> int:
    rows = schools_summary()
    if not rows:
        print("还没有注册任何学校适配器。用 `python -m campusfree new-school <id>` 创建第一个。")
        return 1
    print(f"已注册 {len(rows)} 所学校：\n")
    print(f"{'ID':<12}{'学校':<20}{'节次':<6}{'默认校区':<10}教务系统")
    print("-" * 90)
    for r in rows:
        print(f"{r['school_id']:<12}{r['school_name']:<20}{r['periods']:<6}"
              f"{r['default_campus']:<10}{r['base_url']}")
    return 0


def cmd_check(args) -> int:
    try:
        adapter = get_adapter(args.school)
    except KeyError as exc:
        print(f"[错误] {exc}")
        return 2

    problems = validate_adapter(adapter)
    prof: SchoolProfile = adapter.profile
    print(f"体检对象：{prof.school_name}（{prof.school_id}）")
    print(f"  教务系统：{prof.entry_url()}")
    print(f"  节次数量：{len(prof.periods)}")
    print(f"  默认校区：{prof.default_campus or '（未指定，取数据首个）'}")
    print(f"  浏览器  ：{adapter.browser.describe()}")

    if problems:
        print(f"\n[不合格] 发现 {len(problems)} 个问题：")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("\n[合格] 适配器契约检查全部通过，可以开爬。")
    return 0


def cmd_run(args) -> int:
    try:
        adapter = get_adapter(args.school)
    except KeyError as exc:
        print(f"[错误] {exc}")
        return 2

    problems = validate_adapter(adapter)
    if problems:
        print(f"[错误] 适配器 {args.school} 不合格，请先修复：")
        for p in problems:
            print(f"  - {p}")
        return 2

    if args.range:
        try:
            start, end = parse_range(args.range)
        except ValueError as exc:
            print(f"[错误] {exc}", file=sys.stderr)
            return 2
        options = RunOptions.from_range(
            start, end, clear_before_today=args.clear_old,
            period_gap=args.gap, building_gap=max(args.gap, 0.3),
        )
    elif args.auto:
        options = RunOptions(
            auto_expand=True, max_days=args.max_days, stop_threshold=args.stop_threshold,
            clear_before_today=args.clear_old, period_gap=args.gap,
        )
    else:
        options = RunOptions(
            day_offsets=[args.dayoffset], clear_before_today=args.clear_old,
            period_gap=args.gap,
        )

    store = RoomStore(_db_path_for(args.school))
    runner = CrawlRunner(adapter, store)

    # 只有真的要开爬时才 import playwright / 连浏览器
    try:
        from . import cdp
    except Exception as exc:  # pragma: no cover
        print(f"[错误] 依赖加载失败：{exc}")
        return 2

    spec = adapter.browser
    if not cdp.ensure_browser(spec):
        print(f"[错误] 无法启动调试模式浏览器：{spec.browser_name}")
        print(f"       请确认已安装：{spec.exe_path}")
        return 1

    browser = cdp.connect_cdp(spec)
    try:
        page = cdp.open_entry_page(browser, spec, adapter.profile.entry_url())
        if not adapter.is_logged_in(page):
            print(f"[错误] {adapter.login_hint()}")
            return 1
        print("[登录] 已复用浏览器登录态 [OK]")
        report = runner.run(page, options)
        print(f"\n{report.summary()}")
        for err in report.errors[:10]:
            print(f"  [ERR] {err}")
        return 0 if not report.errors else 1
    finally:
        try:
            browser.close()
        except Exception:
            pass


def cmd_export(args) -> int:
    try:
        adapter = get_adapter(args.school)
    except KeyError as exc:
        print(f"[错误] {exc}")
        return 2
    store = RoomStore(_db_path_for(args.school))
    out_dir = args.out or _out_dir_for(args.school)
    static_exp = StaticExporter(store, adapter.profile, out_dir)
    stats = static_exp.export(verbose=not args.quiet)
    oversized = stats.get("oversized_files") or []
    print(f"\n[导出] 输出目录：{out_dir}")
    print(f"[导出] 共 {stats.get('dates', 0)} 天、{stats.get('rooms', 0)} 间教室，"
          f"合计 {stats.get('total_bytes', 0) / 1024:.0f} KB")
    if oversized:
        print(f"[提醒] 以下文件偏大（>500KB），手机流量加载会慢：{', '.join(oversized)}")
    return 0


def cmd_new_school(args) -> int:
    from .scaffold import create_adapter_scaffold

    path = create_adapter_scaffold(ROOT, args.school_id, school_name=args.name)
    print(f"[生成] 新学校适配器骨架：{path}")
    print("\n下一步：")
    print(f"  1. 打开 {path}，把 SchoolProfile 里的网址、节次表改成你们学校的")
    print("  2. 实现 list_campuses / list_buildings / select_building / list_free_rooms 四个方法")
    print(f"  3. 自检：python -m campusfree check --school {args.school_id}")
    print(f"  4. 开爬：python -m campusfree run --school {args.school_id} --range 0-6")
    print("\n完整教程见 docs/ADAPTER_GUIDE.md")
    return 0


# ── 参数解析 ──

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="campusfree",
        description="校园空闲教室接入框架：一套流水线，接任意高校教务系统",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_schools = sub.add_parser("schools", help="列出已注册的学校适配器")
    p_schools.set_defaults(func=cmd_schools)

    p_check = sub.add_parser("check", help="体检某个学校适配器是否合格")
    p_check.add_argument("--school", required=True, help="学校 ID，如 tust")
    p_check.set_defaults(func=cmd_check)

    p_run = sub.add_parser("run", help="爬取空闲教室数据")
    p_run.add_argument("--school", required=True)
    p_run.add_argument("--range", default=None, help="日期范围，如 0-6（今天起 7 天）")
    p_run.add_argument("--dayoffset", type=int, default=1, help="单天偏移，1=明天")
    p_run.add_argument("--auto", action="store_true", help="自动探测学期边界")
    p_run.add_argument("--max-days", type=int, default=130)
    p_run.add_argument("--stop-threshold", type=int, default=14)
    p_run.add_argument("--clear-old", action="store_true", help="开跑前清掉今天之前的旧数据")
    p_run.add_argument("--gap", type=float, default=0.0, help="每个节次之间的间隔秒数")
    p_run.set_defaults(func=cmd_run)

    p_export = sub.add_parser("export", help="导出静态 JSON")
    p_export.add_argument("--school", required=True)
    p_export.add_argument("--out", default=None, help="输出目录，默认按学校自动定位")
    p_export.add_argument("--quiet", action="store_true")
    p_export.set_defaults(func=cmd_export)

    p_new = sub.add_parser("new-school", help="生成一个新学校适配器的骨架文件")
    p_new.add_argument("school_id", help="英文短名，如 nku")
    p_new.add_argument("--name", default="", help="学校中文名")
    p_new.set_defaults(func=cmd_new_school)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
