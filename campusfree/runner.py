"""爬取调度层 —— 通用的「翻日期 × 翻校区 × 翻楼 × 翻节次」循环

这是框架的心脏。它不知道自己爬的是哪所学校，只知道：
    拿到适配器 → 一层层展开 → 把结果丢给存储层。

设计要点：
1. 断点续传：多天模式时某天已有数据就整天跳过，不删不重爬（省时间）。
2. 失败隔离：某栋楼 / 某节次出错只记警告，不让整轮爬取崩掉。
3. 可注入：page 可以外部传入（测试时传假页面，不需要真浏览器）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, List, Optional, Tuple

from .adapter import SchoolAdapter
from .model import Building, Campus
from .store import RoomStore


@dataclass
class RunOptions:
    """一次爬取任务的参数"""
    day_offsets: List[int] = field(default_factory=lambda: [1])
    fixed_date: Optional[str] = None      # 指定首日（一般不用）
    auto_expand: bool = False             # 自动探测学期边界
    max_days: int = 130                   # 自动模式上限天数
    stop_threshold: int = 14              # 连续多少天没数据就认为学期结束
    clear_before_today: bool = False      # 开跑前是否清掉今天之前的数据
    resume: bool = True                   # 多天模式是否续传
    period_gap: float = 0.0               # 每个节次之间的间隔秒数（温柔一点，别把教务系统打挂）
    building_gap: float = 0.3

    @classmethod
    def from_range(cls, start: int, end: int, **kw) -> "RunOptions":
        return cls(day_offsets=list(range(start, end + 1)), **kw)


@dataclass
class RunReport:
    """爬取结果报告"""
    total_rows: int = 0
    days_done: int = 0
    days_skipped: int = 0
    empty_days_in_row: int = 0
    errors: List[str] = field(default_factory=list)
    stopped_early: bool = False

    def summary(self) -> str:
        extra = f"，提前结束（连续 {self.empty_days_in_row} 天无数据）" if self.stopped_early else ""
        return (
            f"完成：写入 {self.total_rows} 条，覆盖 {self.days_done} 天"
            f"（跳过 {self.days_skipped} 天）{extra}"
            + (f"，{len(self.errors)} 个错误" if self.errors else "")
        )


class CrawlRunner:
    """通用爬取器"""

    def __init__(
        self,
        adapter: SchoolAdapter,
        store: RoomStore,
        log: Callable[[str], None] = print,
    ) -> None:
        self.adapter = adapter
        self.store = store
        self.log = log

    # ── 主入口 ──

    def run(self, page: Any, options: RunOptions) -> RunReport:
        report = RunReport()
        offsets = self._build_offsets(options)

        if options.clear_before_today:
            today = datetime.now().strftime("%Y-%m-%d")
            removed = self.store.clear_before(today)
            self.log(f"[清旧] 已删除 {today} 之前的旧学期数据（{removed} 条）")

        campuses = self._resolve_campuses(page)
        if not campuses:
            report.errors.append("没有发现任何校区，爬取终止")
            return report
        self.log(f"[校区] 共 {len(campuses)} 个：{[c.name for c in campuses]}")

        for idx, dayoff in enumerate(offsets):
            date_str = self._date_for(options, idx, dayoff)
            before = report.total_rows
            self.log(f"\n{'#' * 46}\n# 日期 [{idx + 1}/{len(offsets)}] {date_str} (offset={dayoff})\n{'#' * 46}")

            if options.resume and len(offsets) > 1:
                existing = self.store.count_date(date_str)
                if existing > 0:
                    self.log(f"[SKIP] {date_str} 已有 {existing} 条，整日跳过")
                    report.total_rows += existing
                    report.days_skipped += 1
                    continue

            self.store.clear_date(date_str)
            day_rows = self._crawl_one_day(page, date_str, dayoff, campuses, options, report)
            report.days_done += 1

            # 自动边界探测：连续 N 天啥也爬不到 = 学期结束了
            if options.auto_expand:
                if day_rows == 0:
                    report.empty_days_in_row += 1
                    if report.empty_days_in_row >= options.stop_threshold:
                        self.log(f"[停止] 连续 {report.empty_days_in_row} 天无数据，判定学期边界")
                        report.stopped_early = True
                        break
                else:
                    report.empty_days_in_row = 0

            # 上面 _crawl_one_day 已经累加过，这里只做统计展示
            del before

        return report

    # ── 内部步骤 ──

    def _build_offsets(self, options: RunOptions) -> List[int]:
        if options.auto_expand:
            return list(range(0, options.max_days))
        return list(options.day_offsets)

    def _date_for(self, options: RunOptions, idx: int, dayoff: int) -> str:
        if options.fixed_date and idx == 0:
            return options.fixed_date
        return (datetime.now() + timedelta(days=dayoff)).strftime("%Y-%m-%d")

    def _resolve_campuses(self, page: Any) -> List[Campus]:
        """拿校区列表：主接口失败就退回适配器的兜底方案"""
        try:
            campuses = self.adapter.list_campuses(page) or []
        except Exception as exc:
            self.log(f"[警告] 校区接口异常：{exc}")
            campuses = []
        if not campuses:
            self.log("[警告] 未获取到校区列表，改用适配器的兜底方案")
            try:
                campuses = self.adapter.fallback_campuses(page) or []
            except Exception as exc:
                self.log(f"[警告] 兜底方案也失败：{exc}")
                campuses = []
        return campuses

    def _crawl_one_day(
        self,
        page: Any,
        date_str: str,
        dayoff: int,
        campuses: List[Campus],
        options: RunOptions,
        report: RunReport,
    ) -> int:
        day_rows = 0
        for campus in campuses:
            self.log(f"\n[校区] {campus.name} ({campus.code})")
            buildings = self._safe_list_buildings(page, campus, report)
            if not buildings:
                self.log("  [SKIP] 无教学楼")
                continue
            self.log(f"  教学楼 {len(buildings)} 栋")

            for b_idx, building in enumerate(buildings, 1):
                self.log(f"  [{b_idx}/{len(buildings)}] {building.name}")
                if not self._safe_select_building(page, campus, building, report):
                    self.log("    [SKIP] 切换教学楼失败")
                    continue

                if options.building_gap:
                    self._sleep(options.building_gap)

                for period in self.adapter.profile.period_numbers():
                    try:
                        rooms = self.adapter.list_free_rooms(page, period, dayoff) or []
                    except Exception as exc:
                        report.errors.append(f"{date_str} {campus.name} {building.name} 第{period}节: {exc}")
                        continue
                    if rooms:
                        n = self.store.save_rooms(campus.name, rooms, period, date_str)
                        day_rows += n
                        report.total_rows += n
                    if options.period_gap:
                        self._sleep(options.period_gap)
        return day_rows

    def _safe_list_buildings(
        self, page: Any, campus: Campus, report: RunReport
    ) -> List[Building]:
        try:
            return self.adapter.list_buildings(page, campus) or []
        except Exception as exc:
            report.errors.append(f"{campus.name} 教学楼列表失败: {exc}")
            return []

    def _safe_select_building(
        self, page: Any, campus: Campus, building: Building, report: RunReport
    ) -> bool:
        try:
            return bool(self.adapter.select_building(page, campus, building))
        except Exception as exc:
            report.errors.append(f"{campus.name} {building.name} 切换失败: {exc}")
            return False

    @staticmethod
    def _sleep(seconds: float) -> None:  # pragma: no cover - 计时相关
        import time

        time.sleep(seconds)


def parse_range(text: str) -> Tuple[int, int]:
    """解析 '0-6' 这样的范围字符串

    单独抽出来是因为这是最容易写错又最容易被测的一段：
    格式不对要给出人话报错，而不是 Python 抛个 ValueError 完事。
    """
    raw = (text or "").strip()
    parts = raw.split("-")
    if len(parts) != 2:
        raise ValueError(f"--range 格式应为 '起-止'（如 '0-6'），收到：{raw!r}")
    try:
        start, end = int(parts[0]), int(parts[1])
    except ValueError:
        raise ValueError(f"--range 的起止都必须是整数，收到：{raw!r}") from None
    if start > end:
        raise ValueError(f"--range 起始({start}) 不能大于结束({end})")
    return start, end
