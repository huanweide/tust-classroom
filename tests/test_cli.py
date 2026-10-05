"""CLI 测试：命令能不能跑、报错是不是人话"""
import pytest

from campusfree import cli


def test_schools_lists_tust(capsys):
    class A:
        school = None

    rc = cli.cmd_schools(A())
    out = capsys.readouterr().out
    assert rc == 0
    assert "tust" in out and "天津科技大学" in out


def test_check_passes_for_tust(capsys):
    class A:
        school = "tust"

    assert cli.cmd_check(A()) == 0
    assert "合格" in capsys.readouterr().out


def test_check_reports_unknown_school(capsys):
    class A:
        school = "nope"

    assert cli.cmd_check(A()) == 2
    assert "找不到学校适配器" in capsys.readouterr().out


def test_export_writes_files(tmp_path, capsys):
    """export 子命令要真的产出 JSON"""
    from campusfree.store import RoomStore

    db = tmp_path / "db" / "t.db"
    store = RoomStore(str(db))
    from campusfree.model import Room
    store.save_rooms("泰达", [Room("9号楼", "9-101")], 1, "2026-10-05")

    import campusfree.cli as c
    root_backup = c.ROOT
    c.ROOT = str(tmp_path)
    try:
        class A:
            school = "tust"
            out = str(tmp_path / "out")
            quiet = True
        assert c.cmd_export(A()) == 0
        assert (tmp_path / "out" / "index.json").exists()
    finally:
        c.ROOT = root_backup


def test_run_rejects_bad_range(capsys):
    class A:
        school = "tust"
        range = "6-0"
        auto = False
        dayoffset = 1
        clear_old = False
        gap = 0.0
        max_days = 130
        stop_threshold = 14

    assert cli.cmd_run(A()) == 2
    assert "--range" in capsys.readouterr().err
