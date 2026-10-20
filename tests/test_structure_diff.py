"""MOD-1 验收：六个 fixture 各命中对应 `structure.*`，`clean.zip` 零误报。

`plan/03` §MOD-1 验收清单的逐条落地。这里断言的是**判定层**（纯函数 + 结构事实），
不是 CLI 文案；CLI 面另由 `tests/test_cli_contract.py` 与 `tests/test_tool_behaviour.py` 管。

三条硬约束的守门也在这里：
- 不得引"规范要求 LFH/CD 一致" → `precedent` 只能取 `PRECEDENTS` 枚举；
- 不得用 casefold 近似 → 本模块不出现 `casefold`/`lower()`（AST 守门另有 `test_rule_boundaries.py`）；
- 零误报基线 → `clean.zip` 空 findings（`plan/01` §2 模块⑤）。
"""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from extract_oracle.rules import structure
from extract_oracle.zip_reader import read_archive

FIXTURES = Path(__file__).resolve().parent.parent / "data" / "fixtures"


def _findings(name: str):
    return structure.check(read_archive(FIXTURES / name))


def _rule_ids(name: str) -> list[str]:
    return [item.rule_id for item in _findings(name)]


# ---------------------------------------------------------------- 六个 fixture 的验收


def test_mismatch_name_reports_exactly_one_name_diverge():
    findings = _findings("mismatch_name.zip")
    assert [item.rule_id for item in findings] == ["structure.NAME_DIVERGES"]
    only = findings[0]
    assert only.lfh_name == "allowed.txt"
    assert only.cd_name == "evil.txt"
    assert only.evidence["lfhNameHex"] == b"allowed.txt".hex()
    assert only.evidence["cdNameHex"] == b"evil.txt".hex()
    # 分歧方向：读哪个头由实现选择决定（不得写成"规范要求一致"）
    assert only.evidence["readers"]["libarchive"] == "lfh"
    assert only.evidence["readers"]["info-zip-unzip"] == "cd"


def test_alias_lfh_reports_flag_diverge_with_bit_11():
    findings = _findings("alias_lfh.zip")
    assert [item.rule_id for item in findings] == ["structure.FLAG_DIVERGES"]
    only = findings[0]
    assert only.evidence["lfhFlags"] == 0x0000
    assert only.evidence["cdFlags"] == 0x0800
    assert only.evidence["differingBits"] == [11]


def test_overlap_reports_one_lfh_overlap_with_two_spans():
    findings = _findings("overlap.zip")
    assert [item.rule_id for item in findings] == ["structure.LFH_OVERLAP"]
    evidence = findings[0].evidence
    first, second = evidence["first"], evidence["second"]
    assert first["start"] == 0
    # 第二条 LFH 的起点落在第一条的区间内部（不是相邻）
    assert first["start"] < second["start"] < first["end"]


def test_wrong_count_reports_declared_vs_actual():
    findings = _findings("wrong_count.zip")
    assert [item.rule_id for item in findings] == ["structure.CD_COUNT_MISMATCH"]
    evidence = findings[0].evidence
    assert evidence["declared"] == 5
    assert evidence["actual"] == 2
    # 归档级 finding：没有单一条目可归属
    assert findings[0].entry_index is None
    assert findings[0].cd_offset is None


def test_crc_diverge_reports_one_crc_diverge():
    findings = _findings("crc_diverge.zip")
    assert [item.rule_id for item in findings] == ["structure.CRC_DIVERGES"]
    evidence = findings[0].evidence
    assert evidence["cdCrc"] == evidence["lfhCrc"] ^ 0x1
    assert evidence["dataDescriptor"] is False


def test_size_diverge_reports_one_size_diverge():
    findings = _findings("size_diverge.zip")
    assert [item.rule_id for item in findings] == ["structure.SIZE_DIVERGES"]
    evidence = findings[0].evidence
    assert evidence["cdUncompSize"] == evidence["lfhUncompSize"] + 7
    assert evidence["lfhCompSize"] == evidence["cdCompSize"]


def test_clean_zip_is_zero_finding_baseline():
    """零误报基线（`plan/01` §2 模块⑤）：完全正常的归档不得产出任何 `structure.*`。"""

    assert _findings("clean.zip") == ()


# ---------------------------------------------------------------- 误报控制


