"""判定层输出的**唯一形状**（`plan/03` §0 的 `Finding`）。

判定模块（`rules/*`）只产出本模块的 `Finding`，不碰文件、不碰 CLI；序列化与排序口径
在这里定义一次（`data/README.md` §4.8：`findings` 按 `(cd_offset, ruleId)` 升序）。

为什么放在包根而不是 `rules/` 里：K10 要求判定模块之间互不 import。形状契约若放进
`rules/`，每个判定模块都要 import 它 —— 那是"判定模块互相 import"的字面形态，
AST 守门会（正确地）变红。包根的叶子模块不属于判定层。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


def display_name(raw: bytes | None) -> str | None:
    """原始名字节 → 人读展示形（**可逆性由 `*_hex` 字段保证，不靠这个**）。

    口径修订（M2 实测）：`plan/03` 原写"surrogateescape 可逆"，但 surrogateescape 产生的
    孤立代理项在 `json.dumps(..., ensure_ascii=False)` 下无法编码为 UTF-8（写盘直接抛
    `UnicodeEncodeError`），而 `ensure_ascii=True` 违反 K03。因此展示形改用
    `backslashreplace`：合法 UTF-8 原样显示，非法字节显示为 `\\xNN`，JSON 安全且确定。
    精确字节一律在 `lfhNameHex` / `cdNameHex` 里逐字节保留。
    """

    if raw is None:
        return None
    return raw.decode("utf-8", "backslashreplace")


@dataclass(frozen=True)
class Finding:
    """一条判定结果。`precedent` 对 MOD-1 必填（实现选择来源，**不是**规范条文）。"""

    rule_id: str
    message: str
    evidence: dict[str, Any] = field(default_factory=dict)
    precedent: str | None = None
    entry_index: int | None = None
    lfh_offset: int | None = None
    cd_offset: int | None = None
    lfh_name: str | None = None
    cd_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """报告里的固定键集（键序由 `json.dumps(sort_keys=True)` 统一，不靠这里）。"""

        return {
            "ruleId": self.rule_id,
            "entryIndex": self.entry_index,
            "lfhOffset": self.lfh_offset,
            "cdOffset": self.cd_offset,
            "lfhName": self.lfh_name,
            "cdName": self.cd_name,
            "message": self.message,
            "evidence": self.evidence,
            "precedent": self.precedent,
        }


def sort_key(item: Finding) -> tuple[int, str, int]:
    """`(cd_offset, ruleId)` 升序；归档级 finding（无 CD 偏移）排最前。

    第三项 `entry_index` 只是并列时的确定性兜底：同一偏移上同一规则理论上只会有一条，
    但排序键必须是**全序**，否则并列顺序取决于输入顺序（K09）。
    """

    return (
        item.cd_offset if item.cd_offset is not None else -1,
        item.rule_id,
        item.entry_index if item.entry_index is not None else -1,
    )


def sort_findings(items: Iterable[Finding]) -> tuple[Finding, ...]:
    return tuple(sorted(items, key=sort_key))


__all__ = ["Finding", "display_name", "sort_findings", "sort_key"]
