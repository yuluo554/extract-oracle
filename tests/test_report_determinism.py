"""确定性导出（K03/K09）：同输入双跑逐字节一致，且不含本机路径。"""

from __future__ import annotations

import re
from pathlib import Path

from extract_oracle.report import SCHEMA_VERSION, dumps_json, render_text, write_atomic

FIXTURE = Path(__file__).resolve().parent.parent / "data" / "fixtures" / "clean.zip"

PAYLOAD = {
    "tool_version": "0.1.0",
    "schema_version": SCHEMA_VERSION,
    "command": "check",
    "target": "windows",
    "findings": [
        {"ruleId": "structure.NAME_DIVERGES", "entryIndex": 0, "message": "m"},
        {"ruleId": "budget.PATH_OVER_260", "entryIndex": 1, "message": "n"},
    ],
    "summary": {"entry_count": 2, "finding_count": 2},
}


def test_json_dump_is_byte_stable():
    assert dumps_json(PAYLOAD) == dumps_json(dict(reversed(list(PAYLOAD.items()))))


def test_text_export_is_byte_stable():
    assert render_text(PAYLOAD) == render_text(PAYLOAD)


def test_export_has_no_host_path_and_no_timestamp():
    text = dumps_json(PAYLOAD)
    assert not re.search(r"\b[A-Za-z]:[\\/]", text), "输出里不得出现盘符绝对路径"
    assert "/home/" not in text and "/Users/" not in text
    assert not re.search(r"\b20\d{2}-\d{2}-\d{2}T\d{2}:", text), "输出里不得出现时间戳"


def test_export_is_lf_terminated_with_trailing_newline():
    text = dumps_json(PAYLOAD)
    assert "\r" not in text
    assert text.endswith("\n")


def test_chinese_is_not_ascii_escaped():
    payload = {**PAYLOAD, "note": "中文名"}
    assert "中文名" in dumps_json(payload)


def test_write_atomic_leaves_no_temp_file(tmp_path):
    """K03：写盘只经 report.write_atomic，且不留临时文件。"""

    out = tmp_path / "report.json"
    write_atomic(out, dumps_json(PAYLOAD))
    assert out.read_bytes() == dumps_json(PAYLOAD).encode("utf-8")
    leftovers = [p.name for p in tmp_path.iterdir() if p.name.startswith(".tmp-")]
    assert leftovers == []


def test_write_atomic_is_idempotent(tmp_path):
    out = tmp_path / "a" / "b" / "report.txt"
    write_atomic(out, "x\n")
    write_atomic(out, "x\n")
    assert out.read_text(encoding="utf-8") == "x\n"


# ---------------------------------------------------------------- M2 的新输出面


FIXTURES = Path(__file__).resolve().parent.parent / "data" / "fixtures"


def _run_json(argv: list[str]) -> tuple[int, str]:
    """跑一次 CLI，返回 `(退出码, stdout)`——不经过 capsys，方便双跑比对字节。"""

    import io
    import json
    from contextlib import redirect_stdout

    from extract_oracle.cli import main

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = main(argv)
    text = buffer.getvalue()
    json.loads(text)  # 必须是合法 JSON（半份报告会在这里炸）
    return code, text


def test_inspect_is_byte_identical_across_runs():
    """K09：同输入双跑逐字节一致——`inspect` 现在带 entries/names，面变大了，判据不变。"""

    first = _run_json(["inspect", str(FIXTURES / "upath.zip"), "--format", "json"])
    second = _run_json(["inspect", str(FIXTURES / "upath.zip"), "--format", "json"])
    assert first == second


def test_check_structure_is_byte_identical_across_runs():
    first = _run_json(
        ["check", str(FIXTURES / "overlap.zip"), "--target", "windows", "--module", "structure"]
    )
    second = _run_json(
        ["check", str(FIXTURES / "overlap.zip"), "--target", "windows", "--module", "structure"]
    )
    assert first == second


def test_m2_output_has_no_host_path_and_no_timestamp():
    """新输出面同样不得出现盘符路径 / 时间戳（K03 的常驻判据扩到 entries 与 findings）。"""

    for argv in (
        ["inspect", str(FIXTURES / "clean.zip"), "--format", "json"],
        ["check", str(FIXTURES / "mismatch_name.zip"), "--target", "windows", "--module", "structure"],
    ):
        _code, text = _run_json(argv)
        assert not re.search(r"\b[A-Za-z]:[\\/]", text), argv
        assert "/home/" not in text and "/Users/" not in text, argv
        assert not re.search(r"\b20\d{2}-\d{2}-\d{2}T\d{2}:", text), argv


def test_raw_name_bytes_survive_json_roundtrip():
    """非法 UTF-8 的原名字节必须能安全进 JSON（M2 把展示形从 surrogateescape 改成
    backslashreplace 的直接理由：surrogateescape 的孤立代理项在 `ensure_ascii=False`
    下无法编码为 UTF-8，写盘会抛 `UnicodeEncodeError`）。"""

    from extract_oracle.findings import display_name

    raw = b"bad\xffname.txt"
    shown = display_name(raw)
    payload = {"cdName": shown, "cdNameHex": raw.hex()}
    text = dumps_json(payload)
    text.encode("utf-8")  # 不得抛 UnicodeEncodeError
    assert bytes.fromhex(payload["cdNameHex"]) == raw  # 原始字节仍是唯一可靠来源


def test_findings_are_sorted_deterministically():
    """`findings` 按 `(cd_offset, ruleId)` 升序（`data/README.md` §4.8 的规范序）。"""

    import json

    _code, text = _run_json(
        ["check", str(FIXTURES / "wrong_count.zip"), "--target", "windows", "--module", "structure"]
    )
    findings = json.loads(text)["findings"]
    keys = [(item["cdOffset"] if item["cdOffset"] is not None else -1, item["ruleId"]) for item in findings]
    assert keys == sorted(keys)