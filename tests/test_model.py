"""模型层测试"""
from campusfree.model import (
    Building,
    Campus,
    Period,
    Room,
    SchoolProfile,
    periods_from_list,
)


def test_periods_from_list():
    assert periods_from_list([(1, "08:00-08:45"), (2, "08:55-09:40")]) == {
        1: "08:00-08:45",
        2: "08:55-09:40",
    }


def test_period_numbers_sorted():
    p = SchoolProfile(
        school_id="x", school_name="X", base_url="https://x.edu.cn",
        periods={3: "c", 1: "a", 2: "b"},
    )
    assert p.period_numbers() == [1, 2, 3]


def test_entry_url_variants():
    base = "https://x.edu.cn/"
    assert SchoolProfile("x", "X", base, {1: "a"}).entry_url() == "https://x.edu.cn/"
    assert SchoolProfile("x", "X", base, {1: "a"}, entry_path="/a/b").entry_url() == "https://x.edu.cn/a/b"
    assert SchoolProfile("x", "X", base, {1: "a"}, entry_path="a/b").entry_url() == "https://x.edu.cn/a/b"


def test_room_full_name():
    assert Room(building_name="9号楼", classroom_name="9-101").full_name() == "9号楼9-101"


def test_campus_and_building_str():
    assert str(Campus(code="02", name="泰达")) == "泰达(02)"
    assert str(Building(code="9", name="9号楼")) == "9号楼(9)"
    assert str(Period(number=1, time_range="08:00-08:45")) == "第1节 08:00-08:45"
