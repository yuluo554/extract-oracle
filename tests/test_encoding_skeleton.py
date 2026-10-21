"""MOD-2 **骨架**验收（M2 交付边界）：原始名字节 / bit 11 / extra fields。

`plan/HANDOFF-M2.md` §3 第 3 条："原始名字节 + bit 11 + extra fields 的解析（编码推断留 M5，
但**原始字节必须留**）"。因此本文件只断言**结构事实**，不断言任何"会写成什么名"的推断：

- 原始字节逐字节可逆（`raw_name_hex` ↔ 盘上字节）；
- bit 11 直接取自 CD flags；
- extra 切成 `(id, size)` 序列，`0x7075` 的 `version/name_crc32/utf8_name` 与 CRC 校验；
- `capabilities.encoding` 在 M2 **必须仍为 False**（骨架不冒充模块落地，K08）。
"""

from __future__ import annotations

from pathlib import Path

from extract_oracle.capabilities import MODULES
from extract_oracle.rules import encoding
from extract_oracle.zip_reader import read_archive

FIXTURES = Path(__file__).resolve().parent.parent / "data" / "fixtures"


def _names(name: str):
    return encoding.describe_all(read_archive(FIXTURES / name))


# ---------------------------------------------------------------- 原始字节必须留


def test_raw_name_bytes_are_preserved_verbatim():
    """GBK 名字的原始字节必须逐字节留（不解码、不替换、不丢）。"""

    facts = _names("zh_gbk.zip")[0]
    assert facts.raw_name_hex == "中文名.txt".encode("gbk").hex()
    assert facts.raw_name_length == len("中文名.txt".encode("gbk"))
    assert bytes.fromhex(facts.raw_name_hex) == "中文名.txt".encode("gbk")


def test_raw_bytes_roundtrip_on_every_fixture():
    """全部 22 份样本：`raw_name_hex` 解回字节 == 解析器给的 `cd_name`。"""

    for path in sorted(FIXTURES.iterdir()):
        if path.suffix not in {".zip", ".epub"}:
            continue
        archive = read_archive(path)
        for entry, facts in zip(archive.entries, encoding.describe_all(archive)):
            assert bytes.fromhex(facts.raw_name_hex) == entry.cd_name, path.name
            assert facts.entry_index == entry.index


# ---------------------------------------------------------------- bit 11


def test_bit11_is_read_from_cd_flags():
    assert _names("zh_gbk.zip")[0].bit11 is False
    assert _names("upath.zip")[0].bit11 is False
    # clean.zip 的两条都不置位
    assert [item.bit11 for item in _names("clean.zip")] == [False, False]
    # epub 的容器条目置位（生成器里 FLAG_UTF8）
    assert all(item.bit11 for item in _names("compressed.epub"))


def test_bit11_matches_raw_flag_bit():
    """与 `zip_reader` 给的 CD flags 逐位对上（防"另算一份 bit 11"）。"""

    archive = read_archive(FIXTURES / "alias_lfh.zip")
    entry = archive.entries[0]
    facts = encoding.describe(entry)
    assert facts.bit11 == bool(entry.cd_flags & 0x0800)
    # 该样本 CD 置位、LFH 未置位 → 骨架层要能同时看见两者（MOD-1 报 FLAG_DIVERGES）
    assert entry.lfh_flags & 0x0800 == 0


# ---------------------------------------------------------------- extra fields


def test_extra_fields_are_split_into_id_and_size():
    facts = _names("upath.zip")[0]
    assert encoding.UPATH_ID in facts.extra_ids
    assert facts.upath.present is True
    assert facts.upath.version == 1


def test_upath_crc_valid_when_computed_over_raw_name():
    facts = _names("upath.zip")[0]
    assert facts.upath.crc_valid is True
    assert facts.upath.utf8_name == "café.txt"


def test_upath_crc_invalid_is_recorded_not_hidden():
    """CRC 取反的样本：`crc_valid=False` 必须如实给出（M5 据此降级 + 报 finding）。"""

    facts = _names("upath_badcrc.zip")[0]
    assert facts.upath.present is True
    assert facts.upath.crc_valid is False
    # 字段里的 utf8 名字本身是可解的——失效的是 CRC 校验，不是解码
    assert facts.upath.utf8_name == "café.txt"


def test_absent_upath_is_present_false_not_none():
    """"字段不在"与"字段在但读不懂"是两件事，不能合并成同一个空值。"""

    facts = _names("clean.zip")[0]
    assert facts.upath.present is False
    assert facts.upath.crc_valid is None
    assert facts.extra_ids == ()


def test_extra_ids_are_carried_through_for_record_only_fields():
    """`0xCAFE`（测试用 extra）必须原样出现在 `extraIds` 里，不解释也不丢。"""

    facts = _names("extra.epub")
    mimetype = next(item for item in facts if item.raw_name_hex == b"mimetype".hex())
    assert 0xCAFE in mimetype.extra_ids


# ---------------------------------------------------------------- 骨架 → 落地（M5 翻转）


def test_encoding_module_is_implemented_since_m5():
    """K08：`implemented` 是 `check` 的唯一门。M5 起翻 True，验收靶子 = `tests/test_encoding.py`。

    M2 时期本文件断言它**仍是 False**（"骨架不冒充模块落地"）。M5 收尾把这条翻成正向断言：
    模块已落地，**且** `check()` 真的存在——两条一起断，防"只改 flag 不写实现"。
    """

    module = next(item for item in MODULES if item.name == "encoding")
    assert module.implemented is True
    assert callable(getattr(encoding, "check", None)), "encoding 落地后必须提供 check()"


def test_candidate_order_is_registered_and_used():
    """候选顺序登记在 `data/README.md` §4.4（K02）；M5 起它真的决定候选与胜出顺序。"""

    assert encoding.CANDIDATE_ENCODINGS == ("UTF-8", "CP437", "GBK", "CP932", "CP949", "CP1251")
    facts = _names("zh_gbk.zip")[0]
    # 结构事实面（`describe`）仍不产出推断字段——推断只在 `check()` 的返回块里
    assert not hasattr(facts, "candidates"), "describe() 只给结构事实，候选列表在 check() 的块里"
    # 推断面：候选按 K02 顺序
    block = encoding.check(read_archive(FIXTURES / "zh_gbk.zip"))[1]
    order = [item["encoding"] for item in block[0]["candidates"]]
    assert order == [name for name in encoding.CANDIDATE_ENCODINGS if name in order]
