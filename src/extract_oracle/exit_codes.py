"""退出码常量（代码侧唯一定义处）。

口径单一真相源 = `data/README.md` §4.1。本模块只把那张表落成常量，
**不得**在别处硬编码整数退出码；新增/改动必须先改 §4.1 再同提交改这里。
"""

from __future__ import annotations

from enum import IntEnum


class ExitCode(IntEnum):
    """与 `data/README.md` §4.1 一一对应。"""

    OK = 0
    FINDINGS = 1
    INPUT_UNREADABLE = 2
    CAPABILITY_MISSING = 3
    USAGE_ERROR = 4


__all__ = ["ExitCode"]
