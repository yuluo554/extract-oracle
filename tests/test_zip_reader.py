"""ZIP 字节层：EOCD 定位与结构事实（不含任何判定）。

这层只读字节、不写盘、不联网；`find_eocd` 的两个边界（注释里含签名字节 / 短文件）单独钉住。
"""

from __future__ import annotations

import struct

import pytest

from extract_oracle.errors import OracleError, ReasonCode
from extract_oracle.zip_reader import EOCD_MIN_SIZE, EOCD_SIG, find_eocd, probe


def _eocd(comment: bytes = b"", entries: int = 1) -> bytes:
    return (
        struct.pack(
            "<IHHHHIIH",
            int.from_bytes(EOCD_SIG, "little"),
            0,
            0,
            entries,
            entries,
            0,
            0,
            len(comment),
        )
        + comment
    )


def test_short_input_raises_eocd_not_found():
    with pytest.raises(OracleError) as exc:
        find_eocd(b"PK\x05\x06")
    assert exc.value.code == ReasonCode.EOCD_NOT_FOUND
    assert exc.value.exit_code == 2


def test_finds_eocd_at_zero_for_bare_record():
    assert find_eocd(_eocd()) == 0


def test_last_candidate_wins_when_comment_contains_signature():
    """注释里允许出现签名字节——必须取**最后一个**候选（与主流实现一致）。"""

    tricky = _eocd() + _eocd(comment=b"PK\x05\x06 inside comment")
    offset = find_eocd(tricky)
    assert offset == EOCD_MIN_SIZE
    assert tricky[offset : offset + 4] == EOCD_SIG


def test_inconsistent_comment_length_is_rejected():
    """声明了超长注释但文件没那么长 → 不是合法 EOCD，应继续向前找或报错。"""

    bogus = (
        struct.pack("<IHHHHIIH", int.from_bytes(EOCD_SIG, "little"), 0, 0, 1, 1, 0, 0, 0xFFFF)
        + b"short"
    )
    with pytest.raises(OracleError):
        find_eocd(bogus)


def test_probe_reads_declared_fields(tmp_path):
    fixture = _eocd(entries=7)
    path = tmp_path / "x.zip"
    path.write_bytes(fixture)
    facts = probe(path)
    assert facts.declared_entries == 7
    assert facts.archive_size == len(fixture)


def test_probe_missing_file_reports_unreadable(tmp_path):
    with pytest.raises(OracleError) as exc:
        probe(tmp_path / "nope.zip")
    assert exc.value.code == ReasonCode.INPUT_UNREADABLE