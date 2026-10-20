"""M4 验收：MOD-4 非法名与可访问性分级（K08 的靶子）。

覆盖 `plan/HANDOFF-M4.md` §3 / §6 的待办：

1. 三级分级 + `reasons[]` + `evidence[]`，分级顺序按 `data/README.md` §4.2；
2. `reserved.zip`：`CON.txt`/`NUL.txt` → `WRITTEN_UNREADABLE` 且**三证据齐**；`aux.tar.gz` → `OK`；
3. `trailing.zip`：`trailing. ` / `trailingdot.` / `colon:name.txt` → `WRITTEN_TRUNCATED`；
4. `trim.zip`：`readme.` → `WRITTEN_TRUNCATED`、`readme` → `OK`，且**仍触发** `collision.TRIM`；
5. `long_comp.zip` → `BLOCKED`；`clean.zip` 三平台全 `OK`（零误报基线）；
6. `entries[].accessibility` 进报告 + 三个 `--target` 各自可断言 + 退码含 accessibility。

口径一律引用 `data/README.md` §4.2 / §4.7，本文不写第二份数值表述。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from extract_oracle import platforms as platform_tables
from extract_oracle.capabilities import MODULES
from extract_oracle.cli import main
from extract_oracle.errors import ReasonCode
from extract_oracle.exit_codes import ExitCode
from extract_oracle.report import ACCESS_LEVELS
from extract_oracle.rules import access, fold
from extract_oracle.zip_reader import read_archive

REPO = Path(__file__).resolve().parent.parent
FIXTURES = REPO / "data" / "fixtures"
TRUTH = FIXTURES / "truth"
PLATFORM_DIR = REPO / "data" / "platforms"

sys.path.insert(0, str(REPO / "tools"))

import gen_fixtures  # noqa: E402


def _synthetic(tmp_path: Path, name: str, pairs: list[tuple[str, bytes]]) -> Path:
    """用生成器的 `build_zip` 现造样本（不落 fixture 目录，不碰真值）。"""

    entries = [gen_fixtures.Entry(item.encode("utf-8"), payload) for item, payload in pairs]
    path = tmp_path / name
    path.write_bytes(gen_fixtures.build_zip(entries))
    return path


@pytest.fixture(scope="module")
def tables():
    return platform_tables.load(PLATFORM_DIR)


def _verdicts(name: str, targets: list[str], tables) -> dict[int, dict[str, dict]]:
    return access.check(read_archive(FIXTURES / name), targets, tables)


def _levels(name: str, target: str, tables) -> dict[str, str]:
    archive = read_archive(FIXTURES / name)
    result = access.check(archive, [target], tables)
    return {
        archive.entries[index].cd_name.decode("utf-8", "surrogateescape"): per_platform[target][
            "level"
        ]
        for index, per_platform in result.items()
    }


# ------------------------------------------------------------------ 能力门（K08）


def test_accessibility_module_is_implemented():
    """`capabilities.accessibility` 已翻 True——本文件就是它的验收靶子（同提交，K08）。"""

    module = next(item for item in MODULES if item.name == "accessibility")
    assert module.implemented is True
    assert module.rule_prefix == "accessibility"


def test_accessibility_module_is_dispatchable_from_cli(capsys):
    """翻 True 之后 `--module accessibility` 必须真能跑（不是"翻了个没分派的门"）。"""

    assert main(
        ["check", str(FIXTURES / "clean.zip"), "--target", "windows", "--module", "accessibility"]
    ) == int(ExitCode.OK)
    payload = json.loads(capsys.readouterr().out)
    assert payload["modules"] == ["accessibility"]
    assert payload["collisions"] == []


def test_report_level_order_matches_rules():
    """`report.ACCESS_LEVELS` 与 `rules/access.LEVELS` 是同一份枚举（两处定义由本断言钉住）。"""

    assert ACCESS_LEVELS == access.LEVELS
    assert set(access.GRADES) == set(access.LEVELS) - {"OK"}


# ------------------------------------------------------------------ 三级定义与词表


def test_level_vocabulary_is_closed():
    """取值封闭：只能是 §4.2 的四个（`OK` 是取值但不是级别）。"""

    assert access.LEVELS == ("BLOCKED", "WRITTEN_UNREADABLE", "WRITTEN_TRUNCATED", "OK")
    assert access.GRADES == ("BLOCKED", "WRITTEN_UNREADABLE", "WRITTEN_TRUNCATED")


def test_evidence_tokens_are_closed_and_contain_the_three_measured_ones():
    """`CON.txt` 的三条实测证据必须在词表里（它们是第三级的**来源**，不是编的）。"""

    for token in ("test_path_false", "get_content_error", "open_readable"):
        assert token in access.EVIDENCE_TOKENS
    assert access.RESERVED_EVIDENCE == ("test_path_false", "get_content_error", "open_readable")


def test_judge_never_emits_unknown_reasons(tables):
    """所有 fixture × 三平台的 `reasons` / `evidence` 都落在封闭词表内。"""

    reason_tokens = set(access.REASON_TOKENS)
    evidence_tokens = set(access.EVIDENCE_TOKENS)
    scanned = 0
    for path in sorted(FIXTURES.iterdir()):
        if path.suffix not in {".zip", ".epub"}:
            continue
        result = access.check(read_archive(path), list(access.PLATFORMS), tables)
        for per_platform in result.values():
            for verdict in per_platform.values():
                assert set(verdict["reasons"]) <= reason_tokens, path.name
                assert set(verdict["evidence"]) <= evidence_tokens, path.name
                scanned += 1
    assert scanned >= 60, scanned  # 22 份样本 × 3 平台的下界（非空跑自证）


# ------------------------------------------------------------------ 分级顺序（§4.2 七步）


def test_ordering_blocked_wins_over_reserved_name(tables):
    """`BLOCKED` 先于保留名：`CON?.txt` 含非法字符 → `BLOCKED`，不是 `WRITTEN_UNREADABLE`。"""

    verdict = access.judge_name("CON?.txt", "windows", tables)
    assert verdict["level"] == "BLOCKED"
    assert "illegal_char" in verdict["reasons"]
    assert "reserved_device_name" not in verdict["reasons"]  # 先命中档的 reasons 归 BLOCKED


def test_ordering_unreadable_wins_over_truncation(tables):
    """保留名先于裁剪：`CON.txt ` 既是保留名又被裁剪 → `WRITTEN_UNREADABLE`（裁剪原因仍被记录）。

    本机实测支撑这条顺序：`CON.txt ` 落盘为 `CON.txt`，`Get-Content` 报错 → 更严重的那一档胜出。
    """

    verdict = access.judge_name("CON.txt ", "windows", tables)
    assert verdict["level"] == "WRITTEN_UNREADABLE"
    assert "reserved_device_name" in verdict["reasons"]
    assert "trailing_space_or_dot" in verdict["reasons"]  # 全收，不丢


def test_reserved_name_is_matched_after_trimming(tables):
    """裁剪后才是保留名的（`con.txt.` → `con.txt`）也判 `WRITTEN_UNREADABLE`（本机实测）。"""

    assert access.judge_name("con.txt.", "windows", tables)["level"] == "WRITTEN_UNREADABLE"
    assert access.judge_name("aux.tar.gz.", "windows", tables)["level"] == "WRITTEN_TRUNCATED"


def test_all_reasons_are_collected_not_short_circuited(tables):
    """同一档内多因同时命中时 `reasons` 全收（`a.:b.` 的尾随点 + 冒号）。"""

    verdict = access.judge_name("a.:b.", "windows", tables)
    assert verdict["level"] == "WRITTEN_TRUNCATED"
    assert set(verdict["reasons"]) == {"trailing_space_or_dot", "ads_colon_truncation"}


@pytest.mark.parametrize(
    "name,platform,level",
    [
        ("", "windows", "BLOCKED"),
        ("", "linux", "BLOCKED"),
        ("a//b", "windows", "BLOCKED"),
        ("a//b", "linux", "BLOCKED"),
        ("a/", "macos", "BLOCKED"),
        ("/a", "macos", "BLOCKED"),
        (".", "linux", "BLOCKED"),
        ("a/../b", "linux", "BLOCKED"),
        ("nul.txt ", "windows", "WRITTEN_UNREADABLE"),  # 裁掉尾随空格后就是保留名
        ("x\x00y", "windows", "BLOCKED"),
        ("a<b", "windows", "BLOCKED"),
        ("a|b", "windows", "BLOCKED"),
        ("a?b", "windows", "BLOCKED"),
        ("a*b", "windows", "BLOCKED"),
        ("a\tb", "windows", "BLOCKED"),
        ("CON.txt", "windows", "WRITTEN_UNREADABLE"),
        ("NUL.txt", "windows", "WRITTEN_UNREADABLE"),
        ("COM1.log", "windows", "WRITTEN_UNREADABLE"),
        ("CLOCK$", "windows", "WRITTEN_UNREADABLE"),
        ("aux.tar", "windows", "WRITTEN_UNREADABLE"),
        ("aux.tar.gz", "windows", "OK"),
        ("CON.txt", "linux", "OK"),  # Linux 无保留名概念（不猜 macOS 的 `:` 同理）
        ("trailing. ", "windows", "WRITTEN_TRUNCATED"),
        ("trailingdot.", "windows", "WRITTEN_TRUNCATED"),
        ("colon:name.txt", "windows", "WRITTEN_TRUNCATED"),
        ("alpha.txt", "windows", "OK"),
        ("dir/sub/name.txt", "windows", "OK"),  # `/` 是分隔符，不是非法字符
    ],
)
def test_grading_table(name, platform, level, tables):
    """§4.2 的判据逐格：一条断言一个名字，失败时能直接看出是哪一格。"""

    assert access.judge_name(name, platform, tables)["level"] == level


def test_reserved_name_match_is_by_last_dot_and_case_insensitive(tables):
    """保留名按**最后一个点之前**整体匹配，大小写无关（走真实 `$UpCase` 表）。"""

    assert access.judge_name("CON.txt", "windows", tables)["level"] == "WRITTEN_UNREADABLE"
    assert access.judge_name("con.txt", "windows", tables)["level"] == "WRITTEN_UNREADABLE"
    assert access.judge_name("AUX.txt", "windows", tables)["level"] == "WRITTEN_UNREADABLE"
    assert access.judge_name("AUX.tar.gz", "windows", tables)["level"] == "OK"
    assert access.judge_name("AUX.txt.txt", "windows", tables)["level"] == "OK"
    assert access.judge_name("AUX..txt", "windows", tables)["level"] == "OK"


def test_reserved_devices_include_zero_and_exclude_double_digits(tables):
    """`COM0`/`LPT0` 保留、`COM10` 起不保留——本机实测（`data/README.md` §4.2 修订）。"""

    assert {"COM0", "LPT0", "COM9", "LPT9"} <= access.RESERVED_DEVICE_NAMES
    assert "COM10" not in access.RESERVED_DEVICE_NAMES
    assert access.judge_name("COM0.txt", "windows", tables)["level"] == "WRITTEN_UNREADABLE"
    assert access.judge_name("COM10.txt", "windows", tables)["level"] == "OK"


def test_superscript_device_variants_are_ok_by_measurement(tables):
    """上标 ¹²³ 变体按**本机实测**判 `OK`（MS Learn 的 CMD 例子与 Win32 文件 API 不同）。

    MS Learn 说 `COM¹` 是设备名（`echo test > COM¹` 在 CMD 里失败）；但 `CreateFileW` 走
    Win32 文件命名空间，本机实测 `COM¹.txt` 创建成功、`Test-Path=True`、`Get-Content` 读得到。
    本工具预言的是提取器（走文件 API）的落盘结果，所以按实测判 `OK`——**不猜规范语气**。
    收窄理由记在 `data/README.md` §4.2 的 2026-10-21 修订。
    """

    for name in ("COM\u00b9.txt", "COM\u00b2.txt", "LPT\u00b3.log"):
        assert access.judge_name(name, "windows", tables)["level"] == "OK", name


def test_component_length_is_counted_in_utf16_units(tables):
    """组件上限按 UTF-16 码元（255 上限，256 就 `BLOCKED`）。"""

    assert access.judge_name("x" * 255, "windows", tables)["level"] == "OK"
    verdict = access.judge_name("x" * 256, "windows", tables)
    assert verdict["level"] == "BLOCKED"
    assert "component_too_long" in verdict["reasons"]
    # 非 BMP 字符算 2 个码元：128 个 emoji = 256 码元 → BLOCKED
    assert access.judge_name("\U0001f600" * 128, "windows", tables)["level"] == "BLOCKED"
    assert access.judge_name("\U0001f600" * 127, "windows", tables)["level"] == "OK"


# ------------------------------------------------------------------ 真值对账（逐 fixture）


def test_reserved_zip_matches_truth_with_three_evidence(tables):
    """`reserved.zip`：`CON.txt`/`NUL.txt` → `WRITTEN_UNREADABLE` 且**三证据齐**；`aux.tar.gz` → `OK`。"""

    expected = json.loads((TRUTH / "reserved.zip.json").read_text(encoding="utf-8"))[
        "expected_accessibility"
    ]["windows"]
    assert _levels("reserved.zip", "windows", tables) == expected

    result = _verdicts("reserved.zip", ["windows"], tables)
    for index, per_platform in result.items():
        verdict = per_platform["windows"]
        if verdict["level"] != "WRITTEN_UNREADABLE":
            continue
        assert verdict["evidence"] == list(access.RESERVED_EVIDENCE), index


def test_trailing_zip_matches_truth(tables):
    """`trailing.zip`：三条都 `WRITTEN_TRUNCATED`（含 `:` 的 ADS 截断）。"""

    expected = json.loads((TRUTH / "trailing.zip.json").read_text(encoding="utf-8"))[
        "expected_accessibility"
    ]["windows"]
    assert _levels("trailing.zip", "windows", tables) == expected

    result = _verdicts("trailing.zip", ["windows"], tables)
    reasons = {
        json.dumps(per_platform["windows"]["reasons"]): per_platform["windows"]["level"]
        for per_platform in result.values()
    }
    # 两个空格/点裁剪、一个冒号截断——两条不同 reason 都要出现
    assert any("trailing_space_or_dot" in key for key in reasons)
    assert any("ads_colon_truncation" in key for key in reasons)


def test_trim_zip_matches_truth_and_still_triggers_trim_collision(tables):
    """`trim.zip`：`readme.` → `WRITTEN_TRUNCATED`、`readme` → `OK`，且**仍触发** `collision.TRIM`。"""

    expected = json.loads((TRUTH / "trim.zip.json").read_text(encoding="utf-8"))[
        "expected_accessibility"
    ]["windows"]
    assert _levels("trim.zip", "windows", tables) == expected

    collisions = fold.check(read_archive(FIXTURES / "trim.zip"), ["windows"], tables)
    assert [item.code for item in collisions] == ["collision.TRIM"]


def test_long_comp_zip_is_blocked(tables):
    """`long_comp.zip` → `BLOCKED`（单组件 256 码元创建即失败，**不是**截断）。"""

    expected = json.loads((TRUTH / "long_comp.zip.json").read_text(encoding="utf-8"))[
        "expected_accessibility"
    ]["windows"]
    levels = _levels("long_comp.zip", "windows", tables)
    assert set(levels.values()) == set(expected.values()) == {"BLOCKED"}

    verdict = next(iter(_verdicts("long_comp.zip", ["windows"], tables).values()))["windows"]
    assert "component_too_long" in verdict["reasons"]


def test_clean_zip_is_ok_on_all_three_platforms(tables):
    """零误报基线：`clean.zip` 三平台全 `OK`（不得有 `BLOCKED`/`UNREADABLE`/`TRUNCATED`）。"""

    result = _verdicts("clean.zip", list(access.PLATFORMS), tables)
    for per_platform in result.values():
        for platform, verdict in per_platform.items():
            assert verdict["level"] == "OK", (platform, verdict)


def test_long_path_zip_is_ok_on_windows(tables):
    """`long_path.zip`：整路径 314 字节 > 260，但各组件 44 字节——**不是** `BLOCKED`。

    `data/README.md` §3.2：`budget.PATH_OVER_260` 是**可移植性预算告警**，不是本机截断事实
    （本机 `LongPathsEnabled=1` 可直接创建）。M4 只判可访问性，预算告警归 M5。
    """

    expected = json.loads((TRUTH / "long_path.zip.json").read_text(encoding="utf-8"))[
        "expected_accessibility"
    ]
    assert expected["windows"] == {}
    assert set(_levels("long_path.zip", "windows", tables).values()) == {"OK"}


def test_all_fixtures_match_declared_truth_per_platform(tables):
    """凡真值写了 `expected_accessibility` 的 fixture，逐名逐平台比对（不只看条数）。"""

    checked = 0
    for path in sorted(FIXTURES.glob("*.zip")):
        truth = json.loads((TRUTH / f"{path.name}.json").read_text(encoding="utf-8"))
        expected = truth.get("expected_accessibility")
        if not expected:
            continue
        assert set(expected) == set(access.PLATFORMS), f"{path.name} 真值缺平台键"
        for platform in access.PLATFORMS:
            got = _levels(path.name, platform, tables)
            if not expected[platform]:
                # 空 = "不得有任何一级"（`plan/04` §二 第 3 条）
                assert set(got.values()) == {"OK"}, (path.name, platform, got)
                continue
            for name, level in expected[platform].items():
                if name == "<long>":  # 超长名字不写进真值（避免 300 字符的行）
                    assert set(got.values()) == {level}, (path.name, platform)
                    continue
                assert got[name] == level, (path.name, platform, name, got)
        checked += 1
    assert checked >= 5, checked  # 五份真值（reserved/trailing/trim/long_comp/long_path）


# ------------------------------------------------------------------ 报告面


def test_entries_carry_accessibility_only_when_module_in_scope(capsys):
    """`entries[].accessibility` 进报告；`structure` 范围的报告**不带**这个键（范围要能分开看）。"""

    main(["check", str(FIXTURES / "reserved.zip"), "--target", "windows", "--module", "accessibility"])
    payload = json.loads(capsys.readouterr().out)
    for entry in payload["entries"]:
        assert "accessibility" in entry
        assert entry["accessibility"]["windows"]["level"] in access.LEVELS

    main(["check", str(FIXTURES / "reserved.zip"), "--target", "windows", "--module", "structure"])
    payload = json.loads(capsys.readouterr().out)
    for entry in payload["entries"]:
        assert "accessibility" not in entry


def test_inspect_never_reports_accessibility(capsys):
    """`inspect` 是结构事实，不产判定（`plan/00` D13）。"""

    main(["inspect", str(FIXTURES / "reserved.zip"), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)
    assert "accessibility" not in json.dumps(payload, sort_keys=True)


def test_targets_are_independently_assertable(capsys):
    """三个 `--target` 的结论各占一个平台键，能分开断言。"""

    assert main(
        [
            "check",
            str(FIXTURES / "reserved.zip"),
            "--target",
            "windows,linux",
            "--module",
            "accessibility",
        ]
    ) == int(ExitCode.FINDINGS)
    payload = json.loads(capsys.readouterr().out)
    assert payload["targets"] == ["windows", "linux"]
    levels = {entry["cdName"]: entry["accessibility"] for entry in payload["entries"]}
    assert levels["CON.txt"]["windows"]["level"] == "WRITTEN_UNREADABLE"
    assert levels["CON.txt"]["linux"]["level"] == "OK"  # Linux 侧不报 Windows 保留名
    assert "macos" not in levels["CON.txt"]  # 没点名的平台不出键


def test_summary_counts_are_per_level_and_match_entries(capsys):
    """`summary.accessibility_levels` 必须与 `entries[].accessibility` 逐级对得上。"""

    main(
        [
            "check",
            str(FIXTURES / "trailing.zip"),
            "--target",
            "windows",
            "--module",
            "accessibility",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    counted = {level: 0 for level in access.LEVELS}
    for entry in payload["entries"]:
        counted[entry["accessibility"]["windows"]["level"]] += 1
    assert payload["summary"]["accessibility_levels"] == counted
    assert payload["summary"]["accessibility_count"] == 3


def test_summary_accessibility_fields_are_null_outside_scope(capsys):
    """不在范围内时 `accessibility_levels` 为 `null`（不是 0——"没查"与"全 OK"是两件事）。"""

    main(["check", str(FIXTURES / "clean.zip"), "--target", "windows", "--module", "structure"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["accessibility_levels"] is None
    assert payload["summary"]["accessibility_count"] == 0


def test_exit_code_counts_accessibility_as_judgement_output(capsys):
    """§4.1：不可访问的条目是判定产出 → 退 1（即使没有 findings / collisions）。"""

    code = main(
        ["check", str(FIXTURES / "reserved.zip"), "--target", "windows", "--module", "accessibility"]
    )
    assert code == int(ExitCode.FINDINGS)
    payload = json.loads(capsys.readouterr().out)
    assert payload["findings"] == [] and payload["collisions"] == []
    assert payload["summary"]["accessibility_count"] == 2


def test_check_without_module_still_refuses_while_encoding_and_container_missing(capsys):
    """不给 `--module` = 要求五模块齐备；还剩两个 → 退 3（收窄 ≠ 豁免）。"""

    code = main(["check", str(FIXTURES / "clean.zip"), "--target", "windows"])
    assert code == int(ExitCode.CAPABILITY_MISSING)
    payload = json.loads(capsys.readouterr().err.strip())
    assert payload["error"] == ReasonCode.CAPABILITY_MISSING.value
    assert set(payload["detail"]["missing_modules"]) == {"encoding", "container"}


def test_missing_platform_table_still_refuses_accessibility(tmp_path, capsys, monkeypatch):
    """表缺 → 3，不是"三平台全 OK"的假绿（K04 的反向）。"""

    monkeypatch.setenv(platform_tables.ENV_DIR, str(tmp_path))
    monkeypatch.chdir(tmp_path)
    code = main(
        ["check", str(FIXTURES / "reserved.zip"), "--target", "windows", "--module", "accessibility"]
    )
    assert code == int(ExitCode.CAPABILITY_MISSING)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err.strip())["error"] == ReasonCode.PLATFORM_TABLE_MISSING.value


# ------------------------------------------------------------------ 确定性


def test_check_accessibility_output_is_byte_identical_across_runs():
    """K09：同输入双跑逐字节一致（含 `entries[].accessibility`）。"""

    import io
    from contextlib import redirect_stdout

    def run() -> tuple[int, str]:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(
                [
                    "check",
                    str(FIXTURES / "trailing.zip"),
                    "--target",
                    "windows,linux",
                    "--module",
                    "accessibility",
                ]
            )
        return code, buffer.getvalue()

    assert run() == run()


def test_check_accessibility_output_has_no_host_path_or_timestamp():
    import io
    import re
    from contextlib import redirect_stdout

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        main(
            [
                "check",
                str(FIXTURES / "reserved.zip"),
                "--target",
                "windows",
                "--module",
                "accessibility",
            ]
        )
    text = buffer.getvalue()
    assert not re.search(r"\b[A-Za-z]:[\\/]", text)
    assert "/home/" not in text and "/Users/" not in text
    assert not re.search(r"\b20\d{2}-\d{2}-\d{2}T\d{2}:", text)


def test_accessibility_entry_point_runs_in_subprocess(tmp_path):
    """`python -m extract_oracle` 通路的独立冒烟（交付态入口）。"""

    env = {"PYTHONPATH": str(REPO / "src"), "PYTHONUTF8": "1"}
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "extract_oracle",
            "check",
            str(FIXTURES / "reserved.zip"),
            "--target",
            "windows",
            "--module",
            "accessibility",
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(tmp_path),
    )
    assert proc.returncode == 1, proc.stderr
    payload = json.loads(proc.stdout)
    con = next(entry for entry in payload["entries"] if entry["cdName"] == "CON.txt")
    assert con["accessibility"]["windows"]["level"] == "WRITTEN_UNREADABLE"
    assert con["accessibility"]["windows"]["evidence"] == list(access.RESERVED_EVIDENCE)


def test_synthetic_names_round_trip_through_report(tmp_path, capsys):
    """自造样本（非 fixture）：`a//b` 与 `dir/ok.txt` 的分级能进报告，且不误报合法子目录。"""

    path = _synthetic(tmp_path, "mixed.zip", [("a//b", b"1"), ("dir/ok.txt", b"2")])
    code = main(
        ["check", str(path), "--target", "windows", "--module", "accessibility"]
    )
    assert code == int(ExitCode.FINDINGS)
    payload = json.loads(capsys.readouterr().out)
    levels = {entry["cdName"]: entry["accessibility"]["windows"]["level"] for entry in payload["entries"]}
    assert levels == {"a//b": "BLOCKED", "dir/ok.txt": "OK"}
