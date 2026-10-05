"""SQLite 存储层 —— 通用的「空闲教室」仓库

表结构刻意保持与老版本 100% 一致（free_rooms 表、索引、唯一约束都没变），
这样老用户升级后本地 data/classrooms.db 直接可用，不用重新爬一遍。
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from typing import Iterable, List, Sequence, Tuple

SCHEMA = """
CREATE TABLE IF NOT EXISTS free_rooms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campus_name TEXT NOT NULL,
    building_name TEXT NOT NULL,
    classroom_name TEXT NOT NULL,
    period INTEGER NOT NULL,
    date TEXT NOT NULL,
    scraped_at TEXT NOT NULL,
    UNIQUE(campus_name, building_name, classroom_name, period, date)
)
"""

INDEX = """
CREATE INDEX IF NOT EXISTS idx_free_rooms_query
ON free_rooms(campus_name, building_name, period, date)
"""


class RoomStore:
    """空闲教室仓库：负责建表、写入、清理、查询"""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        parent = os.path.dirname(db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(SCHEMA)
            conn.execute(INDEX)

    # ── 写入 ──

    def save_rooms(
        self,
        campus_name: str,
        rooms: Iterable,
        period: int,
        date_str: str,
    ) -> int:
        """批量写入某校某节次的空闲教室，返回写入条数

        rooms 里的元素只要有 building_name / classroom_name 两个属性即可
        （既接受 model.Room，也接受普通字典风格的简单对象）。
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rows: List[Tuple[str, str, str, int, str, str]] = []
        for r in rooms:
            if isinstance(r, dict):
                bname = r.get("building_name", "")
                cname = r.get("classroom_name", "")
            else:
                bname = getattr(r, "building_name", "")
                cname = getattr(r, "classroom_name", "")
            if not cname:
                continue
            rows.append((campus_name, bname, cname, period, date_str, now))

        if not rows:
            return 0
        with self._connect() as conn:
            conn.executemany(
                "INSERT OR IGNORE INTO free_rooms "
                "(campus_name, building_name, classroom_name, period, date, scraped_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                rows,
            )
        return len(rows)

    # ── 清理 ──

    def clear_date(self, date_str: str) -> None:
        """清空某一天的数据（重爬前用）"""
        with self._connect() as conn:
            conn.execute("DELETE FROM free_rooms WHERE date = ?", (date_str,))

    def clear_before(self, date_str: str) -> int:
        """清空某天之前的所有数据（换学期时用），返回删除条数"""
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM free_rooms WHERE date < ?", (date_str,))
            return cur.rowcount or 0

    def count_date(self, date_str: str) -> int:
        """某天已有多少条记录（用于断点续传判断）"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM free_rooms WHERE date = ?", (date_str,)
            ).fetchone()
            return row[0] if row else 0

    # ── 查询 ──

    def distinct_campuses(self) -> List[str]:
        with self._connect() as conn:
            return [r[0] for r in conn.execute(
                "SELECT DISTINCT campus_name FROM free_rooms ORDER BY campus_name"
            )]

    def distinct_dates(self) -> List[str]:
        with self._connect() as conn:
            return [r[0] for r in conn.execute(
                "SELECT DISTINCT date FROM free_rooms ORDER BY date"
            )]

    def distinct_buildings(self, campus_name: str) -> List[str]:
        with self._connect() as conn:
            return [r[0] for r in conn.execute(
                "SELECT DISTINCT building_name FROM free_rooms "
                "WHERE campus_name = ? ORDER BY building_name",
                (campus_name,),
            )]

    def total_rows(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) FROM free_rooms").fetchone()
            return row[0] if row else 0

    def iter_day_rows(self, date_str: str) -> Sequence[sqlite3.Row]:
        """取某天的全部记录（导出用），返回 Row 序列"""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(
                "SELECT campus_name, building_name, classroom_name, period "
                "FROM free_rooms WHERE date = ? "
                "ORDER BY campus_name, building_name, classroom_name, period",
                (date_str,),
            ).fetchall()

    def iter_distinct_rooms(self) -> Sequence[sqlite3.Row]:
        """取全部「校区+楼+教室」组合（搜索索引用）"""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(
                "SELECT DISTINCT campus_name, building_name, classroom_name "
                "FROM free_rooms ORDER BY campus_name, building_name, classroom_name"
            ).fetchall()


def default_db_path(root: str, school_id: str = "") -> str:
    """默认数据库路径

    有 school_id 时用 data/<school_id>.db（多校互不干扰），
    没有时用老的 data/classrooms.db（向后兼容）。
    """
    name = f"{school_id}.db" if school_id else "classrooms.db"
    return os.path.join(root, "data", name)


def legacy_db_path(root: str) -> str:
    """老版本固定路径（兼容 shim 用）"""
    return os.path.join(root, "data", "classrooms.db")
