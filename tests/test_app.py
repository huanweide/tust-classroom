"""Flask 本地 API 测试

为什么值得测：这些接口的手写 SQL 拼装（尤其是搜索的 UNION 分支、
start>end 的区间翻转）是最容易悄悄出错又没人发现的地方。
"""
import pytest

import app as app_module
from campusfree.model import Room
from campusfree.store import RoomStore


@pytest.fixture
def client(tmp_path, monkeypatch):
    db = tmp_path / "api.db"
    store = RoomStore(str(db))
    store.save_rooms("泰达", [Room("9号楼", "9-101"), Room("9号楼", "9-102")], 1, "2026-10-05")
    store.save_rooms("泰达", [Room("9号楼", "9-101")], 2, "2026-10-05")
    store.save_rooms("泰达", [Room("3号楼", "3阶梯(d)")], 1, "2026-10-05")
    store.save_rooms("河西", [Room("A楼", "A-301")], 3, "2026-10-06")
    monkeypatch.setattr(app_module, "DB_PATH", str(db))
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def test_api_campuses(client):
    assert client.get("/api/campuses").get_json() == ["河西", "泰达"]


def test_api_buildings(client):
    got = client.get("/api/buildings?campus=泰达").get_json()
    assert got == ["3号楼", "9号楼"]


def test_api_periods_has_13(client):
    got = client.get("/api/periods").get_json()
    assert len(got) == 13
    assert got[0] == {"period": 1, "time_range": "08:20-09:05"}
    # 字段名必须与 /api/free-rooms 一致，否则前端两套写法
    assert all("time_range" in g and "time" not in g for g in got)


def test_api_dates_newest_first(client):
    """/api/dates 是 DESC 取最近 7 天"""
    assert client.get("/api/dates").get_json() == ["2026-10-06", "2026-10-05"]


def test_api_free_rooms_filter(client):
    got = client.get("/api/free-rooms?date=2026-10-05&period=1&campus=泰达").get_json()
    names = sorted(r["classroom_name"] for r in got)
    assert names == ["3阶梯(d)", "9-101", "9-102"]
    assert all(r["time_range"] for r in got)


def test_api_free_rooms_bad_period(client):
    resp = client.get("/api/free-rooms?date=2026-10-05&period=abc")
    assert resp.status_code == 400
    assert "整数" in resp.get_json()["error"]


def test_search_exact(client):
    got = client.get("/api/classrooms/search?q=9-101").get_json()
    assert got[0]["classroom_name"] == "9-101"
    assert got[0]["full_name"] == "9号楼9-101"


def test_search_smart_decompose(client):
    """9-3 这种「楼号-房号」简写要能拆开匹配"""
    got = client.get("/api/classrooms/search?q=9-1&campus=泰达").get_json()
    names = {r["classroom_name"] for r in got}
    assert "9-101" in names and "9-102" in names


def test_search_empty_query(client):
    assert client.get("/api/classrooms/search?q=").get_json() == []


def test_search_limit(client):
    got = client.get("/api/classrooms/search?q=9&limit=1").get_json()
    assert len(got) == 1


def test_classroom_slots(client):
    got = client.get("/api/classroom/9-101/slots?date=2026-10-05&campus=泰达").get_json()
    assert got["free_count"] == 2
    assert got["total_periods"] == 13
    assert [p["period"] for p in got["free_periods"]] == [1, 2]


def test_classroom_slots_missing_date(client):
    resp = client.get("/api/classroom/9-101/slots")
    assert resp.status_code == 400


def test_classroom_slots_unknown_room_suggests(client):
    # 9-10 不是完整教室名（真名是 9-101），应给出「你是不是要找 9-101」
    resp = client.get("/api/classroom/9-10/slots?date=2026-10-05&campus=泰达")
    assert resp.status_code == 404
    suggestions = resp.get_json()["suggestions"]
    assert any("9-101" in s["classroom_name"] for s in suggestions)


def test_classroom_slots_date_without_data(client):
    resp = client.get("/api/classroom/9-101/slots?date=2099-01-01&campus=泰达")
    assert resp.status_code == 404
    assert "暂无爬取数据" in resp.get_json()["error"]


def test_range_finds_continuous_free(client):
    """9-101 在第 1、2 节都空 → 查 1-2 区间应命中"""
    got = client.get(
        "/api/free-classrooms-in-range?date=2026-10-05&start_period=1&end_period=2&campus=泰达"
    ).get_json()
    assert [r["classroom_name"] for r in got] == ["9-101"]


def test_range_swaps_reversed_periods(client):
    """start>end 时要自动交换，否则会静默返回空（老版本踩过的坑）"""
    got = client.get(
        "/api/free-classrooms-in-range?date=2026-10-05&start_period=2&end_period=1&campus=泰达"
    ).get_json()
    assert [r["classroom_name"] for r in got] == ["9-101"]


def test_range_bad_period(client):
    resp = client.get("/api/free-classrooms-in-range?date=2026-10-05&start_period=x")
    assert resp.status_code == 400


def test_index_route(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "空闲教室" in resp.get_data(as_text=True)
