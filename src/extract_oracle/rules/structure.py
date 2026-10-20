"""MOD-1 双头差分与重叠（`plan/03` §MOD-1）。

**六条规则，零解码**：全部判定落在字节层给出的结构事实上（`zip_reader.EntryView`）。

依据纪律（硬，`plan/00` 决策 ⑤、`data/README.md` §1.4）：

- `precedent` 必填，取值只能是 `PRECEDENTS` 里的实现选择枚举；
- **不得**引"规范要求 LFH 与 CD 一致"——逐字检索 APPNOTE 6.3.10，「must be identical」
  与「SHOULD match」均无命中。规范没说过的话不能编。

本模块是纯函数：`(Archive) -> tuple[Finding, ...]`。不写盘、不联网、不 import 其他判定模块、
不 import `cli`（K10，AST 守门在 `tests/test_rule_boundaries.py`）。
"""

from __future__ import annotations

from ..findings import Finding, display_name, sort_findings
from ..zip_reader import Archive, EntryView

#: `precedent` 的合法取值（实现选择枚举，`plan/03` §MOD-1）。
#:
#: **M2 扩展记**：原枚举只有四个"读哪个头"的取值。但六条规则里 `LFH_OVERLAP` 与
#: `CD_COUNT_MISMATCH` 的依据**不是**读头选择——前者是"物理区间相交"的结构自证，
#: 后者是 APPNOTE 的 EOCD 字段定义（`docs/rules.md` §二 本来就标"结构自证"）。
#: 把它们的 `precedent` 写成 `python_zipfile_reads_cd` / `unzip_reads_cd` 是**错误归因**
#: （与"不得编造条文"同一条纪律：也不得编造依据来源）。因此新增一个显式取值
#: `structural_self_evidence`，并同提交改 `plan/03` §MOD-1 的枚举与 `docs/rules.md` §六。
PRECEDENTS: tuple[str, ...] = (
    "unzip_reads_cd",
    "libzip_reads_cd",
    "python_zipfile_reads_cd",
    "libarchive_reads_lfh",
    "structural_self_evidence",
)

#: general purpose bit flag bit 3 = 有 data descriptor（CRC/大小写在头之后）。
FLAG_DATA_DESCRIPTOR = 0x0008


def _base(
    entry: EntryView,
    rule_id: str,
    message: str,
    evidence: dict,
    precedent: str,
) -> Finding:
    return Finding(
        rule_id=rule_id,
        message=message,
        evidence=evidence,
        precedent=precedent,
        entry_index=entry.index,
        lfh_offset=entry.lfh_offset,
        cd_offset=entry.cd_offset,
        lfh_name=display_name(entry.lfh_name),
        cd_name=display_name(entry.cd_name),
    )


def _data_descriptor_exempt(entry: EntryView, lfh_value: int) -> bool:
    """bit 3 置位 **且** LFH 该字段为 0 → 豁免。

    这是 APPNOTE 允许的形态：有 data descriptor 时 LFH 的 CRC/大小字段"可以先写 0"，
    真值在数据之后的 descriptor 里。此时拿 0 去和 CD 比必然"不等"，但那是**合法写法**，
    不是分歧（误报控制，`plan/03` §MOD-1 表格第三列）。
    """

    return bool(entry.lfh_flags & FLAG_DATA_DESCRIPTOR) and lfh_value == 0


def check_name(entry: EntryView) -> Finding | None:
    """`structure.NAME_DIVERGES`：`lfh_name != cd_name`（**字节**比较，不解码）。"""

    if entry.lfh_name == entry.cd_name:
        return None
    return _base(
        entry,
        "structure.NAME_DIVERGES",
        "本地头与中央目录的名字不同：不同工具会写出不同文件名",
        {
            "lfhNameHex": entry.lfh_name.hex(),
            "cdNameHex": entry.cd_name.hex(),
            "lfhNameLength": len(entry.lfh_name),
            "cdNameLength": len(entry.cd_name),
            # 逐个工具读哪个头（本机实测 + libarchive#2695 作者原话）。
            # 7-Zip 也取 LFH，但枚举里没有 `7zip_reads_lfh` 这个取值——它只出现在本字段，
            # 不进 `precedent`（枚举是口径，不得就地扩）。
            "readers": {
                "libarchive": "lfh",
                "7zip": "lfh",
                "info-zip-unzip": "cd",
                "libzip": "cd",
                "python-zipfile": "cd",
            },
        },
        "libarchive_reads_lfh",
    )


def check_crc(entry: EntryView) -> Finding | None:
    """`structure.CRC_DIVERGES`：`lfh_crc != cd_crc`（bit 3 + LFH 为 0 时豁免）。"""

    if _data_descriptor_exempt(entry, entry.lfh_crc):
        return None
    if entry.lfh_crc == entry.cd_crc:
        return None
    return _base(
        entry,
        "structure.CRC_DIVERGES",
        "本地头与中央目录的 CRC32 不同：一个工具报错、另一个照解",
        {
            "lfhCrc": entry.lfh_crc,
            "cdCrc": entry.cd_crc,
            "lfhFlags": entry.lfh_flags,
            "cdFlags": entry.cd_flags,
            "dataDescriptor": bool(entry.lfh_flags & FLAG_DATA_DESCRIPTOR),
        },
        "libarchive_reads_lfh",
    )