def test_no_fixture_reports_a_rule_it_was_not_built_for():
    """串报控制：22 份样本里只有 6 份该命中 `structure.*`，且各只命中自己那一条。

    这条防的是"规则太松"——例如把 LFH/CD 名字比较写成解码后比较，`norm.zip` 就会假命中。
    """

    expected = {
        "mismatch_name.zip": ["structure.NAME_DIVERGES"],
        "alias_lfh.zip": ["structure.FLAG_DIVERGES"],
        "overlap.zip": ["structure.LFH_OVERLAP"],
        "wrong_count.zip": ["structure.CD_COUNT_MISMATCH"],
        "crc_diverge.zip": ["structure.CRC_DIVERGES"],
        "size_diverge.zip": ["structure.SIZE_DIVERGES"],
    }
    seen: dict[str, list[str]] = {}
    for path in sorted(FIXTURES.iterdir()):
        if path.suffix not in {".zip", ".epub"}:
            continue
        rules = [item.rule_id for item in structure.check(read_archive(path))]
        if rules:
            seen[path.name] = rules
    assert seen == expected


def test_data_descriptor_exempts_crc_and_size():
    """bit 3 置位 **且** LFH 该字段为 0 → 豁免（合法写法，不是分歧）。

    没有这条豁免，任何"CRC 写在 descriptor 里"的正常归档都会被判成 `CRC_DIVERGES`。
    """

    data = _zip_with_lfh_overrides(flags=structure.FLAG_DATA_DESCRIPTOR, lfh_crc=0, lfh_csize=0, lfh_usize=0)
    archive = _archive_from_bytes(data)
    assert structure.check(archive) == ()


def test_bit3_with_nonzero_lfh_value_still_reports():
    """反向对照：bit 3 置位但 LFH 值**非 0** → 仍要报（豁免只针对"先写 0"这一种合法形态）。"""

    data = _zip_with_lfh_overrides(flags=structure.FLAG_DATA_DESCRIPTOR, lfh_crc=0xDEADBEEF, lfh_csize=0, lfh_usize=0)
    rules = [item.rule_id for item in structure.check(_archive_from_bytes(data))]
    assert "structure.CRC_DIVERGES" in rules


def test_adjacent_records_are_not_overlap():
    """相邻不算相交：`next.start == prev.end` 必须判**不**相交（否则零误报基线当场破）。"""

    assert "structure.LFH_OVERLAP" not in _rule_ids("clean.zip")


def test_overlap_evidence_uses_half_open_intervals():
    """区间是 `[start, end)`：end 恰为下一条起点时不算重叠——用 clean.zip 的两条钉住。"""

    archive = read_archive(FIXTURES / "clean.zip")
    first, second = archive.entries
    assert first.lfh_end == second.lfh_offset


# ---------------------------------------------------------------- 依据纪律


def test_every_finding_carries_a_precedent_from_the_enum():
    """`precedent` 必填且只能取实现选择枚举（`plan/03` §MOD-1 依据纪律）。"""

    for name in (
        "mismatch_name.zip",
        "alias_lfh.zip",
        "overlap.zip",
        "wrong_count.zip",
        "crc_diverge.zip",
        "size_diverge.zip",
    ):
        for finding in _findings(name):
            assert finding.precedent in structure.PRECEDENTS, f"{name}: {finding.precedent!r}"


def test_precedent_matches_the_rule_that_produced_it():
    """按规则固定 `precedent`——防"归错因"（M2 实测：重叠/计数原本被填成工具读头）。

    重叠与计数不是"读哪个头"的问题：前者是物理区间自证、后者是 EOCD 字段定义。
    把它们归到 `*_reads_cd` 是错误归因，与"不得编造条文"同一条纪律。
    """

    expected = {
        "structure.NAME_DIVERGES": "libarchive_reads_lfh",
        "structure.CRC_DIVERGES": "libarchive_reads_lfh",
        "structure.SIZE_DIVERGES": "libarchive_reads_lfh",
        "structure.FLAG_DIVERGES": "unzip_reads_cd",
        "structure.LFH_OVERLAP": "structural_self_evidence",
        "structure.CD_COUNT_MISMATCH": "structural_self_evidence",
    }
    for name in (
        "mismatch_name.zip",
        "alias_lfh.zip",
        "overlap.zip",
        "wrong_count.zip",
        "crc_diverge.zip",
        "size_diverge.zip",
    ):
        for finding in _findings(name):
            assert finding.precedent == expected[finding.rule_id], (
                f"{finding.rule_id} 的 precedent 应为 {expected[finding.rule_id]!r}"
            )


