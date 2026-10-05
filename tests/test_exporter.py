"""静态导出测试：产物结构、默认校区顺序、日期压缩格式"""
import json
import os
from datetime import datetime

from campusfree.exporter import StaticExporter
from campusfree.model import Room


def _seed(store):
    store.save_rooms("河西", [Room("A楼", "A-301")], 1, "2026-10-05")
    store.save_rooms("泰达", [Room("9号楼", "9-101"), Room("9号楼", "9-102")], 1, "2026-10-05")
    store.save_rooms("泰达", [Room("9号楼", "9-101")], 2, "2026-10-05")
    store.save_rooms("泰达", [Room("3号楼", "3-201")], 5, "2026-10-06")


def test_export_creates_expected_files(tmp_store, tust_adapter, tmp_path):
    _seed(tmp_store)
    out = str(tmp_path / "static" / "data")
    StaticExporter(tmp_store, tust_adapter.profile, out).export(verbose=False)

    for name in ("index.json", "2026-10-05.json", "2026-10-06.json", "search.json"):
        assert os.path.exists(os.path.join(out, name)), f"缺少产物 {name}"


def test_campus_order_puts_default_first(tmp_store, tust_adapter, tmp_path):
    """前端默认展示泰达 —— 数据库按名字排是河西在前，必须靠 campus_order 纠正"""
    _seed(tmp_store)
    out = str(tmp_path / "d")
    StaticExporter(tmp_store, tust_adapter.profile, out).export(verbose=False)
    index = json.load(open(os.path.join(out, "index.json"), encoding="utf-8"))
    assert index["campuses"][0] == "泰达"
    assert index["default_campus"] == "泰达"


def test_day_file_compresses_periods(tmp_store, tust_adapter, tmp_path):
    _seed(tmp_store)
    out = str(tmp_path / "d")
    StaticExporter(tmp_store, tust_adapter.profile, out).export(verbose=False)
    day = json.load(open(os.path.join(out, "2026-10-05.json"), encoding="utf-8"))
    # 9-101 在第 1、2 节都空 → 合并成 [1, 2]，而不是两条记录
    assert day["泰达"]["9号楼"]["9-101"] == [1, 2]
    assert day["泰达"]["9号楼"]["9-102"] == [1]


def test_index_semantics(tmp_store, tust_adapter, tmp_path):
    """updated 是「数据覆盖的最后一天」，不是抓取时间 —— 这个坑踩过一次"""
    _seed(tmp_store)
    out = str(tmp_path / "d")
    StaticExporter(tmp_store, tust_adapter.profile, out).export(verbose=False)
    index = json.load(open(os.path.join(out, "index.json"), encoding="utf-8"))
    assert index["updated"] == "2026-10-06"
    assert index["dates"] == ["2026-10-05", "2026-10-06"]
    assert index["periods"]["13"] == "21:20-22:05"
    assert index["school"] == "天津科技大学"
    # generated_at 必须是可解析的时间戳
    datetime.fromisoformat(index["generated_at"])


def test_search_index_shape(tmp_store, tust_adapter, tmp_path):
    _seed(tmp_store)
    out = str(tmp_path / "d")
    StaticExporter(tmp_store, tust_adapter.profile, out).export(verbose=False)
    search = json.load(open(os.path.join(out, "search.json"), encoding="utf-8"))
    assert {"c", "b", "r"} <= set(search[0])
    assert len(search) == 4


def test_export_clears_stale_files(tmp_store, tust_adapter, tmp_path):
    """重新导出时，上一次留下的过期日期文件必须被清掉"""
    out = tmp_path / "d"
    out.mkdir()
    (out / "1999-01-01.json").write_text("{}", encoding="utf-8")
    _seed(tmp_store)
    StaticExporter(tmp_store, tust_adapter.profile, str(out)).export(verbose=False)
    assert not (out / "1999-01-01.json").exists()


def test_export_empty_db_does_not_crash(tmp_store, tust_adapter, tmp_path):
    out = str(tmp_path / "d")
    stats = StaticExporter(tmp_store, tust_adapter.profile, out).export(verbose=False)
    assert stats["dates"] == 0
    index = json.load(open(os.path.join(out, "index.json"), encoding="utf-8"))
    assert index["updated"] == ""
