"""MOD-2 编码与 Unicode path extra field（**M2 只做骨架**；推断在 M5 收尾）。

M2 的交付边界（`plan/03` §MOD-2、`plan/HANDOFF-M2.md` §3 第 3 条）：

- **原始名字节必须留**：`raw_name_hex` 逐字节可逆，不靠任何解码；
- **bit 11**（general purpose flag，名字为 UTF-8）原样给出；
- **extra fields** 切成 `(id, size)` 序列，`0x7075` 解析 `version / name_crc32 / utf8_name`
  并**校验 CRC 是否对上原名字节**（对不上 = 覆盖失效，这是结构事实，不是猜测）。

**M5 才做的**（本模块现在**不做**，`capabilities` 里 `encoding` 保持 False）：

- 六个候选编码的完整性与可信度（`data/README.md` §4.4 的 `high/medium/low`）；
- `encoding.candidates[]` 与 `predictedNames`；
- `encoding.UPATH_CRC_MISMATCH` finding。

误报控制（`plan/03`）：无法完整解码的候选**不出现**在候选列表里；`predictedNames` 对不可解码
情形给 `null` + `reason`，不编造替代名。M5 落地时必须照此写。
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass

from ..zip_reader import Archive, EntryView, ExtraField

#: general purpose bit flag bit 11：名字为 UTF-8（APPNOTE 6.3.10 D.1）。
FLAG_UTF8 = 0x0800

#: Info-ZIP Unicode Path extra field（APPNOTE 6.3.10 D.6）。
UPATH_ID = 0x7075
#: Info-ZIP Unicode Comment extra field（只记录不解释）。
UCOMMENT_ID = 0x6375
#: Extended timestamp（只记录不解释）。
EXT_TIMESTAMP_ID = 0x0008

#: M5 的候选顺序（`data/README.md` §4.4）。这里**只登记顺序**，不做推断。
CANDIDATE_ENCODINGS: tuple[str, ...] = ("UTF-8", "CP437", "GBK", "CP932", "CP949", "CP1251")

#: 只记录不解释的 extra id（M5 也不会解释它们，但报告里要能看见）。
RECORD_ONLY_IDS: tuple[int, ...] = (UCOMMENT_ID, EXT_TIMESTAMP_ID)


@dataclass(frozen=True)
class UpathField:
    """`0x7075` 的结构事实。`crc_valid is None` = 字段不存在。"""

    present: bool
    version: int | None = None
    name_crc32: int | None = None
    utf8_name: str | None = None
    crc_valid: bool | None = None

    def to_dict(self) -> dict:
        return {
            "present": self.present,
            "version": self.version,
            "name_crc32": self.name_crc32,
            "utf8_name": self.utf8_name,
            "crc_valid": self.crc_valid,
        }


@dataclass(frozen=True)
class NameFacts:
    """一个条目的名字层结构事实（M2 骨架的输出）。**不含任何推断出的"会写成什么名"**。"""

    entry_index: int
    raw_name_hex: str
    raw_name_length: int
    bit11: bool
    extra_ids: tuple[int, ...]
    upath: UpathField

    def to_dict(self) -> dict:
        return {
            "entryIndex": self.entry_index,
            "rawNameHex": self.raw_name_hex,
            "rawNameLength": self.raw_name_length,
            "bit11": self.bit11,
            "extraIds": list(self.extra_ids),
            "upath": self.upath.to_dict(),
        }


def _find(extra: tuple[ExtraField, ...], field_id: int) -> ExtraField | None:
    return next((item for item in extra if item.field_id == field_id), None)


def parse_upath(entry: EntryView) -> UpathField:
    """解析 `0x7075`：`version(1) / name_crc32(4) / utf8_name(rest)`。

    CRC 按**条目原名字节**校验（APPNOTE 6.3.10 D.6）。结构不完整时 `present=True` 但
    `crc_valid=None`——"字段在但读不懂"与"字段不在"是两件事，不能合并。
    """

    field = _find(entry.cd_extra, UPATH_ID)
    if field is None:
        return UpathField(present=False)
    if len(field.data) < 5:
        return UpathField(present=True)
    version = field.data[0]
    name_crc32 = int.from_bytes(field.data[1:5], "little")
    raw_utf8 = field.data[5:]
    try:
        utf8_name: str | None = raw_utf8.decode("utf-8")
    except UnicodeDecodeError:
        utf8_name = None
    expected = zlib.crc32(entry.cd_name) & 0xFFFFFFFF
    return UpathField(
        present=True,
        version=version,
        name_crc32=name_crc32,
        utf8_name=utf8_name,
        crc_valid=name_crc32 == expected,
    )


def describe(entry: EntryView) -> NameFacts:
    return NameFacts(
        entry_index=entry.index,
        raw_name_hex=entry.cd_name.hex(),
        raw_name_length=len(entry.cd_name),
        bit11=bool(entry.cd_flags & FLAG_UTF8),
        extra_ids=tuple(item.field_id for item in entry.cd_extra),
        upath=parse_upath(entry),
    )


def describe_all(archive: Archive) -> tuple[NameFacts, ...]:
    """按 CD 顺序（= `entry_index` 升序）给出全部条目的名字层事实。"""

    return tuple(describe(entry) for entry in archive.entries)


__all__ = [
    "CANDIDATE_ENCODINGS",
    "EXT_TIMESTAMP_ID",
    "FLAG_UTF8",
    "RECORD_ONLY_IDS",
    "UCOMMENT_ID",
    "UPATH_ID",
    "NameFacts",
    "UpathField",
    "describe",
    "describe_all",
    "parse_upath",
]