def test_structural_self_evidence_is_not_used_for_header_rules():
    """反向：结构自证这个取值**只**给重叠与计数，不得被用来搪塞名字/CRC/大小/flag 四条。"""

    header_rules = {
        "structure.NAME_DIVERGES",
        "structure.CRC_DIVERGES",
        "structure.SIZE_DIVERGES",
        "structure.FLAG_DIVERGES",
    }
    for name in ("mismatch_name.zip", "crc_diverge.zip", "size_diverge.zip", "alias_lfh.zip"):
        for finding in _findings(name):
            assert finding.rule_id in header_rules
            assert finding.precedent != "structural_self_evidence", finding.rule_id


def test_no_finding_claims_the_spec_requires_lfh_cd_agreement():
    """禁令（`plan/00` 决策 ⑤）：不得写"规范要求 LFH 与 CD 一致"——规范没有这句话。

    判据落在**输出的全部字符串**上：message / precedent / evidence 的键与值。
    """

    banned = ("规范要求", "spec requires", "must be identical", "SHOULD match")
    for name in ("mismatch_name.zip", "alias_lfh.zip", "overlap.zip", "wrong_count.zip"):
        for finding in _findings(name):
            blob = repr(finding.to_dict())
            for phrase in banned:
                assert phrase not in blob, f"{name} 含禁用表述: {phrase}"


# ---------------------------------------------------------------- 排序（K09）


def test_findings_sorted_by_cd_offset_then_rule_id():
    from extract_oracle.findings import sort_key

    keys = [sort_key(item) for item in _findings("mismatch_name.zip")]
    assert keys == sorted(keys)


# ---------------------------------------------------------------- ZIP64 路径


def test_zip64_sentinel_without_record_is_capability_missing(tmp_path):
    """声明 0xFFFF 却读不到 ZIP64 EOCD → `zip64_unsupported`（退出码 3），**不猜**。"""

    from extract_oracle.errors import OracleError, ReasonCode

    path = tmp_path / "z64.zip"
    path.write_bytes(_zip_with_declared_entries(0xFFFF))
    with pytest.raises(OracleError) as exc:
        read_archive(path)
    assert exc.value.code == ReasonCode.ZIP64_UNSUPPORTED
    assert exc.value.exit_code == 3


# ---------------------------------------------------------------- 构造助手


def _zip_with_declared_entries(declared: int) -> bytes:
    """一条 stored 条目 + EOCD 声明任意条目数。"""

    name = b"a.txt"
    payload = b"PAYLOAD-A\n"
    import zlib

    crc = zlib.crc32(payload) & 0xFFFFFFFF
    lfh = struct.pack(
        "<IHHHHHIIIHH", 0x04034B50, 20, 0, 0, 0x0000, 0x0021, crc, len(payload), len(payload), len(name), 0
    ) + name + payload
    cd_start = len(lfh)
    cd = struct.pack(
        "<IHHHHHHIIIHHHHHII",
        0x02014B50, 20, 20, 0, 0, 0x0000, 0x0021, crc, len(payload), len(payload), len(name), 0, 0, 0, 0, 0, 0
    ) + name
    eocd = struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, declared, declared, len(cd), cd_start, 0)
    return lfh + cd + eocd


def _zip_with_lfh_overrides(*, flags: int, lfh_crc: int, lfh_csize: int, lfh_usize: int) -> bytes:
    """CD 正常、LFH 的 flags/CRC/大小按参数写（构造 data descriptor 场景）。"""

    import zlib

    name = b"dd.txt"
    payload = b"PAYLOAD-DD\n"
    crc = zlib.crc32(payload) & 0xFFFFFFFF
    lfh = struct.pack(
        "<IHHHHHIIIHH", 0x04034B50, 20, flags, 0, 0x0000, 0x0021, lfh_crc, lfh_csize, lfh_usize, len(name), 0
    ) + name + payload
    cd_start = len(lfh)
    cd = struct.pack(
        "<IHHHHHHIIIHHHHHII",
        0x02014B50, 20, 20, flags, 0, 0x0000, 0x0021, crc, len(payload), len(payload), len(name), 0, 0, 0, 0, 0, 0
    ) + name
    eocd = struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, 1, 1, len(cd), cd_start, 0)
    return lfh + cd + eocd


def _archive_from_bytes(data: bytes):
    """把内存字节写成临时文件再走真实解析路径（不绕过 `read_archive`）。"""

    import tempfile

    handle = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    try:
        handle.write(data)
        handle.close()
        return read_archive(Path(handle.name))
    finally:
        Path(handle.name).unlink(missing_ok=True)
