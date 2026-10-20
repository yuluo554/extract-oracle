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


def test_check_module_scope_refuses_unimplemented_module(capsys):
    """`--module` 是**收窄**不是**豁免**：点名一个没落地的模块照样退 3。"""

    unimplemented = [module.name for module in MODULES if not module.implemented]
    if not unimplemented:  # pragma: no cover
        pytest.skip("五模块已全部落地")
    code = main(
        ["check", str(FIXTURES / "clean.zip"), "--target", "windows", "--module", unimplemented[0]]
    )
    assert code == int(ExitCode.CAPABILITY_MISSING)
    captured = capsys.readouterr()
    assert captured.out == ""
    payload = json.loads(captured.err.strip())
    assert payload["detail"]["missing_modules"] == [unimplemented[0]]


def test_check_unknown_module_is_usage_error():
    assert main(["check", str(FIXTURES / "clean.zip"), "--target", "windows", "--module", "nope"]) == int(
        ExitCode.USAGE_ERROR
    )


def test_check_structure_module_reports_scope_and_findings(capsys):
    """`--module structure` 的报告必须写明**本次范围**（防"只跑一个模块"被读成"全查过"）。"""

    code = main(["check", str(FIXTURES / "mismatch_name.zip"), "--target", "windows", "--module", "structure"])
    assert code == int(ExitCode.FINDINGS)
    payload = json.loads(capsys.readouterr().out)
    assert payload["modules"] == ["structure"]
    assert [item["ruleId"] for item in payload["findings"]] == ["structure.NAME_DIVERGES"]
    assert payload["summary"]["finding_count"] == 1


def test_check_clean_archive_returns_zero_with_structure_module(capsys):
    """零误报基线的 CLI 面：无 finding 才允许退 0（`data/README.md` §4.1）。"""

    code = main(["check", str(FIXTURES / "clean.zip"), "--target", "windows", "--module", "structure"])
    assert code == int(ExitCode.OK)
    payload = json.loads(capsys.readouterr().out)
    assert payload["findings"] == []
    assert payload["summary"]["finding_count"] == 0


def test_check_module_forms_are_equivalent():
    from extract_oracle.cli import _parse_modules

    assert _parse_modules(["structure,fold"]) == _parse_modules(["structure", "fold"]) == [
        "structure",
        "fold",
    ]
    assert _parse_modules(None) is None


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


def test_inspect_reports_three_layers(capsys):
    """M2：`inspect` 必须给出 CD 层与每条 LFH 的结构事实（含 `lfhEnd`）。"""

    assert main(["inspect", str(FIXTURES / "clean.zip"), "--format", "json"]) == int(ExitCode.OK)
    payload = json.loads(capsys.readouterr().out)
    assert payload["cd"]["actual_entries"] == 2
    assert payload["cd"]["zip64"] is False
    entries = payload["entries"]
    assert [item["index"] for item in entries] == [0, 1]
    for item in entries:
        # LFH 三层完整化：起点、终点、CD 偏移、两侧 flags/CRC/大小都要在
        for key in (
            "lfhOffset",
            "lfhEnd",
            "cdOffset",
            "lfhFlags",
            "cdFlags",
            "lfhCrc",
            "cdCrc",
            "lfhCompSize",
            "cdCompSize",
            "lfhUncompSize",
            "cdUncompSize",
            "method",
        ):
            assert key in item, key
        assert item["lfhEnd"] > item["lfhOffset"]
        assert item["cdOffset"] >= item["lfhEnd"]
        # 原始字节与展示形都要在（原始字节是 MOD-2 的唯一可靠输入）
        assert bytes.fromhex(item["cdNameHex"]).decode() == item["cdName"]


def test_inspect_reports_name_layer_without_verdicts(capsys):
    """`inspect` 是结构事实：有 `names`（原始字节/bit11/extra），但 `findings` 恒空。"""

    assert main(["inspect", str(FIXTURES / "upath.zip"), "--format", "json"]) == int(ExitCode.OK)
    payload = json.loads(capsys.readouterr().out)
    assert payload["findings"] == []
    facts = payload["names"][0]
    assert facts["bit11"] is False
    assert facts["rawNameHex"] == "中文名.txt".encode("gbk").hex()
    assert facts["upath"]["present"] is True
    assert facts["upath"]["crc_valid"] is True


def test_inspect_does_not_produce_rule_ids(capsys):
    """`inspect` 不得产出任何 `ruleId`（`plan/00` D13：结构事实与判定不重叠）。"""

    for name in ("mismatch_name.zip", "overlap.zip", "wrong_count.zip"):
        main(["inspect", str(FIXTURES / name), "--format", "json"])
        payload = json.loads(capsys.readouterr().out)
        assert payload["findings"] == [], name
        assert "ruleId" not in json.dumps(payload)


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