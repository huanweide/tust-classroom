"""适配器契约校验测试

这些用例的价值：校外同学照着模板写适配器，最容易「继承了但方法没写完」
或「网址忘了写 http」。契约校验要在他运行 check 命令时就报错，
而不是等跑了半天才在半夜的定时任务里炸掉。
"""
import pytest

from campusfree.adapter import BrowserSpec, SchoolAdapter, validate_adapter
from campusfree.model import Building, Campus, Room, SchoolProfile


def _good_profile(**kw):
    data = {
        "school_id": "demo",
        "school_name": "示例大学",
        "base_url": "https://jw.example.edu.cn",
        "periods": {1: "08:00-08:45"},
    }
    data.update(kw)
    return SchoolProfile(**data)


class GoodAdapter(SchoolAdapter):
    @property
    def profile(self):
        return _good_profile()

    def list_campuses(self, page):
        return []

    def list_buildings(self, page, campus):
        return []

    def select_building(self, page, campus, building):
        return True

    def list_free_rooms(self, page, period, day_offset):
        return []


def test_valid_adapter_passes():
    assert validate_adapter(GoodAdapter()) == []


def test_incomplete_adapter_cannot_even_be_built():
    """只写了一部分的适配器，Python 在实例化阶段就拦下（早失败，好过半夜炸）"""
    class Incomplete(SchoolAdapter):
        @property
        def profile(self):
            return _good_profile()

        def list_campuses(self, page):
            return []

    with pytest.raises(TypeError) as exc:
        Incomplete()
    assert "abstract" in str(exc.value).lower()


def test_duck_typed_object_missing_methods():
    """没继承 SchoolAdapter 但长得像适配器的对象：要给出「缺了哪些方法」的清单"""
    class Duck:
        profile = _good_profile()

        def list_campuses(self, page):
            return []

    problems = validate_adapter(Duck())
    joined = "\n".join(problems)
    assert "必须继承" in joined
    for name in ("list_buildings", "select_building", "list_free_rooms"):
        assert name in joined


def test_non_adapter_class_rejected():
    class NotAnAdapter:
        pass

    problems = validate_adapter(NotAnAdapter())
    assert any("必须继承" in p for p in problems)


@pytest.mark.parametrize("bad_url", ["jw.example.edu.cn", "", "ftp://x", "example.com"])
def test_bad_base_url(bad_url):
    class A(GoodAdapter):
        @property
        def profile(self):
            return _good_profile(base_url=bad_url)

    problems = validate_adapter(A())
    assert any("base_url" in p for p in problems)


def test_empty_periods():
    class A(GoodAdapter):
        @property
        def profile(self):
            return _good_profile(periods={})

    assert any("periods" in p for p in validate_adapter(A()))


def test_period_key_must_be_positive_int():
    class A(GoodAdapter):
        @property
        def profile(self):
            return _good_profile(periods={0: "x", 2: "y"})

    assert any(">=" in p for p in validate_adapter(A()))


def test_period_without_time():
    class A(GoodAdapter):
        @property
        def profile(self):
            return _good_profile(periods={1: "  "})

    assert any("没有填写时间" in p for p in validate_adapter(A()))


def test_default_campus_must_be_in_order():
    class A(GoodAdapter):
        @property
        def profile(self):
            return _good_profile(default_campus="南校区", campus_order=["主校区"])

    assert any("default_campus" in p for p in validate_adapter(A()))


def test_non_ascii_school_id_rejected():
    class A(GoodAdapter):
        @property
        def profile(self):
            return _good_profile(school_id="示例")

    assert any("school_id" in p for p in validate_adapter(A()))


def test_browser_spec_endpoint_uses_ipv4():
    spec = BrowserSpec(exe_path="edge.exe", profile_dir="p", debug_port=9333)
    assert spec.cdp_endpoint == "http://127.0.0.1:9333"
    assert "edge.exe" in spec.describe()


def test_is_logged_in_detects_login_page():
    class FakePage:
        def __init__(self, url):
            self.url = url

    a = GoodAdapter()
    assert a.is_logged_in(FakePage("https://jw.example.edu.cn/free/index")) is True
    assert a.is_logged_in(FakePage("https://authserver.example.edu.cn/login")) is False


def test_normalize_room_name_strips_whitespace():
    assert GoodAdapter().normalize_room_name(" 9-101 \n") == "9-101"
    assert GoodAdapter().normalize_room_name("") == ""
