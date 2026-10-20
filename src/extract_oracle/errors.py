"""错误与降级：reason code → 退出码的唯一映射表。

纪律（`data/README.md` §4.1）：任何"我做不了"的分支必须是 2/3，
**绝不允许静默返回 0**。因此本模块只提供"显式拒绝"的载体，不提供"降级成空结果"的路径。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .exit_codes import ExitCode


class ReasonCode(str, Enum):
    """机读原因码。取值固定，新增须同提交改 `data/README.md` §4.1 与本文档。"""

    USAGE_ERROR = "usage_error"
    INPUT_UNREADABLE = "input_unreadable"
    EOCD_NOT_FOUND = "eocd_not_found"
    CD_UNREADABLE = "cd_unreadable"
    LFH_UNREADABLE = "lfh_unreadable"
    ZIP64_UNSUPPORTED = "zip64_unsupported"
    PLATFORM_TABLE_MISSING = "platform_table_missing"
    CAPABILITY_MISSING = "capability_missing"


#: reason code → 退出码。**全项目唯一一张映射表**。
EXIT_FOR_REASON: dict[ReasonCode, ExitCode] = {
    ReasonCode.USAGE_ERROR: ExitCode.USAGE_ERROR,
    ReasonCode.INPUT_UNREADABLE: ExitCode.INPUT_UNREADABLE,
    ReasonCode.EOCD_NOT_FOUND: ExitCode.INPUT_UNREADABLE,
    # CD/LFH 解析不了 = 输入不可解析（`data/README.md` §4.1 的第 2 档），不是"没发现问题"。
    ReasonCode.CD_UNREADABLE: ExitCode.INPUT_UNREADABLE,
    ReasonCode.LFH_UNREADABLE: ExitCode.INPUT_UNREADABLE,
    ReasonCode.ZIP64_UNSUPPORTED: ExitCode.CAPABILITY_MISSING,
    ReasonCode.PLATFORM_TABLE_MISSING: ExitCode.CAPABILITY_MISSING,
    ReasonCode.CAPABILITY_MISSING: ExitCode.CAPABILITY_MISSING,
}


@dataclass(frozen=True)
class OracleError(Exception):
    """一次显式拒绝。`detail` 必须是 JSON 可序列化且不含本机绝对路径。"""

    code: ReasonCode
    message: str
    detail: dict[str, Any] = field(default_factory=dict)

    @property
    def exit_code(self) -> ExitCode:
        return EXIT_FOR_REASON[self.code]

    def __str__(self) -> str:  # pragma: no cover - 仅用于调试
        return f"{self.code.value}: {self.message}"


__all__ = ["ReasonCode", "EXIT_FOR_REASON", "OracleError"]
