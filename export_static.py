"""SQLite → 静态 JSON 导出 —— 兼容入口（v2 起内部改为调用 campusfree 框架）

老用法不变（auto_update.bat 照跑）：
    python export_static.py

新用法（支持任意学校）：
    python -m campusfree export --school tust

产出：
    static/data/index.json        元数据（校区/日期/教学楼/节次/更新时间）
    static/data/YYYY-MM-DD.json   当天数据（按校区→楼→教室→节次数组压缩）
    static/data/search.json       教室名搜索索引
"""
import os
import sys

import config
from campusfree.exporter import StaticExporter
from campusfree.registry import get_adapter
from campusfree.store import RoomStore

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "data")


def export(school_id: str = "tust", out_dir: str = None) -> dict:
    """导出静态 JSON，返回统计字典"""
    adapter = get_adapter(school_id)
    store = RoomStore(config.DB_PATH if school_id == "tust"
                      else os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                        "data", f"{school_id}.db"))
    return StaticExporter(store, adapter.profile, out_dir or OUT_DIR).export(verbose=True)


if __name__ == "__main__":
    try:
        export()
    except Exception as e:
        print(f"[FATAL] 导出失败: {e}", file=sys.stderr)
        sys.exit(1)
