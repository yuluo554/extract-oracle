"""CLI 契约：退出码语义、能力门、机读错误行。

这里的断言是 K07/K08 的守门（`plan/05` §六）——改动退出码或能力门必须让本文件先红。
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from extract_oracle import __version__
from extract_oracle.capabilities import MODULES, missing_core
from extract_oracle.cli import main
from extract_oracle.errors import EXIT_FOR_REASON, ReasonCode
from extract_oracle.exit_codes import ExitCode

FIXTURES = Path(__file__).resolve().parent.parent / "data" / "fixtures"


def test_version_single_source():
    """版本号单一真源：`pyproject` 声明 dynamic，值来自根模块 `__version__`。

    第三条断言（产物自报）在 `scripts/build.py`。这里不依赖"包已安装"——
    干净 clone 里先跑测试也必须成立。
    """

    pyproject = (Path(__file__).resolve().parent.parent / "pyproject.toml").read_text(encoding="utf-8")
    assert 'dynamic = ["version"]' in pyproject, "版本必须在 pyproject 里声明为 dynamic"
    assert 'version = { attr = "extract_oracle.__version__" }' in pyproject
    # 反向：pyproject 里不得出现手写的第二份 version 字面量
    assert not re.search(r'^version\s*=\s*"', pyproject, re.M), "pyproject 不得手写 version 字面量"

    recorded = Path(__file__).resolve().parent.parent / "src" / "extract_oracle" / "__init__.py"
    assert f'__version__ = "{__version__}"' in recorded.read_text(encoding="utf-8")


def test_usage_error_maps_to_4(capsys):
    assert main(["check", str(FIXTURES / "clean.zip")]) == int(ExitCode.USAGE_ERROR)
    payload = json.loads(capsys.readouterr().err.strip())
    assert payload["error"] == ReasonCode.USAGE_ERROR.value
    assert payload["exit_code"] == int(ExitCode.USAGE_ERROR)


def test_unknown_target_rejected():
    assert main(["check", str(FIXTURES / "clean.zip"), "--target", "amiga"]) == int(
        ExitCode.USAGE_ERROR
    )


def test_missing_archive_is_input_unreadable(tmp_path, capsys):
    missing = tmp_path / "nope.zip"
    assert main(["inspect", str(missing)]) == int(ExitCode.INPUT_UNREADABLE)
    payload = json.loads(capsys.readouterr().err.strip())
    assert payload["error"] == ReasonCode.INPUT_UNREADABLE.value


def test_non_zip_is_input_unreadable(tmp_path, capsys):
    junk = tmp_path / "junk.bin"
    junk.write_bytes(b"not a zip at all" * 10)
    assert main(["inspect", str(junk)]) == int(ExitCode.INPUT_UNREADABLE)
    payload = json.loads(capsys.readouterr().err.strip())
    assert payload["error"] == ReasonCode.EOCD_NOT_FOUND.value


def test_check_refuses_while_modules_missing(capsys):
    """最坏的一种假绿：空 findings + 退出码 0。骨架期必须显式拒绝。"""

    if not missing_core():  # pragma: no cover - M5 之后此分支才会走到
        pytest.skip("五模块已全部落地，本断言不再适用（应由 findings 断言接管）")
    code = main(["check", str(FIXTURES / "clean.zip"), "--target", "windows"])
    assert code == int(ExitCode.CAPABILITY_MISSING)
    captured = capsys.readouterr()
    assert captured.out == ""  # stdout 不产出半份报告
    payload = json.loads(captured.err.strip())
    assert payload["error"] == ReasonCode.CAPABILITY_MISSING.value
    assert set(payload["detail"]["missing_modules"]) == set(missing_core())


def test_capabilities_reports_all_modules(capsys):
    assert main(["capabilities"]) == int(ExitCode.OK)
    out = capsys.readouterr().out
    for module in MODULES:
        assert module.name in out


def test_platforms_verify_reports_missing_table():
    assert main(["platforms", "--verify"]) == int(ExitCode.CAPABILITY_MISSING)


def test_platforms_without_verify_is_usage_error():
    assert main(["platforms"]) == int(ExitCode.USAGE_ERROR)


def test_inspect_reports_eocd_facts(capsys):
    assert main(["inspect", str(FIXTURES / "clean.zip"), "--format", "json"]) == int(ExitCode.OK)
    payload = json.loads(capsys.readouterr().out)
    assert payload["eocd"]["declared_entries"] == 2
    assert payload["findings"] == []
    assert payload["command"] == "inspect"


def test_multi_target_forms_are_equivalent():
    """README 的 `--target windows,macos` 与重复旗标必须等价（parser 反射对账的一半）。"""

    from extract_oracle.cli import _parse_targets

    assert _parse_targets(["windows,macos"]) == _parse_targets(["windows", "macos"]) == [
        "windows",
        "macos",
    ]


def test_exit_code_table_is_total():
    """`reason → code` 映射必须是全函数（新增 reason 不补映射即红）。"""

    for reason in ReasonCode:
        assert reason in EXIT_FOR_REASON, f"{reason} 未登记退出码"


def test_exception_is_not_silently_zero():
    """任何 reason 的退出码都不得是 0（'我做不了'绝不能退化成 '没发现问题'）。"""

    for reason, code in EXIT_FOR_REASON.items():
        assert code != ExitCode.OK, f"{reason} 映射到了 0"


def test_module_entry_point_runs(tmp_path):
    """`python -m extract_oracle` 通路（与 console script 是两条通路，都要验）。"""

    env = {"PYTHONPATH": str(Path(__file__).resolve().parent.parent / "src"), "PYTHONUTF8": "1"}
    proc = subprocess.run(
        [sys.executable, "-m", "extract_oracle", "inspect", str(FIXTURES / "clean.zip"), "--format", "json"],
        capture_output=True,
        text=True,
        env={**env},
        cwd=str(tmp_path),
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["eocd"]["declared_entries"] == 2