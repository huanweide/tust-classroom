"""测试夹具：提供一个「假教务系统页面」

真实测试要连浏览器、要校园网、要登录态，CI 上根本跑不了。
所以这里造一个假的 page 对象：它只有 .url 和 .evaluate()，
按请求 URL 里的关键词分发现成数据 —— 足够把框架整条流水线跑一遍。
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from campusfree.model import Campus  # noqa: E402


class FakeUrpPage:
    """假教务页面：按 JS 里的接口关键字返回数据"""

    def __init__(self, campuses=None, buildings=None, rooms=None, url=None, fail_campus_api=False):
        # campuses: [(code, name)]
        self._campuses = campuses or []
        # buildings: {campus_code: [(bcode, bname)]}
        self._buildings = buildings or {}
        # rooms: {(period, day_offset): [Room 风格 dict]}
        self._rooms = rooms or {}
        self.url = url or "http://jw.example.edu.cn/freeClassroom/index"
        self.fail_campus_api = fail_campus_api
        self.calls = []

    def evaluate(self, script, arg=None):
        self.calls.append((script, arg))

        if "queryCodeCampusList" in script:
            if self.fail_campus_api:
                return []
            return [{"id": c, "text": n} for c, n in self._campuses]

        if "queryCodeTeaBuildingList" in script:
            code = arg if isinstance(arg, str) else (arg or {}).get("campus_code")
            return [
                {"id": {"teachingBuildingNumber": b}, "teachingBuildingName": n}
                for b, n in self._buildings.get(code, [])
            ]

        if "freeClassroom/today/" in script:
            period = arg["period"]
            off = arg["dayoffset"]
            return self._make_payload(self._rooms.get((period, off), []))

        if "'position'" in script or "position" in script:
            return True

        return None

    @staticmethod
    def _make_payload(rooms):
        """把 [(楼名, 教室名)] 转成 URP 风格返回"""
        by_building = {}
        for bname, rname in rooms:
            by_building.setdefault(bname, []).append({"classroom": rname})
        return {
            "spareroomObjList": [
                {"acmcBuildingName": b, "claroom": rs} for b, rs in by_building.items()
            ]
        }


@pytest.fixture
def fake_page():
    return FakeUrpPage(
        campuses=[("02", "泰达"), ("01", "河西")],
        buildings={
            "02": [("9", "9号楼"), ("3", "3号楼")],
            "01": [("A", "A楼")],
        },
        rooms={
            (1, 0): [("9号楼", "9-101"), ("9号楼", "9-102"), ("3号楼", "3-201")],
            (2, 0): [("9号楼", "9-101")],
            (1, 1): [("A楼", "A-301")],
        },
    )


@pytest.fixture
def tmp_store(tmp_path):
    from campusfree.store import RoomStore

    return RoomStore(str(tmp_path / "test.db"))


@pytest.fixture
def tust_adapter():
    from adapters.tust import ADAPTER

    return ADAPTER()


@pytest.fixture
def demo_profile():
    from campusfree.model import SchoolProfile, periods_from_list

    return SchoolProfile(
        school_id="demo",
        school_name="示例大学",
        base_url="https://jw.example.edu.cn",
        periods=periods_from_list([(1, "08:00-08:45"), (2, "08:55-09:40")]),
        entry_path="/freeClassroom/index",
        default_campus="主校区",
        campus_order=["主校区"],
        source_note="测试用",
    )
