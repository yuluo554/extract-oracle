"""README 指令面 ↔ CLI parser 反射对账（安装面/指令面的一条常驻检查）。

为什么值得单独一条：skill 里实测过"文档写 `--show-kind=a,b`、实现加了 `choices=(…)` →
README 第一条命令 exit 2，而 CI 全绿"。这类缺陷**纯参数面就能抓**，不依赖任何数据。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from extract_oracle.cli import build_parser

REPO = Path(__file__).resolve().parent.parent
README = REPO / "README.md"

#: README 里以 `extract-oracle ` 开头的可执行行（代码块内）。
COMMAND_LINE = re.compile(r"^extract-oracle (.+)$", re.M)


def _readme_commands() -> list[list[str]]:
    text = README.read_text(encoding="utf-8")
    return [line.split() for line in COMMAND_LINE.findall(text)]


def test_readme_has_commands():
    """非空跑自证：一条都没抽到，说明抽取面坏了（而不是 README 没命令）。"""

    assert _readme_commands(), "README 里没抽到任何 extract-oracle 命令"


@pytest.mark.parametrize("argv", _readme_commands(), ids=lambda a: " ".join(a)[:60])
def test_readme_command_parses(argv: list[str]):
    """每一条 README 命令都必须被 parser 接受（占位路径不参与解析）。"""

    parser = build_parser()
    ns = parser.parse_args(argv)
    assert ns.command in {"inspect", "check", "capabilities", "platforms"}


def test_readme_multi_value_target_forms():
    """多值参数三种形态都必须认：单值 / 重复旗标 / 逗号分隔。"""

    from extract_oracle.cli import _parse_targets

    assert _parse_targets(["windows"]) == ["windows"]
    assert _parse_targets(["windows", "linux"]) == ["windows", "linux"]
    assert _parse_targets(["windows,linux"]) == ["windows", "linux"]


def test_readme_does_not_promise_unimplemented_commands():
    """README 的命令只能落在 parser 注册的子命令集合里（防"文档写了、代码没有"）。"""

    parser = build_parser()
    choices = set()
    for action in parser._actions:
        if hasattr(action, "choices") and action.choices and isinstance(action.choices, dict):
            choices |= set(action.choices)
    for argv in _readme_commands():
        assert argv[0] in choices, f"README 命令 {argv[0]!r} 未注册"


def test_readme_documents_exit_codes():
    """"依赖缺失不静默退化"是卖点，README 必须写清退出码语义。"""

    text = README.read_text(encoding="utf-8")
    for code in ("| 0 |", "| 1 |", "| 2 |", "| 3 |", "| 4 |"):
        assert code in text, f"README 缺退出码 {code}"
    assert "绝不静默退化" in text or "不是故障" in text


def test_readme_status_line_carries_the_current_version():
    """版本号"三处一致"的第三处（前两处：`pyproject` 走 `dynamic` 读根模块、产物自报）。

    为什么这条值得单独有：手抄两处时"漏改 `__init__`"是经典事故，而 README 顶部那行是**用户
    下载后先看到的那一处**（随包文档）。判据取"README 里出现 `v<__version__>`"，与产物自报的
    `tests/test_artifact_e2e.py::test_artifact_version_is_the_single_source_of_truth` 成对。
    """

    from extract_oracle import __version__

    text = README.read_text(encoding="utf-8")
    assert f"v{__version__}" in text, f"README 状态行未跟上根模块版本 v{__version__}"


def test_section_references_point_at_existing_sections():
    """代码/文档里的 `data/README.md` §N.M 引用必须有实物（防悬空口径引用）。

    实测来源：`report.py` 曾引用 §4.8（当时不存在）——引用悬空时，"口径单点"变成
    "引用了一个不存在的唯一真相源"，比没有引用更糟。
    """

    import re

    data_readme = (REPO / "data" / "README.md").read_text(encoding="utf-8")
    existing = set(re.findall(r"^###\s+(\d+\.\d+)\s", data_readme, re.M))
    assert existing, "data/README.md 里没解析出任何 §N.M 小节（抽取面坏了）"

    sources = [REPO / "src" / "extract_oracle" / name for name in (
        "report.py", "cli.py", "errors.py", "zip_reader.py"
    )]
    sources += list((REPO / "plan").glob("*.md"))
    dangling = []
    for path in sources:
        text = path.read_text(encoding="utf-8")
        for ref in re.findall(r"data/README\.md[^\n]{0,20}?§(\d+\.\d+)", text):
            if ref not in existing:
                dangling.append(f"{path.name} → §{ref}")
    assert dangling == [], f"悬空的 §N.M 引用: {dangling}"
