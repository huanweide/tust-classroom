"""天津科技大学（TUST）适配器 —— 本框架的第一个官方适配器

数据来源：TUST URP 教务系统「空闲教室」模块。
接口形状（F12 抓包得到，换学校时照这个思路自己抓一遍）：

    POST /student/teachingResources/freeClassroom/queryCodeCampusList
         → [{id: "02", text: "泰达"}, ...]                  校区列表
    POST /student/teachingResources/freeClassroom/queryCodeTeaBuildingList
         参数 xqh=校区编码
         → [{id: {teachingBuildingNumber}, teachingBuildingName}]  楼列表
    POST /student/teachingResources/freeClassroom/today
         参数 position=校区_楼, xqm=校区名                   切换查询上下文
    POST /student/teachingResources/freeClassroom/today/{节次}
         参数 dayplus=距今天数
         → {spareroomObjList: [{acmcBuildingName, claroom:[{classroom}]}]}

⚠ 关于 profile 目录：这里刻意沿用老路径
   %LOCALAPPDATA%\\tust-classroom\\edge-cdp-profile，
   这样老用户升级后不用重新登录一次。
"""
from __future__ import annotations

import os
import re
from typing import Any, List

from campusfree.adapter import BrowserSpec, SchoolAdapter
from campusfree.model import (
    Building,
    Campus,
    Room,
    SchoolProfile,
    periods_from_list,
)

BASE_URL = "http://jwxtxs.tust.edu.cn:46110"

# TUST 13 节次时间表
PERIODS = periods_from_list([
    (1, "08:20-09:05"), (2, "09:15-10:00"), (3, "10:20-11:05"),
    (4, "11:15-12:00"), (5, "13:30-14:15"), (6, "14:25-15:10"),
    (7, "15:25-16:10"), (8, "16:20-17:05"), (9, "17:15-18:00"),
    (10, "18:30-19:15"), (11, "19:25-20:10"), (12, "20:25-21:10"),
    (13, "21:20-22:05"),
])

# 校区编码 → 名字（接口挂掉时的兜底，也是老版本试探法的固化）
CAMPUS_FALLBACK = [("02", "泰达"), ("01", "河西")]


class TustAdapter(SchoolAdapter):
    """天津科技大学空闲教室适配器"""

    @property
    def profile(self) -> SchoolProfile:
        return SchoolProfile(
            school_id="tust",
            school_name="天津科技大学",
            base_url=BASE_URL,
            periods=PERIODS,
            entry_path="/student/teachingResources/freeClassroom/index",
            default_campus="泰达",
            campus_order=["泰达", "河西"],
            source_note="数据来源：天津科技大学 URP 教务系统（非官方工具）",
        )

    @property
    def browser(self) -> BrowserSpec:
        # 沿用老 profile 目录：老用户升级后登录态不丢
        legacy = os.path.expandvars(r"%LOCALAPPDATA%\tust-classroom\edge-cdp-profile")
        return BrowserSpec(
            exe_path=r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            profile_dir=legacy,
            debug_port=9222,
            login_url=BASE_URL,
            browser_name="Microsoft Edge",
        )

    @property
    def login_markers(self) -> List[str]:
        return ["authserver", "login"]

    def login_hint(self) -> str:
        return f"Edge 未登录 URP，请在该浏览器窗口登录一次教务系统：{BASE_URL}"

    # ── 校区 ──

    def list_campuses(self, page: Any) -> List[Campus]:
        result = page.evaluate("""
            async () => {
                const resp = await fetch('/student/teachingResources/freeClassroom/queryCodeCampusList', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                });
                if (!resp.ok) return [];
                return await resp.json();
            }
        """)
        campuses: List[Campus] = []
        for item in result or []:
            code = item.get("id") or item.get("code") or item.get("xqh", "")
            name = item.get("text") or item.get("name") or item.get("xqmc", "")
            name = re.sub(r"[\s\r\n]+", "", str(name or ""))
            if code and name:
                campuses.append(Campus(code=str(code), name=str(name)))
        return campuses

    def fallback_campuses(self, page: Any) -> List[Campus]:
        """接口拿不到时，逐个试探校区编码：能列出楼的编码就是真校区"""
        found: List[Campus] = []
        for code, name in CAMPUS_FALLBACK:
            try:
                if self.list_buildings(page, Campus(code=code, name=name)):
                    found.append(Campus(code=code, name=name))
            except Exception:
                continue
        return found

    # ── 教学楼 ──

    def list_buildings(self, page: Any, campus: Campus) -> List[Building]:
        result = page.evaluate(
            """async (campus_code) => {
                const formData = new URLSearchParams();
                formData.append('xqh', campus_code);
                const resp = await fetch('/student/teachingResources/freeClassroom/queryCodeTeaBuildingList', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                    body: formData.toString()
                });
                if (!resp.ok) return [];
                return await resp.json();
            }""",
            campus.code,
        )
        buildings: List[Building] = []
        for item in result or []:
            inner = item.get("id", item) if isinstance(item, dict) else item
            code = (inner or {}).get("teachingBuildingNumber", "") if isinstance(inner, dict) else ""
            name = item.get("teachingBuildingName", "") if isinstance(item, dict) else ""
            name = re.sub(r"[\s\r\n]+", "", str(name or ""))
            if code and name:
                buildings.append(Building(code=str(code), name=str(name)))
        return buildings

    # ── 切换教学楼 ──

    def select_building(self, page: Any, campus: Campus, building: Building) -> bool:
        """URP 要求 position = 「校区编码_楼编码」，xqm = 校区中文名"""
        try:
            return bool(page.evaluate(
                """async (args) => {
                    const formData = new URLSearchParams();
                    formData.append('position', args.position);
                    formData.append('xqm', args.xqm);
                    const resp = await fetch('/student/teachingResources/freeClassroom/today', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                        body: formData.toString()
                    });
                    return resp.ok;
                }""",
                {"position": f"{campus.code}_{building.code}", "xqm": campus.name},
            ))
        except Exception:
            return False

    # ── 空闲教室 ──

    def list_free_rooms(self, page: Any, period: int, day_offset: int) -> List[Room]:
        result = page.evaluate(
            """async (args) => {
                try {
                    const resp = await fetch(
                        '/student/teachingResources/freeClassroom/today/' + args.period,
                        {
                            method: 'POST',
                            headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                            body: 'dayplus=' + args.dayoffset
                        }
                    );
                    if (!resp.ok) return {error: 'HTTP ' + resp.status};
                    return await resp.json();
                } catch (e) {
                    return {error: e.message};
                }
            }""",
            {"period": period, "dayoffset": day_offset},
        )

        if not isinstance(result, dict):
            return []
        if "error" in result:
            return []

        rooms: List[Room] = []
        for building in result.get("spareroomObjList", []) or []:
            bname = building.get("acmcBuildingName", "")
            for room in building.get("claroom", []) or []:
                name = self.normalize_room_name(room.get("classroom", ""))
                if name:
                    rooms.append(Room(building_name=bname, classroom_name=name))
        return rooms


ADAPTER = TustAdapter
