"""extract-oracle — 归档提取预言机。

本包只做"读字节 + 模拟目标平台语义"，不解压到磁盘、不联网、不评分。
当前状态：**五模块全部落地**（`structure` / `encoding` / `fold` / `accessibility` / `container`，见
`capabilities.py`），不带 `--module` 的 `check` 出完整报告。若某个模块被翻回未落地，
`check` 会**显式拒绝**（退出码 3 + `capability_missing`），不产出空 findings。

版本号是唯一真源：`pyproject.toml` 通过 `dynamic = ["version"]` 读本模块的 `__version__`。
"""

__version__ = "1.0.0"

__all__ = ["__version__"]
