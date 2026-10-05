"""CampusFreeRoom —— 任意高校空闲教室查询接入框架

一句话说明：
    教务系统里明明有「哪些教室现在是空的」这份数据，但它藏在需要登录、
    只在校园网里、手机上看不了的网页深处。本框架把这份数据搬出来，
    变成手机浏览器随开随查、可离线、零后端的静态站。

一条流水线的五个环节：
    登录态复用 → 按校区/楼/节次翻数据 → 存 SQLite → 导出静态 JSON → Pages 发布

接入一所新学校 = 写一个适配器（4 个方法）。详见 docs/ADAPTER_GUIDE.md。
"""
from __future__ import annotations

__version__ = "2.0.0"

from .adapter import BrowserSpec, SchoolAdapter, validate_adapter  # noqa: F401
from .exporter import StaticExporter, export_static  # noqa: F401
from .model import (  # noqa: F401
    Building,
    Campus,
    Period,
    Room,
    SchoolProfile,
    periods_from_list,
)
from .registry import get_adapter, list_adapters  # noqa: F401
from .runner import CrawlRunner, RunOptions, RunReport, parse_range  # noqa: F401
from .store import RoomStore  # noqa: F401
