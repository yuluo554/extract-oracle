"""M5 验收：MOD-5 长度预算（`budget.*` 两条）。

覆盖 `plan/HANDOFF-M5.md` §3 第 3 条与 §6 第四项：

1. 两个预算 fixture（`long_path.zip` / `long_comp.zip`）各命中对应 code；
2. `PATH_OVER_260` 是**预算告警**不是本机截断（`plan/05` §五 U12）——同一样本在
   `accessibility` 下必须是 `OK`，两条判定不许打架；
3. `COMPONENT_OVER_255` **按组件**判（U19 口径），`/` 是分隔符、不是字符；
   Windows 按 UTF-16 码元、Linux 按 **字节**（POSIX `{NAME_MAX}`）；
4. `clean.zip` 零误报。

口径一律引用 `data/README.md` §4.6，本文不写第二份数值表述。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from extract_oracle import platforms as platform_tables
from extract_oracle.capabilities import MODULES
from extract_oracle.cli import main
from extract_oracle.exit_codes import ExitCode
from extract_oracle.rules import access as access_rules
from extract_oracle.rules import budget as budget_rules
from extract_oracle.zip_reader import read_archive

REPO = Path(__file__).resolve().parent.parent
FIXTURES = REPO / "data" / "fixtures"
TRUTH = FIXTURES / "truth"
PLATFORM_DIR = REPO / "data" / "platforms"

sys.path.insert(0, str(REPO / "tools"))

import gen_fixtures  # noqa: E402


@pytest.fixture(scope="module")
def tables():
    return platform_tables.load(PLATFORM_DIR)


def _codes(name: str, targets: list[str], tables) -> list[str]:
    return [
        item.rule_id
        for item in budget_rules.check(read_archive(FIXTURES / name), targets, tables)
    ]


def _truth(name: str) -> dict:
    return json.loads((TRUTH / f"{name}.json").read_text(encoding="utf-8"))


def _synthetic(tmp_path: Path, name: str, entries: list[tuple[bytes, int]]) -> Path:
    """现造样本（`(名字字节, flags)`），不落 fixture 目录也不碰真值。"""

    path = tmp_path / name
    path.write_bytes(
        gen_fixtures.build_zip(
            [gen_fixtures.Entry(raw, b"PAYLOAD\n", flags=flags) for raw, flags in entries]
        )
    )
    return path


# ------------------------------------------------------------------ 能力门与两个 fixture


def test_budget_rules_belong_to_the_container_module():
    """`budget.*` 是 `container` 模块的另一个前缀（`plan/00` §七 对照表）。"""

    module = next(item for item in MODULES if item.name == "container")
    assert "budget.*" in module.rule_prefix
    assert budget_rules.BUDGET_CODES == ("budget.PATH_OVER_260", "budget.COMPONENT_OVER_255")


def test_long_path_hits_path_over_260(tables):
    """`long_path.zip`：整路径 314 字节 > 260，各组件 44 字节未超 255 → 只报 `PATH_OVER_260`。"""

    assert _codes("long_path.zip", ["windows"], tables) == ["budget.PATH_OVER_260"]
    assert _truth("long_path.zip")["expected_findings"] == ["budget.PATH_OVER_260"]


def test_long_comp_hits_component_over_255(tables):
    """`long_comp.zip`：单组件 256 字节/码元 → `COMPONENT_OVER_255`。

    整路径 257 码元 ≤ 260，所以只报组件那一条（两条不会互相串）。
    """

    assert _codes("long_comp.zip", ["windows"], tables) == ["budget.COMPONENT_OVER_255"]
    assert _truth("long_comp.zip")["expected_findings"] == ["budget.COMPONENT_OVER_255"]


def test_clean_zip_has_no_budget_findings(tables):
    """零误报基线：正常短名字不报任何预算。"""

    assert _codes("clean.zip", ["windows", "linux"], tables) == []
    assert _truth("clean.zip")["expected_findings"] == []


def test_budget_evidence_carries_platform_and_limits(tables):
    """证据必须自带平台与口径键——否则读者会把 260 与 4096 当成同一个口径。"""

    item = budget_rules.check(
        read_archive(FIXTURES / "long_path.zip"), ["windows"], tables
    )[0]
    assert item.precedent in budget_rules.PRECEDENTS
    assert item.evidence["platform"] == "windows"
    assert item.evidence["limit"] == 260
    assert item.evidence["units"] == 314 + 1  # 各组件码元 + 分隔符 + 终止 NUL
    assert item.evidence["componentCount"] == 7
    assert item.evidence["longestComponentUnits"] == 44


# ------------------------------------------------------------------ 预算告警 ≠ 本机截断（U12）


def test_path_over_260_is_a_budget_warning_not_a_local_truncation(tables):
    """U12：`PATH_OVER_260` 是**可移植性预算告警**，不是"本机必然截断"。

    两条独立判定的分工：`accessibility` 问"目标平台能不能创建"，`budget` 问"这份路径在
    未开启长路径支持的默认设置下可不可移植"。同一样本上前者必须 `OK`，否则文档里那句
    "LongPathsEnabled=1 时可直接创建"就与输出自相矛盾。
    """

    item = budget_rules.check(
        read_archive(FIXTURES / "long_path.zip"), ["windows"], tables
    )[0]
    assert item.evidence["kind"] == budget_rules.PATH_BUDGET_KIND
    # 措辞上不得断言"被截断/创建失败"
    for banned in ("截断", "创建失败", "失败"):
        assert banned not in item.message, banned
    assert "预算" in item.message or "不可移植" in item.message

    levels = access_rules.check(
        read_archive(FIXTURES / "long_path.zip"), ["windows"], tables
    )
    assert {verdict["windows"]["level"] for verdict in levels.values()} == {"OK"}


def test_component_over_255_is_a_platform_limit_not_a_budget(tables):
    """反向：组件超限是**平台硬限**（创建即失败），所以它不带"预算"那个 kind。"""

    item = budget_rules.check(
        read_archive(FIXTURES / "long_comp.zip"), ["windows"], tables
    )[0]
    assert item.evidence["kind"] == "platform_limit"
    # 与 accessibility 的结论一致：同一样本在 Windows 上是 BLOCKED
    levels = access_rules.check(
        read_archive(FIXTURES / "long_comp.zip"), ["windows"], tables
    )
    assert {verdict["windows"]["level"] for verdict in levels.values()} == {"BLOCKED"}


def test_extended_path_prefix_limit_is_recorded(tables):
    """长路径前缀下的上限也进证据（32767）——不然读者会以为 260 是绝对上限。"""

    item = budget_rules.check(
        read_archive(FIXTURES / "long_path.zip"), ["windows"], tables
    )[0]
    assert item.evidence["extendedLimit"] == budget_rules.WIN_MAX_PATH_EXTENDED


# ------------------------------------------------------------------ 按组件切（U19 口径）


def test_components_split_on_slash_not_by_length(tmp_path, tables):
    """`/` 是分隔符：`a/b` 是两个组件，各组件长度按**切出来的片段**算。

    与 MOD-4 同一口径（U19）。若把 `/` 当成普通字符算进组件长度，每一份带子目录的归档
    都会假报组件超限。
    """

    # 两段各 200 字节：整路径 401 字节 / 403 码元，任何单组件都没超 255
    long_part = b"d" * 200
    path = _synthetic(tmp_path, "two_parts.zip", [(long_part + b"/" + long_part, 0)])
    codes = [item.rule_id for item in budget_rules.check(read_archive(path), ["windows"], tables)]
    assert codes == ["budget.PATH_OVER_260"]  # 整路径超预算，但组件不超

    # 反向：一个 256 字节的组件（名字里没有 `/`）→ 组件超限
    path = _synthetic(tmp_path, "one_part.zip", [(b"x" * 256, 0)])
    codes = [item.rule_id for item in budget_rules.check(read_archive(path), ["windows"], tables)]
    assert codes == ["budget.COMPONENT_OVER_255"]


def test_linux_component_limit_is_measured_in_bytes(tmp_path, tables):
    """Linux 侧按**字节**（POSIX `{NAME_MAX}`），Windows 侧按 UTF-16 **码元**——两者可以不同。

    `中文…` 每字符 UTF-8 占 3 字节、UTF-16 占 1 码元：86 个汉字 = 258 字节但只有 86 码元。
    所以同一份样本在 Linux 上超限、在 Windows 上不超限。
    """

    name = ("\u4e2d" * 86).encode("utf-8")  # 258 字节 / 86 码元
    assert len(name) == 258
    path = _synthetic(tmp_path, "cjk.zip", [(name, gen_fixtures.FLAG_UTF8)])
    archive = read_archive(path)

    linux = [item.rule_id for item in budget_rules.check(archive, ["linux"], tables)]
    windows = [item.rule_id for item in budget_rules.check(archive, ["windows"], tables)]
    assert linux == ["budget.COMPONENT_OVER_255"]
    assert windows == []

    item = budget_rules.check(archive, ["linux"], tables)[0]
    assert item.evidence["platform"] == "linux"
    assert item.evidence["bytes"] == 258
    assert item.precedent == "posix_name_max_bytes"


def test_path_limits_differ_per_platform(tmp_path, tables):
    """整路径预算分平台：Windows 260 码元 / Linux 4096 字节。"""

    # 7 × 44 字节的嵌套路径 = 314 字节：超 Windows 的 260，但远低于 Linux 的 4096，
    # 且各组件 44 字节未超 255 → 只报整路径那一条
    part = b"d" * 44
    nested = b"/".join([part] * 7)
    assert len(nested) == 314
    path = _synthetic(tmp_path, "mid.zip", [(nested, 0)])
    archive = read_archive(path)
    assert [i.rule_id for i in budget_rules.check(archive, ["windows"], tables)] == [
        "budget.PATH_OVER_260"
    ]
    assert [i.rule_id for i in budget_rules.check(archive, ["linux"], tables)] == []

    # 5000 ASCII 字节的单组件：超 Linux 的 4096（也超 255 → 两条都报）
    path = _synthetic(tmp_path, "huge.zip", [(b"a" * 5000, 0)])
    archive = read_archive(path)
    linux = [i.rule_id for i in budget_rules.check(archive, ["linux"], tables)]
    assert linux == ["budget.COMPONENT_OVER_255", "budget.PATH_OVER_260"]


def test_macos_is_not_judged(tmp_path, tables):
    """macOS 侧不判预算：`data/README.md` §4.6 只给了 Windows/Linux 两套口径——**不猜**。"""

    path = _synthetic(tmp_path, "mid_mac.zip", [(b"a" * 300, 0)])
    assert [i.rule_id for i in budget_rules.check(read_archive(path), ["macos"], tables)] == []


def test_budget_does_not_require_platform_tables():
    """`declared_platforms()` 恒空：预算不查 `$UpCase` 表，所以表缺时它仍能判。

    这条是"别把 `$UpCase` 变成 `container` 模块的隐式依赖"的可跑红形态
    （`plan/HANDOFF-M5.md` §2 第 16 条）。
    """

    assert budget_rules.declared_platforms() == ()


def test_budget_works_without_platform_tables(tmp_path, monkeypatch):
    """表缺时 `--module container` 仍要出报告（预算不需要表）——**不是**退 3。"""

    monkeypatch.setenv(platform_tables.ENV_DIR, str(tmp_path))
    monkeypatch.chdir(tmp_path)
    code = main(
        ["check", str(FIXTURES / "long_path.zip"), "--target", "windows", "--module", "container"]
    )
    assert code == int(ExitCode.FINDINGS)


# ------------------------------------------------------------------ 确定性排序


def test_platform_specific_findings_are_ordered_deterministically(tmp_path, tables):
    """同一组件在两平台上都超限 → 两条同 ruleId 的 finding；顺序必须是全序（K09）。

    `Finding` 没有平台字段，所以排序键在 `(cd_offset, ruleId, entryIndex)` 之外再加
    证据的确定性序列化（`findings.sort_key`）——否则并列顺序取决于输入顺序。
    """

    path = _synthetic(tmp_path, "both.zip", [(b"x" * 300, 0)])
    archive = read_archive(path)
    first = [item.to_dict() for item in budget_rules.check(archive, ["windows", "linux"], tables)]
    again = [item.to_dict() for item in budget_rules.check(archive, ["linux", "windows"], tables)]
    assert first == again  # 目标顺序换一下，输出必须一样


# ------------------------------------------------------------------ 命令行面


def test_budget_findings_reach_the_cli_report(capsys):
    """`--module container` 的报告里要能看见 `budget.*`（两条判定同属一个模块范围）。"""

    code = main(
        ["check", str(FIXTURES / "long_comp.zip"), "--target", "windows", "--module", "container"]
    )
    assert code == int(ExitCode.FINDINGS)
    payload = json.loads(capsys.readouterr().out)
    assert [item["ruleId"] for item in payload["findings"]] == [
        "budget.COMPONENT_OVER_255",
        "container.MIMETYPE_COMPRESSED",
    ] or [item["ruleId"] for item in payload["findings"]] == ["budget.COMPONENT_OVER_255"]