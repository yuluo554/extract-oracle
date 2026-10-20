"""最小 ZIP 字节读取层（M2 起扩展为完整解析器）。

骨架期只做**只读的结构探测**，且只用于 `inspect` 子命令（结构事实，不是判定）。
纪律：任何按名字/标志做**判定**的逻辑都在 MOD-1…MOD-5，不在本模块。

不产生任何解压产物：本模块只 `seek`/`read` 字节。
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


@dataclass(frozen=True)
class ZipProbe:
    """EOCD 层的结构事实。字段名与后续报告 schema 对齐，M2 只做加法。"""

    archive_size: int
    eocd_offset: int
    declared_entries: int
    declared_cd_size: int
    declared_cd_offset: int
    comment_length: int


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


def probe(path: Path) -> ZipProbe:
    """只读探测一个归档的 EOCD 结构事实。"""

    try:
        data = path.read_bytes()
    except OSError as exc:  # 读不了 = 输入不可解析，绝不当成空结果
        raise OracleError(
            ReasonCode.INPUT_UNREADABLE,
            "归档读取失败",
            {"reason": exc.__class__.__name__},
        ) from exc

    eocd_offset = find_eocd(data)
    # EOCD 布局（偏移相对记录起点）：0 签名 / 4 disk / 6 cd_disk / 8 entries_this_disk /
    # 10 total_entries / 12 cd_size / 16 cd_offset / 20 comment_length
    entries_this_disk, total_entries, cd_size, cd_offset, comment_length = struct.unpack_from(
        "<HHIIH", data, eocd_offset + 8
    )
    del entries_this_disk  # 分卷归档不走检查路径；字段保留在字节层供 M2 对账
    return ZipProbe(
        archive_size=len(data),
        eocd_offset=eocd_offset,
        declared_entries=total_entries,
        declared_cd_size=cd_size,
        declared_cd_offset=cd_offset,
        comment_length=comment_length,
    )


__all__ = ["ZipProbe", "find_eocd", "probe"]
