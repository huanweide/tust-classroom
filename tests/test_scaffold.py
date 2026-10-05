"""脚手架测试：生成的骨架必须能 import、能通过契约校验"""
import os

import pytest

from campusfree.scaffold import _class_name, create_adapter_scaffold


def test_class_name():
    assert _class_name("nku") == "Nku"
    assert _class_name("bei-you") == "BeiYou"
    assert _class_name("x") == "X"


def test_scaffold_creates_file(tmp_path):
    path = create_adapter_scaffold(str(tmp_path), "nku", school_name="南开大学")
    assert os.path.exists(path)
    text = open(path, encoding="utf-8").read()
    assert "class NkuAdapter" in text
    assert 'school_id="nku"' in text
    assert "南开大学" in text
    assert "TODO" in text


def test_scaffold_refuses_overwrite(tmp_path):
    create_adapter_scaffold(str(tmp_path), "nku")
    with pytest.raises(FileExistsError):
        create_adapter_scaffold(str(tmp_path), "nku")


@pytest.mark.parametrize("bad", ["", "南开", "NK U", "nku!", "中文"])
def test_scaffold_rejects_bad_id(tmp_path, bad):
    with pytest.raises(ValueError):
        create_adapter_scaffold(str(tmp_path), bad)


def test_generated_scaffold_passes_contract(tmp_path, monkeypatch):
    """生成出来的骨架必须能 import 且通过 validate_adapter —— 否则等于给用户一堆报错"""
    root = str(tmp_path)
    os.makedirs(os.path.join(root, "adapters"), exist_ok=True)
    create_adapter_scaffold(root, "nku", school_name="南开大学")

    # 直接按文件路径加载：避免和真实 adapters 包在 sys.modules 里撞车
    import importlib.util

    path = os.path.join(root, "adapters", "nku.py")
    spec = importlib.util.spec_from_file_location("scaffold_probe_nku", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    from campusfree.adapter import validate_adapter
    problems = validate_adapter(mod.ADAPTER())
    assert problems == [], f"骨架不该有契约问题：{problems}"
