"""通用数据模型 —— 与具体学校无关的一层

为什么要有这一层：
    全国各高校教务系统长得完全不一样，但「空闲教室」这件事的数据形状是
    一样的：哪个校区、哪栋楼、哪间教室、第几节课、哪天是空的。
    框架只认这层模型，不认任何学校的字段名，这样换学校就不用改框架。

类比：
    模型 = 快递面单（收件人/电话/地址固定几栏）；
    适配器 = 各学校填面单的人（把自家系统的黑话翻译成面单上的标准栏）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class Campus:
    """校区"""
    code: str          # 教务系统内部的校区编码，如 "02"
    name: str          # 展示名，如 "泰达"

    def __str__(self) -> str:  # pragma: no cover - 仅用于日志友好显示
        return f"{self.name}({self.code})"


@dataclass(frozen=True)
class Building:
    """教学楼"""
    code: str          # 教务系统内部楼号编码
    name: str          # 展示名，如 "9号楼"

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.name}({self.code})"


@dataclass(frozen=True)
class Room:
    """一间空闲教室（某一节次、某一天）"""
    building_name: str
    classroom_name: str

    def full_name(self) -> str:
        return f"{self.building_name}{self.classroom_name}"


@dataclass(frozen=True)
class Period:
    """一节课（节次编号 + 起止时间）"""
    number: int
    time_range: str    # 如 "08:20-09:05"

    def __str__(self) -> str:  # pragma: no cover
        return f"第{self.number}节 {self.time_range}"


@dataclass
class SchoolProfile:
    """学校画像：框架在真正开爬之前需要知道的静态信息"""
    school_id: str                        # 英文短名，用于 CLI --school，如 "tust"
    school_name: str                      # 中文全称，如 "天津科技大学"
    base_url: str                         # 教务系统根地址
    periods: Dict[int, str]               # 节次 → 时间
    entry_path: str = ""                  # 空闲教室页相对路径（可为空则直接用 base_url）
    default_campus: Optional[str] = None  # 前端默认选中校区名（None=由数据顺序决定）
    campus_order: List[str] = field(default_factory=list)  # 校区展示排序（越靠前越优先）
    source_note: str = ""                 # 数据来源声明，写进导出的 index.json

    def period_numbers(self) -> List[int]:
        """所有节次编号（升序）"""
        return sorted(self.periods)

    def entry_url(self) -> str:
        """空闲教室页完整地址"""
        if not self.entry_path:
            return self.base_url
        return f"{self.base_url.rstrip('/')}/{self.entry_path.lstrip('/')}"


def periods_from_list(pairs: List[tuple]) -> Dict[int, str]:
    """把 [(1, "08:20-09:05"), ...] 转成 {1: "08:20-09:05"} —— 写适配器时更顺手"""
    return {int(n): str(t) for n, t in pairs}
