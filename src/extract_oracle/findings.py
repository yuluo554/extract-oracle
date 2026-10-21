"""判定层输出的**唯一形状**（`plan/03` §0 的 `Finding`）。

判定模块（`rules/*`）只产出本模块的 `Finding`，不碰文件、不碰 CLI；序列化与排序口径
在这里定义一次（`data/README.md` §4.8：`findings` 按 `(cd_offset, ruleId)` 升序）。

为什么放在包根而不是 `rules/` 里：K10 要求判定模块之间互不 import。形状契约若放进
`rules/`，每个判定模块都要 import 它 —— 那是"判定模块互相 import"的字面形态，
AST 守门会（正确地）变红。包根的叶子模块不属于判定层。
"""

from __future__ import annotations

import json
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


def sort_key(item: Finding) -> tuple[int, str, int, str]:
    """`(cd_offset, ruleId)` 升序；归档级 finding（无 CD 偏移）排最前。

    后两项是并列时的确定性兜底：同一偏移上同一规则理论上只会有一条，但 M5 的 `budget.*`
    会**按平台**各出一条（同一组件在 Windows 与 Linux 上都超限，`evidence.platform` 不同），
    此时前三项完全相同。第四项取证据的确定性序列化——排序键必须是**全序**，否则并列顺序
    取决于输入顺序（K09）。
    """

    return (
        item.cd_offset if item.cd_offset is not None else -1,
        item.rule_id,
        item.entry_index if item.entry_index is not None else -1,
        json.dumps(item.evidence, sort_keys=True, ensure_ascii=False, default=str),
    )


def sort_findings(items: Iterable[Finding]) -> tuple[Finding, ...]:
    return tuple(sorted(items, key=sort_key))


#: MOD-3 的四条折叠判定（`data/README.md` §4.3；顺序即**判定顺序**）。
COLLISION_CODES: tuple[str, ...] = (
    "collision.FILEDIR",
    "collision.CASEFOLD",
    "collision.NFC",
    "collision.TRIM",
)

#: `collision.verdict` 的三个合法取值（`plan/01` §2 模块③、`data/README.md` §4.9）。
VERDICTS: tuple[str, ...] = ("overwritten", "renamed", "skipped")


@dataclass(frozen=True)
class Collision:
    """一条跨平台落盘折叠（MOD-3 的输出形状，`plan/01` §2 模块③）。

    与 `Finding` 的区别是**有意**的：`Finding` 说的是"归档内部两处事实不一致"，
    `Collision` 说的是"在目标平台上两条目会落到同一个名字上，最后剩谁"。前者用
    `precedent`（哪个工具读哪个头），后者用 `evidence_strength`（`data/README.md` §4.7）。

    字段口径（`data/README.md` §4.9 是唯一表述）：
    - `names` / `on_disk_names` / `write_order` / `cd_offsets` 四个数组**同长同序**，
      顺序 = CD 顺序（即写序）；
    - `survivor` 是**存活下来那一条的归档名**：`FILEDIR` 取先写者（后写者根本没落盘），
      其余三条取后写者（内容覆盖）；
    - `verdict` 说的是**非存活者**的遭遇：`overwritten` / `renamed` / `skipped`。
    """

    code: str
    platform: str
    names: tuple[str, ...]
    on_disk_names: tuple[str, ...]
    write_order: tuple[int, ...]
    cd_offsets: tuple[int, ...]
    survivor: str
    survivor_entry_index: int
    verdict: str
    evidence_strength: str
    evidence: dict[str, Any] = field(default_factory=dict)

    @property
    def sort_key(self) -> tuple[int, str, str, tuple[int, ...]]:
        return (
            min(self.cd_offsets) if self.cd_offsets else -1,
            self.code,
            self.platform,
            self.write_order,
        )

    def to_dict(self) -> dict[str, Any]:
        """报告里的固定键集（键序由 `json.dumps(sort_keys=True)` 统一）。"""

        return {
            "code": self.code,
            "platform": self.platform,
            "names": list(self.names),
            "onDiskNames": list(self.on_disk_names),
            "writeOrder": list(self.write_order),
            "cdOffsets": list(self.cd_offsets),
            "survivor": self.survivor,
            "survivorEntryIndex": self.survivor_entry_index,
            "verdict": self.verdict,
            "evidenceStrength": self.evidence_strength,
            "evidence": self.evidence,
        }


def sort_collisions(items: Iterable[Collision]) -> tuple[Collision, ...]:
    """`(min(cd_offset), code)` 升序（`data/README.md` §4.8）；并列按平台与写序兜底成全序。"""

    return tuple(sorted(items, key=lambda item: item.sort_key))


__all__ = [
    "COLLISION_CODES",
    "VERDICTS",
    "Collision",
    "Finding",
    "display_name",
    "sort_collisions",
    "sort_findings",
    "sort_key",
]
