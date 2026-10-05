"""学校适配器包

每个 .py 文件 = 一所学校。放进来就会被 campusfree 自动发现，
不需要在框架里注册任何东西。

命名约定：
    文件名    = 学校英文短名（小写，如 tust.py / nku.py）
    模块变量  = ADAPTER（适配器类或实例，二选一都行）

用 `python -m campusfree new-school <英文短名>` 可以自动生成骨架。
"""
