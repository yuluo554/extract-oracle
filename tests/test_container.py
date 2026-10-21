"""M5 验收：MOD-5 容器约定（`container.*` 五条）。

覆盖 `plan/HANDOFF-M5.md` §3 第 2 条与 §6 第三项：

1. 四个 mimetype fixture 各命中**恰好一个** code，且**互不串报**；
2. `clean.zip` 零误报（容器识别为 `none` → 不做容器检查）；
3. `MIMETYPE_PADDING` 在 ODF 上下文带 `inferred: true`（EPUB 上下文不带）；
4. `UTF8_REQUIRED` 只对非纯 ASCII 的 bit-11-未置位条目报（纯 ASCII 报它 = 假阳性）。

ODF 上下文没有入仓 fixture（`data/README.md` §3.2 的 22 份里没有 ODF 样本），所以那一条用
生成器的 `build_zip` 在**临时目录**现造（同 `tests/test_accessibility.py` 的手法，不污染 fixture 目录）。

口径一律引用 `data/README.md` §4.5 / §4.13，本文不写第二份数值表述。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from extract_oracle.capabilities import MODULES
from extract_oracle.cli import main
from extract_oracle.exit_codes import ExitCode
from extract_oracle.rules import container as container_rules
from extract_oracle.zip_reader import read_archive

REPO = Path(__file__).resolve().parent.parent
FIXTURES = REPO / "data" / "fixtures"
TRUTH = FIXTURES / "truth"

sys.path.insert(0, str(REPO / "tools"))

import gen_fixtures  # noqa: E402


def _check(name: str):
    return container_rules.check(read_archive(FIXTURES / name))


def _codes(name: str) -> list[str]:
    return [item.rule_id for item in _check(name)[0]]


def _truth(name: str) -> dict:
    return json.loads((TRUTH / f"{name}.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------------ 能力门（K08）


def test_container_module_is_implemented():
    """`capabilities.container` 已翻 True——本文件与 `tests/test_budget.py` 是它的验收靶子。"""

    module = next(item for item in MODULES if item.name == "container")
    assert module.implemented is True
    assert module.rule_prefix == "container.* / budget.*"


def test_code_vocabulary_is_the_frozen_five():
    """五条 `container.*` 是封闭词表（`data/README.md` §4.5）。"""

    assert container_rules.CONTAINER_CODES == (
        "container.MIMETYPE_NOT_FIRST",
        "container.MIMETYPE_COMPRESSED",
        "container.MIMETYPE_EXTRA",
        "container.MIMETYPE_PADDING",
        "container.UTF8_REQUIRED",
    )
    assert container_rules.KINDS == ("epub", "odf", "none")


# ------------------------------------------------------------------ 四个 mimetype fixture


@pytest.mark.parametrize(
    "fixture, code",
    [
        ("not_first.epub", "container.MIMETYPE_NOT_FIRST"),
        ("compressed.epub", "container.MIMETYPE_COMPRESSED"),
        ("extra.epub", "container.MIMETYPE_EXTRA"),
        ("padding.epub", "container.MIMETYPE_PADDING"),
    ],
)
def test_each_mimetype_fixture_hits_exactly_one_code(fixture: str, code: str):
    """四份样本各命中**恰好一个** code（互不串报）——`plan/03` §MOD-5 验收行。"""

    findings, kind = _check(fixture)
    assert kind == {"kind": "epub"}
    assert [item.rule_id for item in findings] == [code]
    # 真值认领同一个 code（真值与判定不许各说各话）
    assert _truth(fixture)["expected_findings"] == [code]


def test_mimetype_findings_carry_a_documented_precedent():
    """`precedent` 只能取本模块的枚举（每条规则一个出处，`docs/rules.md` §二）。"""

    for fixture in ("not_first.epub", "compressed.epub", "extra.epub", "padding.epub"):
        for item in _check(fixture)[0]:
            assert item.precedent in container_rules.PRECEDENTS, (fixture, item.precedent)


def test_not_first_reports_the_actual_and_expected_index():
    """`MIMETYPE_NOT_FIRST` 的证据要能直接看出"第几条、期望第几条"。"""

    item = _check("not_first.epub")[0][0]
    assert item.evidence["expectedIndex"] == 0
    assert item.evidence["actualIndex"] == 1
    assert item.evidence["firstEntryName"] == "META-INF/container.xml"


def test_compressed_reports_method_and_expected_method():
    """`MIMETYPE_COMPRESSED` 的证据要给出实际 method 与期望 method（stored）。"""

    item = _check("compressed.epub")[0][0]
    assert item.evidence["method"] == 8
    assert item.evidence["expectedMethod"] == 0
    assert item.evidence["encrypted"] is False


def test_extra_reports_the_offending_field_ids():
    """`MIMETYPE_EXTRA` 的证据要给出实际的 extra id（0xCAFE 是生成器放进去的那个）。"""

    item = _check("extra.epub")[0][0]
    assert item.evidence["extraIds"] == [0xCAFE]


def test_padding_in_epub_context_is_not_inferred():
    """EPUB 3.3 §4.3.3 **明文**禁止 padding → `inferred: false`（不是推断，是原句）。"""

    item = _check("padding.epub")[0][0]
    assert item.evidence["inferred"] is False
    assert item.evidence["evidence_strength"] == "measured"
    assert item.evidence["trailingBytes"] == 1
    assert item.precedent == "epub_ocf_zip_requirements"


# ------------------------------------------------------------------ 零误报基线


def test_clean_zip_is_not_a_container_and_has_no_container_findings():
    """零误报基线：普通 ZIP 没有 `mimetype` → 识别为 `none` → 一条都不报。"""

    findings, kind = _check("clean.zip")
    assert kind == {"kind": "none"}
    assert findings == ()


def test_no_fixture_outside_the_mimetype_family_reports_container_codes():
    """反向：`container.*` 只许出现在容器样本上（防"每份归档都被当成容器查"）。"""

    container_fixtures = {"not_first.epub", "compressed.epub", "extra.epub", "padding.epub"}
    for path in sorted(FIXTURES.iterdir()):
        if path.suffix not in {".zip", ".epub"} or path.name in container_fixtures:
            continue
        findings, _kind = container_rules.check(read_archive(path))
        assert [item.rule_id for item in findings] == [], path.name


# ------------------------------------------------------------------ ODF 上下文（inferred）


def _odf(tmp_path: Path, *, padding: bool = False) -> Path:
    """现造一份最小 ODF 包：`mimetype` 排首、内容为 ODF media type（可选尾随换行）。"""

    content = b"application/vnd.oasis.opendocument.text" + (b"\n" if padding else b"")
    entries = [
        gen_fixtures.Entry(b"mimetype", content),
        gen_fixtures.Entry(b"META-INF/manifest.xml", b"<manifest/>\n"),
    ]
    path = tmp_path / "odf.odt"
    path.write_bytes(gen_fixtures.build_zip(entries))
    return path


def test_odf_kind_is_detected_from_the_media_type(tmp_path):
    """ODF 由 `mimetype` 内容的前缀识别（`application/vnd.oasis.opendocument.`）。"""

    findings, kind = container_rules.check(read_archive(_odf(tmp_path)))
    assert kind == {"kind": "odf"}
    assert findings == ()


def test_odf_padding_is_inferred_while_epub_padding_is_not(tmp_path):
    """同一条 `MIMETYPE_PADDING`：ODF 上下文 `inferred: true`，EPUB 上下文 `false`。

    这是 `docs/rules.md` #14 的落地形态——ODF 原文未明文禁止尾随换行，结论是**推出来的**，
    所以输出必须带 `inferred` 标记（`data/README.md` §4.7 的 `inferred` 枚举）。
    """

    findings, kind = container_rules.check(read_archive(_odf(tmp_path, padding=True)))
    assert kind == {"kind": "odf"}
    assert [item.rule_id for item in findings] == ["container.MIMETYPE_PADDING"]
    only = findings[0]
    assert only.evidence["inferred"] is True
    assert only.evidence["evidence_strength"] == "inferred"
    assert only.precedent == "odf_padding_inferred"

    epub = _check("padding.epub")[0][0]
    assert epub.evidence["inferred"] is False
    assert epub.precedent != only.precedent


# ------------------------------------------------------------------ UTF8_REQUIRED


def test_utf8_required_only_fires_for_non_ascii_names_without_bit11(tmp_path):
    """`UTF8_REQUIRED`：容器要求 UTF-8 但 bit 11 未置位，**且**名字非纯 ASCII。

    纯 ASCII 在 UTF-8 与 CP437 下同形——对它们报这条是假阳性，判据里明确排除。
    """

    # bit 11 未置位 + GBK 名字 → 报
    bad = tmp_path / "bad.epub"
    bad.write_bytes(
        gen_fixtures.build_zip(
            [
                gen_fixtures.Entry(b"mimetype", b"application/epub+zip"),
                gen_fixtures.Entry("中文.xhtml".encode("gbk"), b"<html/>\n"),
            ]
        )
    )
    findings, kind = container_rules.check(read_archive(bad))
    assert kind == {"kind": "epub"}
    assert [item.rule_id for item in findings] == ["container.UTF8_REQUIRED"]
    only = findings[0]
    assert only.evidence["bit11"] is False
    assert only.evidence["expectedBit11"] is True
    assert only.precedent in container_rules.PRECEDENTS

    # bit 11 未置位但名字是纯 ASCII → 不报（同形，报了就是假阳性）
    plain = tmp_path / "plain.epub"
    plain.write_bytes(
        gen_fixtures.build_zip(
            [
                gen_fixtures.Entry(b"mimetype", b"application/epub+zip"),
                gen_fixtures.Entry(b"plain.xhtml", b"<html/>\n"),
            ]
        )
    )
    findings, _kind = container_rules.check(read_archive(plain))
    assert findings == ()


def test_utf8_required_is_not_reported_for_odf(tmp_path):
    """`UTF8_REQUIRED` 的依据是 EPUB 3.3 §4.3.2（OCF）——ODF 上下文不套用它。"""

    findings, kind = container_rules.check(read_archive(_odf(tmp_path, padding=True)))
    assert kind == {"kind": "odf"}
    assert "container.UTF8_REQUIRED" not in [item.rule_id for item in findings]


# ------------------------------------------------------------------ 命令行面


def test_container_block_is_null_outside_module_scope(capsys):
    """`container` 块只在本次 `--module` 范围含 `container` 时出现（同 §4.11 的纪律）。"""

    main(["check", str(FIXTURES / "padding.epub"), "--target", "windows", "--module", "structure"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["container"] is None


def test_container_module_reports_kind_and_findings(capsys):
    """`--module container` 的交付态面：`kind` + 五条 finding 的机读形状。"""

    code = main(
        ["check", str(FIXTURES / "not_first.epub"), "--target", "windows", "--module", "container"]
    )
    assert code == int(ExitCode.FINDINGS)
    payload = json.loads(capsys.readouterr().out)
    assert payload["modules"] == ["container"]
    assert payload["container"] == {"kind": "epub"}
    assert [item["ruleId"] for item in payload["findings"]] == ["container.MIMETYPE_NOT_FIRST"]


def test_clean_zip_returns_zero_under_container_module(capsys):
    """零误报基线（CLI 面）：`clean.zip` 在 `container` 模块下退 0。"""

    code = main(
        ["check", str(FIXTURES / "clean.zip"), "--target", "windows", "--module", "container"]
    )
    assert code == int(ExitCode.OK)
    payload = json.loads(capsys.readouterr().out)
    assert payload["findings"] == []
    assert payload["container"] == {"kind": "none"}