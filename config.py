"""TUST 配置 —— 兼容层（v2 起改由 adapters/tust.py 提供真值）

为什么还留这个文件：
    项目从「单校脚本」升级成「多校框架」后，原先散落在 config.py 里的
    TUST 常量统一搬到了 adapters/tust.py。但作者本机的 Windows 任务计划、
    auto_update.bat、以及第三方二次开发代码可能还在 import 这些名字，
    所以这里保留一份「只读视图」，值全部从适配器派生，不repeat定义。

⚠ 不要在这个文件里新增学校专属常量 —— 请改 adapters/tust.py。
"""
import os

from adapters.tust import BASE_URL, PERIODS  # 单一真值来源

# ── 教务系统 ──
BASE_URL = BASE_URL
LOGIN_PAGE = f"{BASE_URL}/"
CAMPUS_LIST_API = f"{BASE_URL}/student/teachingResources/freeClassroom/queryCodeCampusList"
BUILDING_LIST_API = f"{BASE_URL}/student/teachingResources/freeClassroom/queryCodeTeaBuildingList"
FREE_ROOM_API = f"{BASE_URL}/student/teachingResources/freeClassroom/today"  # 后面拼 /{节次}

# ── 登录凭证（环境变量，绝不硬编码）──
STUDENT_ID = os.environ.get("TUST_SID", "")
PASSWORD = os.environ.get("TUST_PWD", "")

# ── 目标校区（None = 自动发现全部校区）──
CAMPUS_CODE = None
CAMPUS_NAME = None

# ── 节次时间表（13 节）──
PERIODS = PERIODS

# ── SQLite 路径 ──
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "classrooms.db")
