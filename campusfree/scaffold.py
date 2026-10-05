"""新学校脚手架生成器 —— 一条命令产出可运行的适配器骨架

为什么要这个：接入新学校最大的心理门槛是「不知道从哪下手」。
生成一个能直接通过 check 的骨架，把 4 个方法摆在眼前，
接入就从「读完整项目源码」变成「填空」。

实现说明：模板里全是 JS 花括号，所以刻意不用 str.format()（会和 JS 的
{} 打架），改用 __占位符__ + replace 替换。
"""
from __future__ import annotations

import os
import re

TEMPLATE = '''"""适配器骨架：__SCHOOL_NAME__（__SCHOOL_ID__）

本文件由 `python -m campusfree new-school __SCHOOL_ID__` 自动生成。
你只需要改「TODO」标出来的地方，其余不用动。

四个方法分别回答：
    list_campuses    你们学校有几个校区？
    list_buildings   某个校区有几栋楼？
    select_building  怎么把查询上下文切到某栋楼？
    list_free_rooms  第 N 节课、第 M 天，哪些教室是空的？

调试技巧：在浏览器里手动操作一遍，打开 F12 → Network，
看系统发了什么请求、返回什么 JSON，把请求抄进 evaluate 里即可。
"""
from __future__ import annotations

import re
from typing import Any, List

from campusfree.adapter import BrowserSpec, SchoolAdapter
from campusfree.model import Building, Campus, Room, SchoolProfile, periods_from_list

# TODO 1/5：改成你们学校教务系统的根地址（务必含 http:// 或 https://）
BASE_URL = "https://jw.example.edu.cn"

# TODO 2/5：改成你们学校的节次时间表（第几节课 : 起止时间）
PERIODS = periods_from_list([
    (1, "08:00-08:45"), (2, "08:55-09:40"), (3, "10:00-10:45"),
    (4, "10:55-11:40"), (5, "14:00-14:45"), (6, "14:55-15:40"),
    (7, "16:00-16:45"), (8, "16:55-17:40"), (9, "19:00-19:45"),
])


class __CLASS_NAME__Adapter(SchoolAdapter):
    """__SCHOOL_NAME__ 空闲教室适配器"""

    @property
    def profile(self) -> SchoolProfile:
        return SchoolProfile(
            school_id="__SCHOOL_ID__",
            school_name="__SCHOOL_NAME__",
            base_url=BASE_URL,
            periods=PERIODS,
            # TODO 3/5：空闲教室页的相对路径（从教务系统根地址后面那段）
            entry_path="/student/teachingResources/freeClassroom/index",
            # TODO 4/5：前端默认选中哪个校区（写中文名；没有多校区就留 None）
            default_campus=None,
            campus_order=[],
            source_note="数据来源：__SCHOOL_NAME__教务系统（非官方）",
        )

    @property
    def browser(self) -> BrowserSpec:
        import os

        return BrowserSpec(
            # TODO 5/5（可选）：换成你本机浏览器路径；Mac/Linux 同样支持
            exe_path=r"C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
            profile_dir=os.path.expandvars(
                r"%LOCALAPPDATA%\\campusfree\\__SCHOOL_ID__-profile"
            ),
            login_url=BASE_URL,
            browser_name="Microsoft Edge",
        )

    # ── 校区列表 ──

    def list_campuses(self, page: Any) -> List[Campus]:
        """示例：调用教务系统的校区下拉框接口

        真实写法请用 F12 抓包，把 URL / 参数 / 返回字段换成你们学校的。
        """
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
            code = str(item.get("id") or item.get("code") or "")
            name = re.sub(r"[\\s\\r\\n]+", "", str(item.get("text") or item.get("name") or ""))
            if code and name:
                campuses.append(Campus(code=code, name=name))
        return campuses

    def fallback_campuses(self, page: Any) -> List[Campus]:
        """校区接口挂了时的兜底：手工写死校区编码与名字"""
        # return [Campus(code="01", name="主校区")]
        return []

    # ── 教学楼列表 ──

    def list_buildings(self, page: Any, campus: Campus) -> List[Building]:
        result = page.evaluate(
            """async (code) => {
                const form = new URLSearchParams();
                form.append('xqh', code);
                const resp = await fetch('/student/teachingResources/freeClassroom/queryCodeTeaBuildingList', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                    body: form.toString()
                });
                if (!resp.ok) return [];
                return await resp.json();
            }""",
            campus.code,
        )
        buildings: List[Building] = []
        for item in result or []:
            code = str((item.get("id") or item).get("teachingBuildingNumber", ""))
            name = re.sub(r"[\\s\\r\\n]+", "", str(item.get("teachingBuildingName", "")))
            if code and name:
                buildings.append(Building(code=code, name=name))
        return buildings

    # ── 切换教学楼 ──

    def select_building(self, page: Any, campus: Campus, building: Building) -> bool:
        try:
            return bool(page.evaluate(
                """async (args) => {
                    const form = new URLSearchParams();
                    form.append('position', args.position);
                    form.append('xqm', args.xqm);
                    const resp = await fetch('/student/teachingResources/freeClassroom/today', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                        body: form.toString()
                    });
                    return resp.ok;
                }""",
                {
                    "position": f"{campus.code}_{building.code}",
                    "xqm": campus.name,
                },
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
                } catch (e) { return {error: e.message}; }
            }""",
            {"period": period, "dayoffset": day_offset},
        )
        if not isinstance(result, dict) or "error" in result:
            return []
        # TODO：这里的字段名（spareroomObjList / claroom / classroom）按你们学校返回改
        rooms: List[Room] = []
        for b in result.get("spareroomObjList", []) or []:
            bname = b.get("acmcBuildingName", "")
            for r in b.get("claroom", []) or []:
                name = self.normalize_room_name(r.get("classroom", ""))
                if name:
                    rooms.append(Room(building_name=bname, classroom_name=name))
        return rooms


ADAPTER = __CLASS_NAME__Adapter
'''


def _class_name(school_id: str) -> str:
    """nku → Nku；bei-you → BeiYou"""
    parts = re.split(r"[^a-zA-Z0-9]+", school_id)
    return "".join(p.capitalize() for p in parts if p) or "MySchool"


def render_template(school_id: str, school_name: str) -> str:
    """把模板渲染成可执行的适配器源码"""
    return (
        TEMPLATE
        .replace("__CLASS_NAME__", _class_name(school_id))
        .replace("__SCHOOL_ID__", school_id)
        .replace("__SCHOOL_NAME__", school_name)
    )


def create_adapter_scaffold(root: str, school_id: str, school_name: str = "") -> str:
    """在 adapters/ 下生成 <school_id>.py，返回文件路径"""
    sid = (school_id or "").strip().lower()
    if not sid or not sid.isascii() or not re.fullmatch(r"[a-z0-9_\-]+", sid):
        raise ValueError(
            f"school_id 只能用小写英文字母/数字/下划线/连字符，收到：{school_id!r}"
        )
    mod_name = sid.replace("-", "_")
    adapters_dir = os.path.join(root, "adapters")
    os.makedirs(adapters_dir, exist_ok=True)
    path = os.path.join(adapters_dir, f"{mod_name}.py")
    if os.path.exists(path):
        raise FileExistsError(f"适配器已存在，不覆盖：{path}")

    content = render_template(mod_name, school_name or f"{sid}（待填写中文名）")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path