def check_size(entry: EntryView) -> Finding | None:
    """`structure.SIZE_DIVERGES`：压缩/未压缩大小任一不等（bit 3 豁免同上）。"""

    if _data_descriptor_exempt(entry, entry.lfh_csize) and _data_descriptor_exempt(
        entry, entry.lfh_usize
    ):
        return None
    if entry.lfh_csize == entry.cd_csize and entry.lfh_usize == entry.cd_usize:
        return None
    return _base(
        entry,
        "structure.SIZE_DIVERGES",
        "本地头与中央目录的大小不同：按哪个头读会得到不同字节数",
        {
            "lfhCompSize": entry.lfh_csize,
            "cdCompSize": entry.cd_csize,
            "lfhUncompSize": entry.lfh_usize,
            "cdUncompSize": entry.cd_usize,
            "lfhFlags": entry.lfh_flags,
            "cdFlags": entry.cd_flags,
            "dataDescriptor": bool(entry.lfh_flags & FLAG_DATA_DESCRIPTOR),
        },
        "libarchive_reads_lfh",
    )


def check_flags(entry: EntryView) -> Finding | None:
    """`structure.FLAG_DIVERGES`：`lfh_flags != cd_flags`（全 16 位比较）。"""

    if entry.lfh_flags == entry.cd_flags:
        return None
    diff = entry.lfh_flags ^ entry.cd_flags
    bits = [bit for bit in range(16) if diff & (1 << bit)]
    return _base(
        entry,
        "structure.FLAG_DIVERGES",
        "本地头与中央目录的 general purpose flag 不同：同一份名字会按不同编码/加密语义解释",
        {
            "lfhFlags": entry.lfh_flags,
            "cdFlags": entry.cd_flags,
            "differingBits": bits,
        },
        "unzip_reads_cd",
    )


def check_overlap(entries: tuple[EntryView, ...]) -> tuple[Finding, ...]:
    """`structure.LFH_OVERLAP`：两个 LFH 的物理区间 `[start, end)` 相交。

    排序后线性扫：`next.start < prev.end` 即相交。**相邻不算相交**（`next.start == prev.end`）。
    区间用 LFH 自己声明的 `comp_size` 算（`EntryView.lfh_span`），所以一条 LFH 落在另一条的
    数据区里会被抓到——这正是 `overlap.zip` 的构造。
    """

    ordered = sorted(entries, key=lambda item: (item.lfh_offset, item.lfh_end, item.index))
    found: list[Finding] = []
    for left, right in zip(ordered, ordered[1:]):
        if right.lfh_offset >= left.lfh_end:
            continue
        found.append(
            _base(
                right,
                "structure.LFH_OVERLAP",
                "两个本地文件头记录物理相交：一个工具拒绝、另一些照解",
                {
                    "first": {
                        "entryIndex": left.index,
                        "start": left.lfh_offset,
                        "end": left.lfh_end,
                    },
                    "second": {
                        "entryIndex": right.index,
                        "start": right.lfh_offset,
                        "end": right.lfh_end,
                    },
                    "readers": {
                        "python-zipfile": "refused",
                        "info-zip-unzip": "extracted",
                        "7zip": "extracted",
                        "libarchive": "extracted",
                    },
                },
                # 重叠不是"读哪个头"的问题：它是物理布局的自证（区间相交）。
                "structural_self_evidence",
            )
        )
    return tuple(found)


def check_count(archive: Archive) -> Finding | None:
    """`structure.CD_COUNT_MISMATCH`：EOCD 声明条目数 ≠ 实际解析到的 CD 条目数。

    归档级 finding：没有单一条目可归属，`entryIndex` / 偏移一律 `None`（排序排最前）。
    """

    declared = archive.probe.declared_entries
    actual = archive.cd_actual_entries
    if declared == actual:
        return None
    return Finding(
        rule_id="structure.CD_COUNT_MISMATCH",
        message="EOCD 声明的条目数与中央目录实际条目数不同",
        evidence={
            "declared": declared,
            "actual": actual,
            "zip64": archive.zip64,
            "cdSpanStart": archive.cd_span[0],
            "cdSpanEnd": archive.cd_span[1],
        },
        # EOCD 的字段定义本身就是依据（`docs/rules.md` §二 标"APPNOTE EOCD 字段定义"），
        # 不是"某个工具读哪个头"。
        precedent="structural_self_evidence",
    )


def check(archive: Archive) -> tuple[Finding, ...]:
    """MOD-1 的全部判定。输出按 `(cd_offset, ruleId)` 升序（`data/README.md` §4.8）。"""

    found: list[Finding] = []
    for entry in archive.entries:
        for rule in (check_name, check_crc, check_size, check_flags):
            finding = rule(entry)
            if finding is not None:
                found.append(finding)
    found.extend(check_overlap(archive.entries))
    count_finding = check_count(archive)
    if count_finding is not None:
        found.append(count_finding)
    return sort_findings(found)


__all__ = [
    "FLAG_DATA_DESCRIPTOR",
    "PRECEDENTS",
    "check",
    "check_count",
    "check_crc",
    "check_flags",
    "check_name",
    "check_overlap",
    "check_size",
]
