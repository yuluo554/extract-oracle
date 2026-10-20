"""ZIP 字节层：EOCD / 中央目录（CD）/ 本地文件头（LFH）三层完整解析。

骨架期只做 EOCD 探测；M2 起补全三层。**本模块只返回结构事实，不做任何判定**——
`plan/02` §一 第一条硬边界：字节层不产出 `ruleId`。任何按名字/标志/编码的**解释**都在
`rules/*`；本模块只 `seek`/`read` 字节，不产生解压产物、不写盘、不联网。

三层各自的字段来源（这也是 MOD-1 全部六条规则的输入）：

```
EOCD  声明的条目数 / CD 大小 / CD 偏移 / 注释长度
 CD   每条：名字、flags、CRC、压缩/未压缩大小、method、extra、relative_offset
 LFH   每条：名字、flags、CRC、压缩/未压缩大小、method、extra
```

**解析失败一律显式拒绝**（`data/README.md` §4.1：输入不可解析 = 2，绝不退化成空结果）。
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

from .errors import OracleError, ReasonCode

EOCD_SIG = b"PK\x05\x06"
EOCD_MIN_SIZE = 22
#: EOCD 之后最多允许的注释长度（APPNOTE 6.3.10：comment 长度字段为 2 字节，上限 65535）。
EOCD_MAX_COMMENT = 0xFFFF

CD_SIG = b"PK\x01\x02"
CD_MIN_SIZE = 46
LFH_SIG = b"PK\x03\x04"
LFH_MIN_SIZE = 30

ZIP64_EOCD_SIG = b"PK\x06\x06"
ZIP64_LOCATOR_SIG = b"PK\x06\x07"
ZIP64_LOCATOR_SIZE = 20
ZIP64_EOCD_MIN_SIZE = 56
#: EOCD 字段达到这些值即表示"真值在 ZIP64 EOCD 里"（APPNOTE 4.4.21 / 4.4.22）。
ZIP64_SENTINEL_16 = 0xFFFF
ZIP64_SENTINEL_32 = 0xFFFFFFFF


@dataclass(frozen=True)
class ZipProbe:
    """EOCD 层的结构事实（M0 起的字段，M2 只做加法）。"""

    archive_size: int
    eocd_offset: int
    declared_entries: int
    declared_cd_size: int
    declared_cd_offset: int
    comment_length: int


@dataclass(frozen=True)
class ExtraField:
    """一个 extra field 的**原始**字节（未解释）。`field_id` 是 2 字节头 id。"""

    field_id: int
    data: bytes

    @property
    def size(self) -> int:
        return len(self.data)


@dataclass(frozen=True)
class EntryView:
    """一个条目的结构事实（`plan/03` §0 的 `EntryView`）。名字是**原始字节**，不解码。"""

    index: int
    lfh_offset: int
    lfh_end: int
    cd_offset: int
    lfh_name: bytes
    cd_name: bytes
    lfh_flags: int
    cd_flags: int
    lfh_crc: int
    cd_crc: int
    lfh_csize: int
    cd_csize: int
    lfh_usize: int
    cd_usize: int
    lfh_extra: tuple[ExtraField, ...]
    cd_extra: tuple[ExtraField, ...]
    method: int

    @property
    def lfh_span(self) -> tuple[int, int]:
        """`[start, end)` 物理区间 = LFH 头 + 名字 + extra + 压缩数据（含 data descriptor 之外的定长部分）。

        `end` 用 **LFH 自己声明的** `comp_size` 算（不用 CD 的）——重叠判定要反映"这条 LFH 实际
        占了多少字节"，CD 的大小可能与 LFH 不一致（那正是 `SIZE_DIVERGES`）。
        """

        return (self.lfh_offset, self.lfh_end)

    @property
    def extra(self) -> tuple[ExtraField, ...]:
        """读者实际消费的那一份 extra：CD 是权威来源，LFH 那份另名保留。"""

        return self.cd_extra

    @property
    def name_raw(self) -> bytes:
        """判定用的原名字节：CD 名（`unzip`/`libzip`/`python` 都读它）。"""

        return self.cd_name


@dataclass(frozen=True)
class Archive:
    """一份归档的完整结构事实。"""

    probe: ZipProbe
    entries: tuple[EntryView, ...]
    cd_actual_entries: int
    cd_span: tuple[int, int]
    zip64: bool


def _need(data: bytes, offset: int, size: int, reason: ReasonCode, what: str) -> None:
    if offset < 0 or offset + size > len(data):
        raise OracleError(
            reason,
            f"{what} 越界",
            {"offset": offset, "need": size, "size": len(data)},
        )


def _u16(data: bytes, offset: int, reason: ReasonCode, what: str) -> int:
    _need(data, offset, 2, reason, what)
    return struct.unpack_from("<H", data, offset)[0]


def _u32(data: bytes, offset: int, reason: ReasonCode, what: str) -> int:
    _need(data, offset, 4, reason, what)
    return struct.unpack_from("<I", data, offset)[0]


def _u64(data: bytes, offset: int, reason: ReasonCode, what: str) -> int:
    _need(data, offset, 8, reason, what)
    return struct.unpack_from("<Q", data, offset)[0]


def find_eocd(data: bytes) -> int:
    """返回 EOCD 记录起始偏移；找不到抛 `EOCD_NOT_FOUND`。

    从尾部向前扫（EOCD 后最多 65535 字节注释）。命中多个时取**最后一个**候选
    （与主流实现一致：注释里允许出现 `PK\\x05\\x06` 字节）。
    """

    if len(data) < EOCD_MIN_SIZE:
        raise OracleError(ReasonCode.EOCD_NOT_FOUND, "文件小于 EOCD 最小长度", {"size": len(data)})

    lowest = max(0, len(data) - EOCD_MIN_SIZE - EOCD_MAX_COMMENT)
    for offset in range(len(data) - EOCD_MIN_SIZE, lowest - 1, -1):
        if data[offset : offset + 4] == EOCD_SIG:
            comment_length = struct.unpack_from("<H", data, offset + 20)[0]
            # 记录必须"到文件尾恰好结束"（允许尾部垃圾时由 M2 的 CD 对账判断）。
            if offset + EOCD_MIN_SIZE + comment_length <= len(data):
                return offset
    raise OracleError(ReasonCode.EOCD_NOT_FOUND, "未找到 EOCD 记录")


def read_zip64_eocd(data: bytes, eocd_offset: int) -> tuple[int, int, int]:
    """读 ZIP64 EOCD 的 `(total_entries, cd_size, cd_offset)`。

    读不到就抛 `ZIP64_UNSUPPORTED`（退出码 3）——**不猜**：EOCD 里是 0xFFFF/0xFFFFFFFF
    说明真值在 ZIP64 记录里，缺失时按"声明值"读会把 65535 当真实条目数。
    """

    locator = eocd_offset - ZIP64_LOCATOR_SIZE
    if locator < 0 or data[locator : locator + 4] != ZIP64_LOCATOR_SIG:
        raise OracleError(
            ReasonCode.ZIP64_UNSUPPORTED,
            "EOCD 含 ZIP64 哨兵值，但未找到 ZIP64 EOCD 定位器",
            {"eocd_offset": eocd_offset},
        )
    z64_offset = _u64(data, locator + 8, ReasonCode.ZIP64_UNSUPPORTED, "ZIP64 locator")
    if data[z64_offset : z64_offset + 4] != ZIP64_EOCD_SIG:
        raise OracleError(
            ReasonCode.ZIP64_UNSUPPORTED,
            "ZIP64 EOCD 定位器指向的记录签名不符",
            {"zip64_eocd_offset": z64_offset},
        )
    _need(data, z64_offset, ZIP64_EOCD_MIN_SIZE, ReasonCode.ZIP64_UNSUPPORTED, "ZIP64 EOCD")
    total_entries = _u64(data, z64_offset + 32, ReasonCode.ZIP64_UNSUPPORTED, "ZIP64 EOCD")
    cd_size = _u64(data, z64_offset + 40, ReasonCode.ZIP64_UNSUPPORTED, "ZIP64 EOCD")
    cd_offset = _u64(data, z64_offset + 48, ReasonCode.ZIP64_UNSUPPORTED, "ZIP64 EOCD")
    return total_entries, cd_size, cd_offset


def _parse_extra(blob: bytes) -> tuple[ExtraField, ...]:
    """切分 extra field 为 `(id, data)` 序列。尾部不足 4 字节的残片**不解释也不丢**——
    它会被记成 id=0xFFFF 的伪字段吗？不会：那会编造一个 id。这里直接停止切分。"""

    fields: list[ExtraField] = []
    offset = 0
    while offset + 4 <= len(blob):
        field_id = struct.unpack_from("<H", blob, offset)[0]
        size = struct.unpack_from("<H", blob, offset + 2)[0]
        if offset + 4 + size > len(blob):
            break
        fields.append(ExtraField(field_id, blob[offset + 4 : offset + 4 + size]))
        offset += 4 + size
    return tuple(fields)


def parse_entries(data: bytes, cd_offset: int, cd_size: int) -> tuple[tuple[EntryView, ...], int]:
    """从 CD 偏移起逐条解析，返回 `(条目, 实际条目数)`。

    **按签名遍历，不按 EOCD 声明数遍历**——`CD_COUNT_MISMATCH` 的存在前提就是两者可以不等。
    """

    entries: list[EntryView] = []
    offset = cd_offset
    while offset + CD_MIN_SIZE <= len(data) and data[offset : offset + 4] == CD_SIG:
        flags = _u16(data, offset + 8, ReasonCode.CD_UNREADABLE, "CD flags")
        method = _u16(data, offset + 10, ReasonCode.CD_UNREADABLE, "CD method")
        crc = _u32(data, offset + 16, ReasonCode.CD_UNREADABLE, "CD crc")
        csize = _u32(data, offset + 20, ReasonCode.CD_UNREADABLE, "CD comp size")
        usize = _u32(data, offset + 24, ReasonCode.CD_UNREADABLE, "CD uncomp size")
        name_len = _u16(data, offset + 28, ReasonCode.CD_UNREADABLE, "CD name len")
        extra_len = _u16(data, offset + 30, ReasonCode.CD_UNREADABLE, "CD extra len")
        comment_len = _u16(data, offset + 32, ReasonCode.CD_UNREADABLE, "CD comment len")
        lfh_offset = _u32(data, offset + 42, ReasonCode.CD_UNREADABLE, "CD relative offset")

        record_len = CD_MIN_SIZE + name_len + extra_len + comment_len
        _need(data, offset, record_len, ReasonCode.CD_UNREADABLE, "CD 记录")
        cd_name = data[offset + CD_MIN_SIZE : offset + CD_MIN_SIZE + name_len]
        extra_start = offset + CD_MIN_SIZE + name_len
        cd_extra = _parse_extra(data[extra_start : extra_start + extra_len])

        lfh = _parse_lfh(data, lfh_offset)
        entries.append(
            EntryView(
                index=len(entries),
                lfh_offset=lfh_offset,
                lfh_end=lfh["end"],
                cd_offset=offset,
                lfh_name=lfh["name"],
                cd_name=cd_name,
                lfh_flags=lfh["flags"],
                cd_flags=flags,
                lfh_crc=lfh["crc"],
                cd_crc=crc,
                lfh_csize=lfh["csize"],
                cd_csize=csize,
                lfh_usize=lfh["usize"],
                cd_usize=usize,
                lfh_extra=lfh["extra"],
                cd_extra=cd_extra,
                method=method,
            )
        )
        offset += record_len

    return tuple(entries), len(entries)


def _parse_lfh(data: bytes, offset: int) -> dict:
    """解析一条 LFH。签名不符 = 输入不可解析（**不猜**、不降级成"没有 LFH"）。"""

    if data[offset : offset + 4] != LFH_SIG:
        raise OracleError(
            ReasonCode.LFH_UNREADABLE,
            "CD 指向的偏移处不是本地文件头",
            {"lfh_offset": offset, "found": data[offset : offset + 4].hex()},
        )
    _need(data, offset, LFH_MIN_SIZE, ReasonCode.LFH_UNREADABLE, "LFH 头")
    flags = _u16(data, offset + 6, ReasonCode.LFH_UNREADABLE, "LFH flags")
    method = _u16(data, offset + 8, ReasonCode.LFH_UNREADABLE, "LFH method")
    crc = _u32(data, offset + 14, ReasonCode.LFH_UNREADABLE, "LFH crc")
    csize = _u32(data, offset + 18, ReasonCode.LFH_UNREADABLE, "LFH comp size")
    usize = _u32(data, offset + 22, ReasonCode.LFH_UNREADABLE, "LFH uncomp size")
    name_len = _u16(data, offset + 26, ReasonCode.LFH_UNREADABLE, "LFH name len")
    extra_len = _u16(data, offset + 28, ReasonCode.LFH_UNREADABLE, "LFH extra len")

    _need(data, offset, LFH_MIN_SIZE + name_len + extra_len, ReasonCode.LFH_UNREADABLE, "LFH 名字与 extra")
    name = data[offset + LFH_MIN_SIZE : offset + LFH_MIN_SIZE + name_len]
    extra_start = offset + LFH_MIN_SIZE + name_len
    extra = _parse_extra(data[extra_start : extra_start + extra_len])
    end = extra_start + extra_len + csize
    _need(data, offset, end - offset, ReasonCode.LFH_UNREADABLE, "LFH 数据区")
    return {
        "flags": flags,
        "method": method,
        "crc": crc,
        "csize": csize,
        "usize": usize,
        "name": name,
        "extra": extra,
        "end": end,
    }


def read_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:  # 读不了 = 输入不可解析，绝不当成空结果
        raise OracleError(
            ReasonCode.INPUT_UNREADABLE,
            "归档读取失败",
            {"reason": exc.__class__.__name__},
        ) from exc


def probe(path: Path) -> ZipProbe:
    """只读探测一个归档的 EOCD 结构事实（M0 起的入口，保持不变）。"""

    data = read_bytes(path)
    eocd_offset = find_eocd(data)
    # EOCD 布局（偏移相对记录起点）：0 签名 / 4 disk / 6 cd_disk / 8 entries_this_disk /
    # 10 total_entries / 12 cd_size / 16 cd_offset / 20 comment_length
    entries_this_disk, total_entries, cd_size, cd_offset, comment_length = struct.unpack_from(
        "<HHIIH", data, eocd_offset + 8
    )
    del entries_this_disk  # 分卷归档不走检查路径；字段保留在字节层供对账
    return ZipProbe(
        archive_size=len(data),
        eocd_offset=eocd_offset,
        declared_entries=total_entries,
        declared_cd_size=cd_size,
        declared_cd_offset=cd_offset,
        comment_length=comment_length,
    )


def read_archive(path: Path) -> Archive:
    """三层完整解析（EOCD → CD → 每条 LFH）。这是 MOD-1/MOD-2 的唯一输入。"""

    data = read_bytes(path)
    eocd_offset = find_eocd(data)
    _entries_this_disk, total_entries, cd_size, cd_offset, comment_length = struct.unpack_from(
        "<HHIIH", data, eocd_offset + 8
    )

    zip64 = (
        total_entries == ZIP64_SENTINEL_16
        or cd_size == ZIP64_SENTINEL_32
        or cd_offset == ZIP64_SENTINEL_32
    )
    if zip64:
        total_entries, cd_size, cd_offset = read_zip64_eocd(data, eocd_offset)

    if cd_offset > len(data):
        raise OracleError(
            ReasonCode.CD_UNREADABLE,
            "EOCD 声明的 CD 偏移超出文件长度",
            {"cd_offset": cd_offset, "size": len(data)},
        )
    entries, actual = parse_entries(data, cd_offset, cd_size)

    facts = ZipProbe(
        archive_size=len(data),
        eocd_offset=eocd_offset,
        declared_entries=total_entries,
        declared_cd_size=cd_size,
        declared_cd_offset=cd_offset,
        comment_length=comment_length,
    )
    return Archive(
        probe=facts,
        entries=entries,
        cd_actual_entries=actual,
        cd_span=(cd_offset, cd_offset + cd_size),
        zip64=zip64,
    )


__all__ = [
    "CD_SIG",
    "EOCD_MIN_SIZE",
    "EOCD_SIG",
    "LFH_SIG",
    "Archive",
    "EntryView",
    "ExtraField",
    "ZipProbe",
    "find_eocd",
    "parse_entries",
    "probe",
    "read_archive",
    "read_bytes",
    "read_zip64_eocd",
]
