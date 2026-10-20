"""extract-oracle — 归档提取预言机（骨架期）。

本包只做"读字节 + 模拟目标平台语义"，不解压到磁盘、不联网、不评分。
当前状态：骨架（M0）。判定模块（MOD-1…MOD-5）自 M2 起逐里程碑落地，
落地前 `check` 子命令**显式拒绝**（退出码 3 + `capability_missing`），不产出空 findings。

版本号是唯一真源：`pyproject.toml` 通过 `dynamic = ["version"]` 读本模块的 `__version__`。
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
