"""存储层测试：建表 / 写入去重 / 清理 / 查询"""
from datetime import datetime, timedelta

from campusfree.model import Room
from campusfree.store import RoomStore, default_db_path, legacy_db_path


def test_save_and_count(tmp_store):
    rooms = [Room("9号楼", "9-101"), Room("9号楼", "9-102")]
    assert tmp_store.save_rooms("泰达", rooms, 1, "2026-10-05") == 2
    assert tmp_store.count_date("2026-10-05") == 2


def test_duplicate_write_is_ignored(tmp_store):
    """同一教室同一节次同一天，重复写入不应出现两条（UNIQUE 约束生效）"""
    rooms = [Room("9号楼", "9-101")]
    tmp_store.save_rooms("泰达", rooms, 1, "2026-10-05")
    tmp_store.save_rooms("泰达", rooms, 1, "2026-10-05")
    assert tmp_store.count_date("2026-10-05") == 1


def test_empty_rooms_returns_zero(tmp_store):
    assert tmp_store.save_rooms("泰达", [], 1, "2026-10-05") == 0
    assert tmp_store.save_rooms("泰达", [Room("9号楼", "")], 1, "2026-10-05") == 0


def test_accepts_dict_style_rooms(tmp_store):
    rooms = [{"building_name": "9号楼", "classroom_name": "9-101"}]
    assert tmp_store.save_rooms("泰达", rooms, 1, "2026-10-05") == 1


def test_clear_date(tmp_store):
    tmp_store.save_rooms("泰达", [Room("9号楼", "9-101")], 1, "2026-10-05")
    tmp_store.save_rooms("泰达", [Room("9号楼", "9-101")], 1, "2026-10-06")
    tmp_store.clear_date("2026-10-05")
    assert tmp_store.count_date("2026-10-05") == 0
    assert tmp_store.count_date("2026-10-06") == 1


def test_clear_before_keeps_future(tmp_store):
    tmp_store.save_rooms("泰达", [Room("9号楼", "9-101")], 1, "2026-09-01")
    tmp_store.save_rooms("泰达", [Room("9号楼", "9-101")], 1, "2026-10-05")
    tmp_store.save_rooms("泰达", [Room("9号楼", "9-101")], 1, "2026-11-01")
    removed = tmp_store.clear_before("2026-10-01")
    assert removed == 1
    assert tmp_store.distinct_dates() == ["2026-10-05", "2026-11-01"]


def test_distinct_queries(tmp_store):
    tmp_store.save_rooms("泰达", [Room("9号楼", "9-101"), Room("3号楼", "3-201")], 1, "2026-10-05")
    tmp_store.save_rooms("河西", [Room("A楼", "A-301")], 2, "2026-10-06")
    assert tmp_store.distinct_campuses() == ["河西", "泰达"]
    assert tmp_store.distinct_buildings("泰达") == ["3号楼", "9号楼"]
    assert tmp_store.distinct_dates() == ["2026-10-05", "2026-10-06"]
    assert tmp_store.total_rows() == 3


def test_iter_day_rows_and_rooms(tmp_store):
    tmp_store.save_rooms("泰达", [Room("9号楼", "9-101")], 1, "2026-10-05")
    tmp_store.save_rooms("泰达", [Room("9号楼", "9-101")], 3, "2026-10-05")
    rows = tmp_store.iter_day_rows("2026-10-05")
    assert [r["period"] for r in rows] == [1, 3]
    assert len(tmp_store.iter_distinct_rooms()) == 1


def test_schema_matches_legacy(tmp_store):
    """老版本数据库升级后必须能直接用：表名、列名一个都不能改"""
    with tmp_store._connect() as conn:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(free_rooms)")]
    assert cols == ["id", "campus_name", "building_name", "classroom_name",
                    "period", "date", "scraped_at"]


def test_db_path_helpers():
    assert default_db_path("/root", "nku").endswith("data\\nku.db") or \
        default_db_path("/root", "nku").endswith("data/nku.db")
    assert legacy_db_path("/root").replace("\\", "/").endswith("data/classrooms.db")
