"""学校适配器协议 + 契约校验

一个学校 = 一个适配器。适配器只负责回答五个问题：

    1. 你们学校教务系统在哪个网址？（SchoolProfile）
    2. 有几个校区？分别叫什么？（list_campuses）
    3. 某个校区有几栋楼？（list_buildings）
    4. 我想查某栋楼，怎么告诉系统？（select_building）
    5. 第 N 节课、第 M 天，哪些教室是空的？（list_free_rooms）

框架负责剩下的全部：翻日期、翻楼、翻节次、去重入库、导出静态站。

⚠ 适配器**不许**引入 playwright。框架会把一个已登录的浏览器页面对象
（duck typing，只要有 .evaluate / .url / .goto 即可）传进来，适配器只管
在这个页面里发请求、解析结果。这样适配器可以脱离浏览器做单元测试。
"""
from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from typing import Any, Dict, List

from .model import Building, Campus, Room, SchoolProfile


class BrowserSpec:
    """浏览器规格：告诉框架「用哪个浏览器、用哪个专用目录」去复用登录态

    新版 Edge（Chromium 136+）不允许给「默认用户目录」开调试端口，所以
    每所学校用一个独立的 profile 目录，首次在该窗口登录一次，之后长期复用。
    """

    def __init__(
        self,
        exe_path: str,
        profile_dir: str,
        debug_port: int = 9222,
        login_url: str = "",
        browser_name: str = "浏览器",
    ) -> None:
        self.exe_path = exe_path
        self.profile_dir = profile_dir
        self.debug_port = debug_port
        self.login_url = login_url or ""
        self.browser_name = browser_name

    @property
    def cdp_endpoint(self) -> str:
        """CDP 地址（明确用 IPv4 回环，避免 localhost 被解析成 ::1 连不上）"""
        return f"http://127.0.0.1:{self.debug_port}"

    def describe(self) -> str:
        return (
            f"{self.browser_name} | exe={self.exe_path} | "
            f"profile={self.profile_dir} | port={self.debug_port}"
        )


class SchoolAdapter(ABC):
    """学校适配器抽象基类 —— 新增学校时继承它并实现全部抽象方法"""

    # ── 静态信息 ──
    @property
    @abstractmethod
    def profile(self) -> SchoolProfile:
        """学校画像（网址、节次、默认校区等）"""

    @property
    def browser(self) -> BrowserSpec:
        """浏览器规格。默认用系统 Edge + 本学校专属 profile 目录。"""
        import os

        return BrowserSpec(
            exe_path=r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            profile_dir=os.path.expandvars(
                rf"%LOCALAPPDATA%\campusfree\{self.profile.school_id}-profile"
            ),
            login_url=self.profile.base_url,
            browser_name="Microsoft Edge",
        )

    # ── 登录态判定 ──
    @property
    def login_markers(self) -> List[str]:
        """URL 里出现这些关键词 = 被踢到登录页 = 登录态失效"""
        return ["authserver", "login", "cas"]

    def is_logged_in(self, page: Any) -> bool:
        """判断当前页面是否已登录（默认实现：看 URL 有没有登录页特征）"""
        url = (getattr(page, "url", "") or "").lower()
        return not any(m in url for m in self.login_markers)

    def login_hint(self) -> str:
        """登录态失效时给用户的提示语"""
        return f"请先在浏览器中登录教务系统：{self.profile.base_url}"

    # ── 四个必须实现的数据动作 ──
    @abstractmethod
    def list_campuses(self, page: Any) -> List[Campus]:
        """列出所有校区"""

    @abstractmethod
    def list_buildings(self, page: Any, campus: Campus) -> List[Building]:
        """列出某校区的教学楼"""

    @abstractmethod
    def select_building(self, page: Any, campus: Campus, building: Building) -> bool:
        """把查询上下文切到某栋楼（返回是否成功）"""

    @abstractmethod
    def list_free_rooms(self, page: Any, period: int, day_offset: int) -> List[Room]:
        """查询「第 period 节、距今天 day_offset 天」的空闲教室"""

    # ── 可选钩子 ──
    def fallback_campuses(self, page: Any) -> List[Campus]:
        """校区接口挂了时的兜底方案（默认：没有兜底，返回空）"""
        return []

    def normalize_room_name(self, name: str) -> str:
        """教室名清洗钩子（默认：去掉空白字符）"""
        return "".join(name.split()) if name else name


