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