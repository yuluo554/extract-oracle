"""CLI 契约：退出码语义、能力门、机读错误行。

这里的断言是 K07/K08 的守门（`plan/05` §六）——改动退出码或能力门必须让本文件先红。
"""

from __future__ import annotations

import json
import os
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


def test_check_with_no_missing_modules_reports_zero_on_clean_archive(capsys):
    """五模块齐备后，不带 `--module` 的 `check` 对干净归档必须**退 0 且三数组皆空**。

    M4 时这里还是"缺两模块 → 退 3"的拒绝断言，并在五模块齐备时 `pytest.skip`。跳过会变成
    静默假绿（`plan/HANDOFF-M5.md` §3 第 6 条），所以 M5 同提交改成**正向断言**：
    模块齐备了这个事实本身要被一条真跑过的输出证明，而不是"没跑到"。
    """

    assert missing_core() == [], "五模块应全部落地——本断言的前提"
    code = main(["check", str(FIXTURES / "clean.zip"), "--target", "windows"])
    captured = capsys.readouterr()
    assert code == int(ExitCode.OK), captured.err
    payload = json.loads(captured.out)
    assert payload["modules"] == [module.name for module in MODULES]
    assert payload["findings"] == []
    assert payload["collisions"] == []
    assert payload["summary"]["accessibility_count"] == 0
    # 三个判定产出之外的字段必须是"查过了"，不是 null（null = 没查）
    assert payload["encoding"] is not None
    assert payload["container"] is not None
    assert payload["summary"]["low_confidence_count"] is not None


def test_check_module_scope_refuses_unimplemented_module(capsys):
    """`--module` 是**收窄**不是**豁免**：点名的模块没落地照样退 3。

    M5 起五模块全落地，正常路径走不到这个分支了；判据仍在，用**注入**的方式证伪——
    临时把某个模块的 `implemented` 翻回 False，门必须重新变红。这样"能力门还在"这件事
    不依赖"恰好还剩一个没实现的模块"（那种依赖会在下一个里程碑消失）。
    """

    from extract_oracle import capabilities, cli

    original = capabilities.MODULES
    broken = tuple(
        capabilities.Capability(
            item.name, item.milestone, item.rule_prefix, implemented=False if index == 0 else item.implemented
        )
        for index, item in enumerate(original)
    )
    # 两处都要换：`miss` 读模块全局（调用时查），`cli` 在 import 时绑了名字。
    original_cli = cli.MODULES
    try:
        capabilities.MODULES = broken
        cli.MODULES = broken
        code = main(
            ["check", str(FIXTURES / "clean.zip"), "--target", "windows", "--module", broken[0].name]
        )
    finally:
        capabilities.MODULES = original
        cli.MODULES = original_cli

    assert code == int(ExitCode.CAPABILITY_MISSING)
    captured = capsys.readouterr()
    assert captured.out == ""
    payload = json.loads(captured.err.strip())
    assert payload["detail"]["missing_modules"] == [broken[0].name]


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


def test_platforms_verify_reports_fingerprint():
    """M3 起 `platforms --verify` 是真校验（表在位 → 0 + 表指纹）。

    "表缺 → 3" 的反向分支在 `tests/test_fold.py`（用 `--dir` 指向空目录 / 篡改表）。
    这里只钉住"占位退 3 已消失"与"输出里真有指纹"。
    """

    assert main(["platforms", "--verify"]) == int(ExitCode.OK)


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
        env={**os.environ, **env},
        cwd=str(tmp_path),
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["eocd"]["declared_entries"] == 2

def test_cli_output_is_utf8_even_when_host_console_cannot_encode_it(tmp_path):
    """`_configure_streams()` 的回归靶子：**伪造一个非 UTF-8 控制台**，输出仍必须是 UTF-8 且不崩。

    实测来源（M6 首推首跑）：产物在 CI 的 Windows runner（cp1252 控制台）上跑
    `platforms --verify`，报告里那张表带中文表标签，于是
    `UnicodeEncodeError: 'charmap' codec can't encode characters` —— **进程直接崩**。
    这不只是"显示不好看"：它让"报告的字节形态"取决于**宿主 locale**，与"同输入 → 同一输出"冲突。
    修复 = `cli._configure_streams()` 把 stdout/stderr 固定成 UTF-8 + LF + `backslashreplace`。

    这里用 `PYTHONIOENCODING=cp1252` **伪造**那个控制台（不看本机是什么控制台）——
    判别 = **"我这条断言，在某个平台上会不会恰好恒真？"**：本机控制台是 cp936（能编码中文），
    所以不伪造输入的话，这条断言在本机恒真、证明不了任何事。
    """

    env = {
        **os.environ,
        "PYTHONPATH": str(Path(__file__).resolve().parent.parent / "src"),
        "PYTHONUTF8": "0",  # 逼它走 locale 默认（而不是 UTF-8 模式）——这才是 CI 上的真实形态
        "PYTHONIOENCODING": "cp1252",
    }
    proc = subprocess.run(
        [sys.executable, "-m", "extract_oracle", "platforms", "--verify"],
        capture_output=True,
        env=env,
        cwd=str(tmp_path),
    )
    assert proc.returncode == 0, proc.stderr.decode("utf-8", errors="replace")
    text = proc.stdout.decode("utf-8")  # cp1252 的高位字节解不成 UTF-8 → 不修就会在这里炸
    assert "platform tables verified" in text and "ntfs_upcase" in text

    # 同一形态的第二处：`check` 的 JSON 面（`ensure_ascii=False`，条目名可能是中文）
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "extract_oracle",
            "check",
            str(FIXTURES / "zh_gbk.zip"),
            "--target",
            "windows",
            "--module",
            "encoding",
        ],
        capture_output=True,
        env=env,
        cwd=str(tmp_path),
    )
    assert proc.returncode == 0, proc.stderr.decode("utf-8", errors="replace")
    json.loads(proc.stdout.decode("utf-8"))  # 非 UTF-8 字节会在这里失败
    assert b"\r\n" not in proc.stdout, "报告换行必须是 LF（K09）"
