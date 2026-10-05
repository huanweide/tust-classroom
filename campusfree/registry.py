"""适配器注册表 —— 自动发现 adapters/ 目录下所有学校适配器

约定优于配置：只要把一个继承 SchoolAdapter 的类放进 adapters/ 包的任意
模块里，并在该模块暴露 `ADAPTER` 变量（实例或类），框架就能自动发现它。
新增学校不用改框架一行代码。
"""
from __future__ import annotations

import importlib
import inspect
import os
import pkgutil
from typing import Any, Dict, List, Type

from .adapter import SchoolAdapter
from .model import SchoolProfile

ADAPTERS_PACKAGE = "adapters"


def _package_root() -> str:
    """adapters/ 目录在磁盘上的位置（本文件的上级目录里的 adapters）"""
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "adapters")


def discover_modules() -> List[str]:
    """列出 adapters/ 下所有可导入的模块名（下划线开头的模板/私有模块除外）"""
    root = _package_root()
    if not os.path.isdir(root):
        return []
    names: List[str] = []
    for mod in pkgutil.iter_modules([root]):
        if mod.name.startswith("_"):
            continue
        names.append(mod.name)
    return sorted(names)


def _load_module(name: str):
    return importlib.import_module(f"{ADAPTERS_PACKAGE}.{name}")


def _candidate_classes(mod) -> List[Type[SchoolAdapter]]:
    """模块里所有「具体实现」的适配器类（跳过抽象基类和模板）"""
    found: List[Type[SchoolAdapter]] = []
    for _, obj in inspect.getmembers(mod, inspect.isclass):
        if not issubclass(obj, SchoolAdapter) or obj is SchoolAdapter:
            continue
        if inspect.isabstract(obj):
            continue
        if obj.__module__ != mod.__name__:
            continue  # 从别处 import 进来的不算
        found.append(obj)
    return found


def instantiate(mod) -> Any:
    """从一个模块里造出适配器实例

    优先级：模块级 ADAPTER（可以是实例也可以是类） > 模块里唯一的适配器类。
    """
    explicit = getattr(mod, "ADAPTER", None)
    if explicit is not None:
        return explicit() if inspect.isclass(explicit) else explicit
    classes = _candidate_classes(mod)
    if not classes:
        return None
    return classes[0]()


def list_adapters() -> Dict[str, Any]:
    """返回 {school_id: 适配器实例}；坏的适配器不会污染整个注册表"""
    result: Dict[str, Any] = {}
    for name in discover_modules():
        try:
            mod = _load_module(name)
            adapter = instantiate(mod)
        except Exception:
            continue  # 单个学校写坏了，不影响其它学校
        if adapter is None:
            continue
        try:
            prof: SchoolProfile = adapter.profile
            result[prof.school_id] = adapter
        except Exception:
            continue
    return result


def get_adapter(school_id: str) -> Any:
    """按 school_id 取适配器；找不到就抛出带候选清单的人话异常"""
    adapters = list_adapters()
    if school_id in adapters:
        return adapters[school_id]
    available = ", ".join(sorted(adapters)) or "（暂无任何适配器）"
    raise KeyError(f"找不到学校适配器 {school_id!r}。已注册：{available}")


def schools_summary() -> List[Dict[str, Any]]:
    """给 CLI 用的学校清单摘要"""
    out: List[Dict[str, Any]] = []
    for sid, adapter in sorted(list_adapters().items()):
        prof: SchoolProfile = adapter.profile
        out.append({
            "school_id": sid,
            "school_name": prof.school_name,
            "base_url": prof.base_url,
            "periods": len(prof.periods),
            "default_campus": prof.default_campus or "-",
        })
    return out
