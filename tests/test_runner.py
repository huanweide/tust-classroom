"""爬取调度测试：翻日期 / 翻校区 / 翻楼 / 翻节次，以及断点续传与失败隔离"""
from datetime import datetime, timedelta

import pytest

from campusfree.adapter import SchoolAdapter
from campusfree.model import Building, Campus, Room
from campusfree.runner import CrawlRunner, RunOptions, parse_range
from campusfree.store import RoomStore


class DemoAdapter(SchoolAdapter):
    """最简适配器：用于测试框架本身（挂着 conftest 里的假页面）"""

    def __init__(self, profile):
        self._profile = profile

    @property
    def profile(self):
        return self._profile

    def list_campuses(self, page):
        # 走假页面的接口（这样 fail_campus_api 才能真的触发兜底分支）
        raw = page.evaluate("queryCodeCampusList") or []
        return [Campus(code=str(i["id"]), name=i["text"]) for i in raw]

    def list_buildings(self, page, campus):
        data = {"02": [("9", "9号楼")], "01": [("A", "A楼")]}
        return [Building(code=b, name=n) for b, n in data.get(campus.code, [])]

    def select_building(self, page, campus, building):
        return True

    def list_free_rooms(self, page, period, day_offset):
        if (period, day_offset) == (1, 0):
            return [Room(building_name="9号楼", classroom_name="9-101")]
        return []


@pytest.fixture
def runner(demo_profile, tmp_store):
    return CrawlRunner(DemoAdapter(demo_profile), tmp_store, log=lambda m: None)


def test_single_day_crawl(runner, fake_page, tmp_store):
    report = runner.run(fake_page, RunOptions(day_offsets=[0]))
    assert report.days_done == 1
    today = datetime.now().strftime("%Y-%m-%d")
    assert tmp_store.count_date(today) >= 1
    assert report.total_rows >= 1


def test_campus_fallback_used_when_api_fails(demo_profile, tmp_store, fake_page):
    """校区接口返回空 → 应改用适配器的兜底方案，而不是直接放弃"""
    fake_page.fail_campus_api = True
    calls = []

    class FallbackAdapter(DemoAdapter):
        def fallback_campuses(self, page):
            calls.append("used")
            return [Campus(code="02", name="泰达")]

    r = CrawlRunner(FallbackAdapter(demo_profile), tmp_store, log=lambda m: None)
    report = r.run(fake_page, RunOptions(day_offsets=[0]))
    assert calls == ["used"]
    assert report.days_done == 1


def test_resume_skips_existing_day(runner, fake_page, tmp_store):
    """多天模式下，已有数据的那天应整日跳过，不删不重爬"""
    today = datetime.now().strftime("%Y-%m-%d")
    tmp_store.save_rooms("泰达", [Room("9号楼", "9-999")], 1, today)
    before = tmp_store.count_date(today)

    report = runner.run(fake_page, RunOptions.from_range(0, 2))
    assert report.days_skipped == 1
    assert tmp_store.count_date(today) == before  # 没被清掉重爬


def test_clear_before_today(runner, fake_page, tmp_store):
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    tmp_store.save_rooms("泰达", [Room("9号楼", "9-001")], 1, yesterday)
    runner.run(fake_page, RunOptions(day_offsets=[0], clear_before_today=True))
    assert tmp_store.count_date(yesterday) == 0


def test_building_error_is_isolated(demo_profile, tmp_store, fake_page):
    """某栋楼切换失败不能让整轮崩掉"""
    class FlakyAdapter(DemoAdapter):
        def select_building(self, page, campus, building):
            return False  # 全部失败

    r = CrawlRunner(FlakyAdapter(demo_profile), tmp_store, log=lambda m: None)
    report = r.run(fake_page, RunOptions(day_offsets=[0]))
    assert report.days_done == 1
    assert report.total_rows == 0


def test_exception_in_rooms_is_recorded(demo_profile, tmp_store, fake_page):
    class BoomAdapter(DemoAdapter):
        def list_free_rooms(self, page, period, day_offset):
            raise RuntimeError("教务系统抽风")

    r = CrawlRunner(BoomAdapter(demo_profile), tmp_store, log=lambda m: None)
    report = r.run(fake_page, RunOptions(day_offsets=[0]))
    assert report.errors
    assert "教务系统抽风" in report.errors[0]


def test_auto_expand_stops_on_empty_streak(demo_profile, tmp_store, fake_page):
    """连续多天爬不到东西 → 判定学期结束，提前收工"""
    class AlwaysEmptyAdapter(DemoAdapter):
        def list_free_rooms(self, page, period, day_offset):
            return []

    r = CrawlRunner(AlwaysEmptyAdapter(demo_profile), tmp_store, log=lambda m: None)
    report = r.run(fake_page, RunOptions(auto_expand=True, max_days=40, stop_threshold=3))
    assert report.stopped_early is True
    assert report.days_done == 3


@pytest.mark.parametrize("text,expected", [
    ("0-6", (0, 6)),
    ("0-0", (0, 0)),
    (" 1-3 ", (1, 3)),
])
def test_parse_range_ok(text, expected):
    assert parse_range(text) == expected


@pytest.mark.parametrize("bad", ["", "0", "1-2-3", "a-b", "5-1", "x"])
def test_parse_range_rejects_bad_input(bad):
    with pytest.raises(ValueError):
        parse_range(bad)
