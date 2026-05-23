"""TUST 教务系统空闲教室查询 — 配置文件"""
import os

# ── 教务系统 ──
BASE_URL = "http://jwxtxs.tust.edu.cn:46110"
LOGIN_PAGE = f"{BASE_URL}/"
CAMPUS_LIST_API = f"{BASE_URL}/student/teachingResources/freeClassroom/queryCodeCampusList"
BUILDING_LIST_API = f"{BASE_URL}/student/teachingResources/freeClassroom/queryCodeTeaBuildingList"
FREE_ROOM_API = f"{BASE_URL}/student/teachingResources/freeClassroom/today"  # 后面拼 /{节次}

# ── 登录凭证（环境变量，绝不硬编码）──
STUDENT_ID = os.environ.get("TUST_SID", "")
PASSWORD = os.environ.get("TUST_PWD", "")

# ── 目标校区 ──
CAMPUS_CODE = "02"  # 泰达校区
CAMPUS_NAME = "泰达"

# ── 节次时间表（13节）──
PERIODS = {
    1:  "08:20-09:05", 2:  "09:15-10:00", 3:  "10:20-11:05",
    4:  "11:15-12:00", 5:  "13:30-14:15", 6:  "14:25-15:10",
    7:  "15:25-16:10", 8:  "16:20-17:05", 9:  "17:15-18:00",
    10: "18:30-19:15", 11: "19:25-20:10", 12: "20:25-21:10",
    13: "21:20-22:05"
}

# ── SQLite 路径 ──
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "classrooms.db")
