"""TUST 空闲教室爬虫 —— 兼容入口（v2 起内部改为调用 campusfree 框架）

老用法完全不变（auto_update.bat / 任务计划程序照跑）：
    python crawler_playwright.py --range 0-6
    python crawler_playwright.py --dayoffset 1
    python crawler_playwright.py --auto

新用法（推荐，支持任意学校）：
    python -m campusfree run --school tust --range 0-6

内部流程：连本机 Edge 的调试端口复用登录态 → 按校区/楼/节次翻数据 → 存 SQLite。
全程不碰账号密码，也不保存 Cookie 文件。
"""
import argparse
import sys

import config
from campusfree import cdp
from campusfree.registry import get_adapter
from campusfree.runner import CrawlRunner, RunOptions, parse_range
from campusfree.store import RoomStore

# 老代码里可能有别的地方 import 这两个名字，保留导出
CDP_ENDPOINT = None  # 运行时由 adapter.browser 决定；见 _endpoint()


def _endpoint() -> str:
    return get_adapter("tust").browser.cdp_endpoint


class TUSTCrawlerPW:
    """老类名保留：内部已改为「框架 + TUST 适配器」实现"""

    def __init__(self, db_path: str = None):
        self.adapter = get_adapter("tust")
        self.store = RoomStore(db_path or config.DB_PATH)

    # ── 老接口：建表 ──
    def _ensure_db(self):
        # RoomStore 在构造时就建好表与索引，这里留空只为兼容老调用
        return True

    # ── 老接口：清某天 ──
    def clear_today_cache(self, date_str):
        self.store.clear_date(date_str)

    # ── 老接口：启动 Edge 调试模式 ──
    def _ensure_edge_debug(self):
        return cdp.ensure_browser(self.adapter.browser)

    def run(self, date_str=None, dayoffset=1, day_range=None, auto=False):
        """爬取空闲教室（参数语义与老版本完全一致）"""
        if not self._ensure_edge_debug():
            print("[错误] 无法启动 Edge 调试模式")
            sys.exit(1)

        if day_range is not None:
            options = RunOptions.from_range(day_range[0], day_range[1])
        elif auto:
            options = RunOptions(auto_expand=True, clear_before_today=True, building_gap=0.3)
        else:
            options = RunOptions(day_offsets=[dayoffset], building_gap=0.3)
        if date_str:
            options.fixed_date = date_str

        browser = cdp.connect_cdp(self.adapter.browser)
        try:
            page = cdp.open_entry_page(browser, self.adapter.browser,
                                       self.adapter.profile.entry_url())
            if not self.adapter.is_logged_in(page):
                print("[错误] " + self.adapter.login_hint())
                sys.exit(1)
            print("[登录] 已通过 Edge Profile 复用登录态 [OK]")

            runner = CrawlRunner(self.adapter, self.store)
            report = runner.run(page, options)
            print(f"\n[爬取] 完成, 共写入 {report.total_rows} 条记录")
            return report.total_rows
        finally:
            try:
                browser.close()
            except Exception:
                pass


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="TUST 空闲教室爬虫（v2：campusfree 框架驱动）"
    )
    parser.add_argument("--range", type=str, default=None,
                        help="日期范围，如 '0-6' 表示今天到 6 天后（共 7 天）")
    parser.add_argument("--dayoffset", type=int, default=1,
                        help="单天偏移，默认 1=明天")
    parser.add_argument("--auto", action="store_true",
                        help="自动边界探测：从今天爬到连续无数据（学期结束）即停")
    parser.add_argument("--school", default="tust",
                        help="学校 ID（默认 tust）；换成别的学校适配器即可复用本脚本")
    args = parser.parse_args(argv)

    crawler = TUSTCrawlerPW()
    if args.range:
        try:
            start, end = parse_range(args.range)
        except ValueError as exc:
            print(f"[错误] {exc}", file=sys.stderr)
            return 2
        total = crawler.run(day_range=(start, end))
    elif args.auto:
        total = crawler.run(auto=True)
    else:
        total = crawler.run(dayoffset=args.dayoffset)
    print(f"\n完成! 共 {total} 条空闲教室记录")
    return 0


if __name__ == "__main__":
    sys.exit(main())
