"""M5 验收：MOD-2 收尾（编码推断 + 0x7075 全量 + `predictedNames`）。

覆盖 `plan/HANDOFF-M5.md` §3 第 1 条与 §6 的前两条：

1. `candidates[]` + `predictedNames`（候选顺序按 K02，置信度按 `data/README.md` §4.4）；
2. `0x7075`：CRC 有效 → 覆盖 + `high`；失配 → 失效 + 降级 `low` + `encoding.UPATH_CRC_MISMATCH`；
3. `zh_gbk.zip` 三提取器预测互不相同；`upath.zip` 四工具一致 `café.txt`；`upath_badcrc.zip` 四方分歧；
4. 预测与 `data/tool-matrix/` 的**实测格**逐格对账（作用域边界见 `data/README.md` §4.12）。

口径一律引用 `data/README.md` §4.4 / §4.12，本文不写第二份数值表述。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from extract_oracle.capabilities import MODULES
from extract_oracle.rules import encoding
from extract_oracle.zip_reader import read_archive

REPO = Path(__file__).resolve().parent.parent
FIXTURES = REPO / "data" / "fixtures"
TRUTH = FIXTURES / "truth"
MATRIX = REPO / "data" / "tool-matrix"


def _block(name: str) -> list[dict]:
    return encoding.check(read_archive(FIXTURES / name))[1]


def _findings(name: str) -> list:
    return list(encoding.check(read_archive(FIXTURES / name))[0])


def _truth(name: str) -> dict:
    return json.loads((TRUTH / f"{name}.json").read_text(encoding="utf-8"))


def _matrix(name: str) -> dict:
    return json.loads((MATRIX / f"{name}.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------------ 能力门（K08）


def test_encoding_module_is_implemented():
    """`capabilities.encoding` 已翻 True——本文件就是它的验收靶子（同提交，K08）。"""

    module = next(item for item in MODULES if item.name == "encoding")
    assert module.implemented is True
    assert callable(encoding.check)


# ------------------------------------------------------------------ 候选顺序与置信度


def test_candidate_order_is_the_frozen_one():
    """K02：候选顺序固定 `UTF-8 / CP437 / GBK / CP932 / CP949 / CP1251`，报告里也按它排。"""

    assert encoding.CANDIDATE_ENCODINGS == ("UTF-8", "CP437", "GBK", "CP932", "CP949", "CP1251")
    order = [item["encoding"] for item in _block("zh_gbk.zip")[0]["candidates"]]
    assert order == [name for name in encoding.CANDIDATE_ENCODINGS if name in order]


def test_undecodable_candidates_are_absent_not_listed_as_low():
    """误报控制：解不全的候选**不出现**在列表里（不是列出来标 `low`）。"""

    # zh_gbk 的字节在 UTF-8 与 CP932 下都解不全 → 两个都不在候选里
    encodings = {item["encoding"] for item in _block("zh_gbk.zip")[0]["candidates"]}
    assert "UTF-8" not in encodings
    assert "CP932" not in encodings
    # 而 CP437 / GBK 这两项是真在的（它们都解全了）
    assert {"CP437", "GBK"} <= encodings


def test_confidence_high_when_bit11_set():
    """`high` 的来源之一是 bit 11 置位（APPNOTE D.2 的 MUST）。"""

    block = _block("compressed.epub")
    assert all(item["bit11"] for item in block)
    assert {item["confidence"] for item in block} == {"high"}


def test_confidence_medium_needs_common_zone():
    """`medium` = 胜出候选解全且全部落在常用字区；CP437 解 GBK 字节落到框线 → 不算常用字区。"""

    item = _block("zh_gbk.zip")[0]
    assert item["preferred"] == "GBK"
    assert item["confidence"] == "medium"
    by_encoding = {entry["encoding"]: entry for entry in item["candidates"]}
    assert by_encoding["GBK"]["commonZone"] is True
    assert by_encoding["CP437"]["commonZone"] is False  # 框线字符（S*）不算常用字区


def test_common_zone_judgement_uses_unicode_categories():
    """常用字区判据只用 `unicodedata` 类别，不做大小写/规范化变换（K10 的实质靶子）。"""

    assert encoding.is_common_zone("alpha.txt") is True
    assert encoding.is_common_zone("中文名.txt") is True
    assert encoding.is_common_zone("имя.txt") is True
    assert encoding.is_common_zone("╓╨╬─├√.txt") is False  # 框线 + √
    assert encoding.is_common_zone("bad\x07name") is False  # 控制字符


def test_double_byte_candidates_outrank_single_byte_ones():
    """§4.4 第 2 条：双字节候选"解全"本身是强证据；单字节对任意字节都成立。

    `candidates[]` 保持 K02 顺序（它是"候选集合"，不是"排名"）；排名落在 `preferred` 上。
    GBK 排在 CP437/CP1251 **之后**，却赢下 `preferred`——这正是"强弱结构"在起作用的证据。
    """

    item = _block("zh_gbk.zip")[0]
    listed = [entry["encoding"] for entry in item["candidates"]]
    assert listed == [name for name in encoding.CANDIDATE_ENCODINGS if name in listed]
    assert listed.index("CP437") < listed.index("GBK")  # 候选列表按 K02
    assert item["preferred"] == "GBK"  # 但排名按"强结构优先"
    strengths = {entry["encoding"]: entry["strongStructure"] for entry in item["candidates"]}
    assert strengths["GBK"] is True and strengths["CP437"] is False and strengths["CP1251"] is False


# ------------------------------------------------------------------ 0x7075 两种结局


def test_upath_valid_crc_overrides_and_is_high():
    """CRC 有效 → 覆盖生效、`confidence = high`、四工具一致写出 `café.txt`。"""

    item = _block("upath.zip")[0]
    assert item["upath"]["present"] is True
    assert item["upath"]["crc_valid"] is True
    assert item["confidence"] == "high"
    assert item["effectiveName"] == "café.txt"
    names = {tool: rec["name"] for tool, rec in item["predictedNames"].items()}
    assert set(names) == set(encoding.EXTRACTORS)
    assert set(names.values()) == {"café.txt"}
    assert all(rec["rule"] == "upath_override" for rec in item["predictedNames"].values())
    assert _findings("upath.zip") == []


def test_upath_crc_mismatch_downgrades_and_reports():
    """CRC 失配 → 覆盖失效、降级 `low`、输出 `encoding.UPATH_CRC_MISMATCH`（唯一一条 finding）。"""

    item = _block("upath_badcrc.zip")[0]
    assert item["upath"]["present"] is True
    assert item["upath"]["crc_valid"] is False
    assert item["confidence"] == "low"
    # 覆盖失效 → `effectiveName` 回到候选胜出者（不是 0x7075 里的 café.txt）
    assert item["effectiveName"] == "中文名.txt"

    findings = _findings("upath_badcrc.zip")
    assert [item.rule_id for item in findings] == ["encoding.UPATH_CRC_MISMATCH"]
    only = findings[0]
    assert only.precedent in encoding.PRECEDENTS
    assert only.evidence["nameCrc32"] != only.evidence["expectedCrc32"]
    assert only.evidence["downgradedTo"] == "low"
    # 覆盖失效不等于"把 0x7075 丢掉不看"——字段本身仍如实给出
    assert only.evidence["utf8Name"] == "café.txt"
    assert item["upath"]["utf8_name"] == "café.txt"


def test_upath_absent_is_not_the_same_as_crc_invalid():
    """"字段不在"（`present=False`, `crc_valid=None`）与"字段在但失配"是两件事。"""

    absent = _block("zh_gbk.zip")[0]["upath"]
    assert absent == {
        "present": False,
        "version": None,
        "name_crc32": None,
        "utf8_name": None,
        "crc_valid": None,
    }
    present = _block("upath_badcrc.zip")[0]["upath"]
    assert present["present"] is True and present["crc_valid"] is False


def test_upath_crc_is_computed_over_raw_name_bytes():
    """`NameCRC32` 的校验对象是**条目原名字节**（APPNOTE 6.3.10 D.6），不是 utf8_name。"""

    archive = read_archive(FIXTURES / "upath.zip")
    entry = archive.entries[0]
    assert encoding.expected_name_crc(entry) == encoding.parse_upath(entry).name_crc32


# ------------------------------------------------------------------ 三份编码 fixture 的预测


def test_zh_gbk_three_extractors_predict_differently():
    """`zh_gbk.zip`：三提取器（python/unzip/7zip）预测**互不相同**（`plan/03` §MOD-2 验收）。"""

    item = _block("zh_gbk.zip")[0]
    names = {tool: rec["name"] for tool, rec in item["predictedNames"].items()}
    assert names["python-zipfile"] == "╓╨╬─├√.txt"  # CP437 回退
    assert names["info-zip-unzip"] == "Íð+-+¹.txt"  # 实测的 OEM 路径
    assert names["7zip"] == names["libarchive"] == "中文名.txt"  # 声明的 ANSI 码页（GBK）
    assert len({names["python-zipfile"], names["info-zip-unzip"], names["7zip"]}) == 3


def test_upath_four_tools_agree_on_cafe():
    """`upath.zip`：0x7075 CRC 有效 → 四工具一致 `café.txt`（`plan/05` §五 U14）。"""

    names = {
        tool: rec["name"] for tool, rec in _block("upath.zip")[0]["predictedNames"].items()
    }
    assert len(set(names.values())) == 1
    assert set(names.values()) == {"café.txt"}


def test_upath_badcrc_four_way_divergence():
    """`upath_badcrc.zip`：覆盖失效 → 四方分歧（CP437 两种 + GBK 两种）。"""

    names = {
        tool: rec["name"] for tool, rec in _block("upath_badcrc.zip")[0]["predictedNames"].items()
    }
    assert names["python-zipfile"] == "╓╨╬─├√.txt"
    assert names["info-zip-unzip"] == "Íð+-+¹.txt"
    assert names["7zip"] == names["libarchive"] == "中文名.txt"
    # 四个工具**不是**同一个名字（这正是"四方分歧"的意思）
    assert len(set(names.values())) == 3
    assert names["python-zipfile"] != names["info-zip-unzip"] != names["7zip"]


@pytest.mark.parametrize("fixture", ["zh_gbk.zip", "upath.zip", "upath_badcrc.zip"])
def test_predictions_match_the_documented_truth(fixture: str):
    """真值里写了 `expected_encoding` / `expected_names` 的，逐字段对账（不只看条数）。"""

    truth = _truth(fixture)
    item = _block(fixture)[0]
    expected_encoding = truth["expected_encoding"]
    assert item["bit11"] == expected_encoding["bit11"]
    if "confidence" in expected_encoding:
        assert item["confidence"] == expected_encoding["confidence"]
    if "preferred" in expected_encoding:
        assert item["preferred"] == expected_encoding["preferred"]
    if "candidates_include" in expected_encoding:
        got = {entry["encoding"] for entry in item["candidates"]}
        assert set(expected_encoding["candidates_include"]) <= got
    if "upath" in expected_encoding:
        for key, want in expected_encoding["upath"].items():
            assert item["upath"][key] == want, key
    if "expected_names" in truth:
        for tool, want in truth["expected_names"].items():
            assert item["predictedNames"][tool]["name"] == want, tool


# ------------------------------------------------------------------ 与四工具实测逐格对账


def _matrix_cells(name: str) -> dict:
    return _matrix(name)["cells"]


@pytest.mark.parametrize(
    "fixture",
    [
        # 单条目样本：预测是"一对一"，可以直接逐格对账（作用域见 §4.12）
        "zh_gbk.zip",
        "upath.zip",
        "upath_badcrc.zip",
        "alias_lfh.zip",
        "crc_diverge.zip",
        "size_diverge.zip",
        "long_path.zip",
    ],
)
def test_single_entry_decode_layer_matches_the_measured_matrix(fixture: str):
    """逐格对账：单条目且两头的名字一致时，预测必须等于实测落盘名（作用域见 §4.12）。

    带平台改写的样本（`reserved` / `trailing` / `trim`）不在这里——它们的落盘名经过
    "保留名加前缀 / 裁剪 / 冒号截断"，那是 `accessibility` 与 `collision` 的领域。
    """

    archive = read_archive(FIXTURES / fixture)
    assert len(archive.entries) == 1, f"{fixture} 不是单条目样本（参数表要跟着改）"
    entry = archive.entries[0]
    assert entry.lfh_name == entry.cd_name, f"{fixture} 两头名字不一致（属 MOD-1，不是编码层）"
    predicted = _block(fixture)[0]["predictedNames"]
    compared = 0
    for tool, cell in _matrix_cells(fixture).items():
        if cell.get("status") != "ok":
            continue  # 拒绝/失败的原因不在编码层（预算 / 双头不一致 / 越界）
        written = [item for item in (cell.get("written") or []) if not item.endswith("/")]
        if not written:
            continue
        assert predicted[tool]["name"] == written[0], (fixture, tool)
        compared += 1
    assert compared >= 1, f"{fixture} 一格都没比到（判据空跑）"


@pytest.mark.parametrize(
    "fixture",
    [
        "clean.zip",
        "norm.zip",
        "wrong_count.zip",
        "overlap.zip",
        "not_first.epub",
        "compressed.epub",
        "extra.epub",
        "padding.epub",
    ],
)
def test_multi_entry_decode_layer_matches_the_measured_matrix_as_a_set(fixture: str):
    """多条目样本：预测的每个名字都必须在实测落盘名里（落盘名之间没有一对一关系）。

    只挑**没有平台改写、没有折叠冲突**的多条目样本：`case.zip`（后写覆盖只剩一个名字）、
    `reserved`/`trailing`/`trim`（`_` 前缀、冒号替换、尾随裁剪）都不在这里——§4.12 已写明
    那是 `accessibility`/`collision` 的领域。
    """

    archive = read_archive(FIXTURES / fixture)
    assert len(archive.entries) > 1
    predicted = _block(fixture)
    assert len(predicted) == len(archive.entries)
    compared = 0
    for tool, cell in _matrix_cells(fixture).items():
        if cell.get("status") != "ok":
            continue
        written = {item for item in (cell.get("written") or []) if not item.endswith("/")}
        if not written:
            continue
        for record in predicted:
            name = record["predictedNames"][tool]["name"]
            if name is None:
                continue
            assert name in written, (fixture, tool, name, sorted(written))
        compared += 1
    assert compared >= 1, f"{fixture} 一格都没比到（判据空跑）"


def test_prediction_level_is_decode_only():
    """诚实边界：`predictedNames` **不**包含 7-Zip 的 `_` 前缀这类平台改写。

    实测格 `reserved.zip` 的 7-Zip 落盘名带下划线前缀，而预测给的是解码层的结果
    （`CON.txt`）。把这条写成断言而不是注释，是因为"预测"与"实测"的分工一旦含糊，
    下一个里程碑很容易把平台改写塞进编码层。
    """

    cell = _matrix_cells("reserved.zip")["7zip"]
    assert "_CON.txt" in cell["written"]
    predicted = _block("reserved.zip")
    names = [item["predictedNames"]["7zip"]["name"] for item in predicted]
    assert "CON.txt" in names  # 解码层的结果（平台改写由 accessibility 负责）
    assert "_CON.txt" not in names


def test_predictions_never_fabricate_a_name():
    """不可解码时给 `null` + `reason`，不编造替代名（`plan/03` §MOD-2 误报控制）。

    构造两条"边界"输入（直接调用，不经归档）：

    - `0xff`：声明码页（GBK）解不全，且候选胜出者也不给（`chosen=None`）→
      `7zip`/`libarchive` 必须给 `null` + `reason`，而不是拿 CP437 的结果冒充；
    - `b""`：**空名字是能解出来的**（解出空串），所以它给 `""` 而不是 `null`——
      "不知道"（解码失败）与"知道会是空名"（解码成功但结果为空的非法名）是两件事，
      后者由 `accessibility` 判 `BLOCKED`。

    另外两条路径（`python` 的 CP437、`unzip` 的 CP850）是**全函数**（对所有字节都成立），
    所以它们照常给出名字。
    """

    assert encoding.preferred([]) is None
    assert encoding.decode(b"\xff", encoding.ANSI_CODEC) is None  # 前提：GBK 在这条字节上真失败

    predictions = encoding.predict_names(b"\xff", False, encoding.UpathField(present=False), None)
    assert set(predictions) == set(encoding.EXTRACTORS)
    for tool in ("7zip", "libarchive"):
        assert predictions[tool]["name"] is None, tool
        assert predictions[tool]["rule"] == "undecodable"
        assert predictions[tool]["reason"] == "no_complete_candidate"
    assert predictions["python-zipfile"]["name"] is not None
    assert predictions["info-zip-unzip"]["name"] is not None

    empty = encoding.predict_names(b"", False, encoding.UpathField(present=False), None)
    for tool in encoding.EXTRACTORS:
        assert empty[tool]["name"] == "", tool


def test_oem_transliteration_table_is_charwise_only():
    """`CP850_TRANSLITERATION`（实测表）只做字符替换，不改变大小写（K10）。"""

    assert set(encoding.CP850_TRANSLITERATION.values()) <= {
        "",
        "i",
        "+",
        "-",
        "_",
        "=",
        "\u00a6",
        "\u00af",
        "\x83",
    }
    for key, value in encoding.CP850_TRANSLITERATION.items():
        assert len(key) == 1
        # 值里不得出现"另一个字母"这种大小写近似（`i` 是实测量的 best-fit，不是 `.lower()`）
        assert value.lower() == value if value.isalpha() else True


def test_check_block_is_sorted_by_entry_index():
    """报告块按 `entryIndex` 升序（与 `entries[]` 同序，便于对读）。"""

    for name in ("clean.zip", "norm.zip", "case.zip"):
        block = _block(name)
        indexes = [item["entryIndex"] for item in block]
        assert indexes == sorted(indexes)
        assert indexes == [entry.index for entry in read_archive(FIXTURES / name).entries]


def test_low_confidence_count_helper():
    """`count_low_confidence` 是 `summary.low_confidence_count` 的来源（§4.12 末）。"""

    assert encoding.count_low_confidence(_block("upath_badcrc.zip")) == 1
    assert encoding.count_low_confidence(_block("zh_gbk.zip")) == 0