# ── 契约校验 ──

_REQUIRED_METHODS = ("list_campuses", "list_buildings", "select_building", "list_free_rooms")


def validate_adapter(adapter: Any) -> List[str]:
    """校验一个适配器是否合格，返回问题清单（空列表 = 合格）

    为什么要这个：写适配器的人（可能是第一次接触本项目的校外同学）
    最容易漏实现某个方法，运行时才炸。这里把错误提前到「自检命令」，
    一条 `python -m campusfree check --school xxx` 就能把问题说清楚。
    """
    problems: List[str] = []

    if not isinstance(adapter, SchoolAdapter):
        problems.append("适配器必须继承 campusfree.adapter.SchoolAdapter")

    # 抽象方法是否真的实现（防「继承了但没写完」）
    for name in _REQUIRED_METHODS:
        func = getattr(adapter, name, None)
        if func is None:
            problems.append(f"缺少方法 {name}()")
            continue
        if getattr(func, "__isabstractmethod__", False):
            problems.append(f"方法 {name}() 是抽象方法，必须在子类中实现")

    # profile 基本检查
    try:
        prof = adapter.profile
    except Exception as exc:  # pragma: no cover - 只在适配器写错时触发
        problems.append(f"profile 属性读取失败：{exc}")
        return problems

    if not isinstance(prof, SchoolProfile):
        problems.append("profile 必须返回 SchoolProfile 实例")
        return problems

    if not prof.school_id or not prof.school_id.isascii():
        problems.append("profile.school_id 必须是非空英文短名（CLI 用它做 --school 参数）")
    if not prof.school_name:
        problems.append("profile.school_name 不能为空")
    if not prof.base_url.startswith(("http://", "https://")):
        problems.append(f"profile.base_url 必须是完整网址（含 http/https），当前={prof.base_url!r}")
    if not prof.periods:
        problems.append("profile.periods 不能为空（至少要有 1 个节次）")
    else:
        bad = [n for n in prof.periods if not isinstance(n, int) or n < 1]
        if bad:
            problems.append(f"profile.periods 的 key 必须是 >=1 的整数，异常：{bad}")
        empty_range = [n for n, t in prof.periods.items() if not str(t).strip()]
        if empty_range:
            problems.append(f"以下节次没有填写时间：{empty_range}")

    # default_campus 与 campus_order 的合理性
    if prof.default_campus and prof.campus_order:
        if prof.default_campus not in prof.campus_order:
            problems.append(
                f"default_campus={prof.default_campus!r} 不在 campus_order={prof.campus_order} 中"
            )

    # browser 规格
    try:
        spec = adapter.browser
        if not isinstance(spec, BrowserSpec):
            problems.append("browser 属性必须返回 BrowserSpec 实例")
        elif not spec.exe_path:
            problems.append("browser.exe_path 不能为空")
    except Exception as exc:  # pragma: no cover
        problems.append(f"browser 属性读取失败：{exc}")

    return problems


def adapter_signature(adapter: Any) -> Dict[str, Any]:
    """返回适配器的自检摘要（给 CLI 打印 / 测试断言用）"""
    prof = adapter.profile
    return {
        "school_id": prof.school_id,
        "school_name": prof.school_name,
        "base_url": prof.base_url,
        "entry_url": prof.entry_url(),
        "period_count": len(prof.periods),
        "default_campus": prof.default_campus,
        "campus_order": list(prof.campus_order),
        "methods": {m: callable(getattr(adapter, m, None)) for m in _REQUIRED_METHODS},
        "browser": adapter.browser.describe(),
    }


def adapter_source_lines(adapter_cls: type) -> int:
    """适配器类的源码行数（用于判断「接入成本高不高」，仅统计参考）"""
    try:
        return len(inspect.getsource(adapter_cls).splitlines())
    except Exception:  # pragma: no cover
        return 0
