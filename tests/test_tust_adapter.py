"""TUST 适配器测试：解析逻辑 + 契约合规 + 老配置兼容"""
import re

import pytest

from campusfree.adapter import validate_adapter
from campusfree.registry import get_adapter, list_adapters, schools_summary


def test_adapter_contract(tust_adapter):
    assert validate_adapter(tust_adapter) == []


def test_profile_values(tust_adapter):
    p = tust_adapter.profile
    assert p.school_id == "tust"
    assert p.school_name == "天津科技大学"
    assert p.base_url == "http://jwxtxs.tust.edu.cn:46110"
    assert len(p.periods) == 13
    assert p.periods[1] == "08:20-09:05"
    assert p.periods[13] == "21:20-22:05"
    assert p.default_campus == "泰达"
    assert p.campus_order == ["泰达", "河西"]


def test_browser_profile_dir_is_legacy_path(tust_adapter):
    """沿用老 profile 目录，老用户升级后不用重新登录"""
    assert "tust-classroom" in tust_adapter.browser.profile_dir
    assert tust_adapter.browser.cdp_endpoint == "http://127.0.0.1:9222"


def test_list_campuses_parses_urp_shape(tust_adapter, fake_page):
    campuses = tust_adapter.list_campuses(fake_page)
    assert [(c.code, c.name) for c in campuses] == [("02", "泰达"), ("01", "河西")]


def test_list_campuses_strips_whitespace(tust_adapter):
    class P:
        def evaluate(self, s, a=None):
            return [{"id": "02", "text": "泰 达\n校区"}]

    got = tust_adapter.list_campuses(P())
    assert got[0].name == "泰达校区"


def test_list_buildings(tust_adapter, fake_page):
    from campusfree.model import Campus

    got = tust_adapter.list_buildings(fake_page, Campus(code="02", name="泰达"))
    assert [(b.code, b.name) for b in got] == [("9", "9号楼"), ("3", "3号楼")]


def test_list_buildings_handles_missing_id(tust_adapter):
    """楼号字段缺失（接口偶发）时不能抛异常，应返回空列表"""
    class P:
        def evaluate(self, s, a=None):
            return [{"teachingBuildingName": "无名楼"}]

    from campusfree.model import Campus

    assert tust_adapter.list_buildings(P(), Campus(code="02", name="泰达")) == []


def test_select_building_uses_position_format(tust_adapter):
    """URP 要求 position = 校区编码_楼编码"""
    from campusfree.model import Building, Campus

    seen = {}

    class P:
        def evaluate(self, s, a=None):
            seen.update(a)
            return True

    ok = tust_adapter.select_building(
        P(), Campus(code="02", name="泰达"), Building(code="9", name="9号楼")
    )
    assert ok is True
    assert seen["position"] == "02_9"
    assert seen["xqm"] == "泰达"


def test_select_building_returns_false_on_exception(tust_adapter):
    from campusfree.model import Building, Campus

    class P:
        def evaluate(self, s, a=None):
            raise RuntimeError("页面已关闭")

    assert tust_adapter.select_building(
        P(), Campus(code="02", name="泰达"), Building(code="9", name="9号楼")
    ) is False


def test_list_free_rooms(tust_adapter, fake_page):
    rooms = tust_adapter.list_free_rooms(fake_page, 1, 0)
    names = sorted(r.classroom_name for r in rooms)
    assert names == ["3-201", "9-101", "9-102"]
    assert all(r.building_name for r in rooms)


def test_list_free_rooms_handles_error_payload(tust_adapter):
    class P:
        def evaluate(self, s, a=None):
            return {"error": "HTTP 500"}

    assert tust_adapter.list_free_rooms(P(), 1, 0) == []


def test_list_free_rooms_handles_garbage(tust_adapter):
    class P:
        def evaluate(self, s, a=None):
            return "not a dict"

    assert tust_adapter.list_free_rooms(P(), 1, 0) == []


def test_login_detection(tust_adapter):
    class P:
        def __init__(self, url):
            self.url = url

    assert tust_adapter.is_logged_in(P("http://jwxtxs.tust.edu.cn:46110/x")) is True
    assert tust_adapter.is_logged_in(P("http://authserver.tust.edu.cn/login")) is False
    assert "jwxtxs" in tust_adapter.login_hint()


def test_registry_discovers_tust():
    assert "tust" in list_adapters()
    assert get_adapter("tust").profile.school_id == "tust"
    assert schools_summary()[0]["school_name"] == "天津科技大学"


def test_unknown_school_gives_hint():
    with pytest.raises(KeyError) as exc:
        get_adapter("nope")
    assert "tust" in str(exc.value)


def test_legacy_config_constants_still_work():
    """老脚本 import config 必须继续能用，且值与适配器一致"""
    import config
    from adapters.tust import BASE_URL, PERIODS

    assert config.BASE_URL == BASE_URL
    assert config.PERIODS == PERIODS
    assert config.CAMPUS_LIST_API.startswith(BASE_URL)
    assert config.FREE_ROOM_API.endswith("/today")
    assert config.DB_PATH.endswith("classrooms.db")
