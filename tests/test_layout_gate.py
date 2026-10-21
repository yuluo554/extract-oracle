"""门自身的变异验证：故意弄坏 → 门必须变红；没红 = 假门。

在临时沙箱里放**真实仓库文件的副本**（不是手写的假文档），这样判据面对的是真实文档形态；
变异逐条施加在副本上，判据组数与被证伪的判据数一一对应（`plan/05` §3.1）。
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def _write_lf(path: Path, text: str) -> None:
    """显式 LF 写盘，**Python 3.9 兼容**（`write_text` 的 `newline=` 参数是 3.10 才加的）。"""

    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)



def _run_gate(sandbox: Path) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(sandbox / "tools" / "check_sprint_layout.py")],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return proc.returncode, proc.stdout


def _fails(output: str) -> list[str]:
    return [line.split()[1] for line in output.splitlines() if line.startswith("FAIL")]


@pytest.fixture()
def sandbox(tmp_path: Path) -> Path:
    """真实文件的副本：拷门需要的 md + **整个 tools/ 目录**（门会扫"文档点名的工具是否存在"）。"""

    root = tmp_path / "sandbox"
    (root / "tools").mkdir(parents=True)
    (root / "tools" / "__init__.py").write_text("", encoding="utf-8")
    (root / "plan").mkdir(parents=True)
    (root / "data").mkdir(parents=True)
    for rel in ["AGENTS.md", "README.md", "data/README.md"]:
        shutil.copy2(REPO / rel, root / rel)
    for path in sorted((REPO / "plan").glob("*.md")):
        shutil.copy2(path, root / "plan" / path.name)
    for path in sorted((REPO / "tools").glob("*.py")):
        shutil.copy2(path, root / "tools" / path.name)
    return root


def _replace(path: Path, old: str, new: str, count: int = 1) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, f"变异锚点失配（变异没发生，'仍绿'不能说明任何事）: {old!r}"
    _write_lf(path, text.replace(old, new, count))
    assert new in path.read_text(encoding="utf-8")  # 替代已生效


def test_baseline_sandbox_is_green(sandbox: Path):
    """阳性对照：未变异的沙箱必须全绿——否则后面每条"变红"都证明不了什么。"""

    code, out = _run_gate(sandbox)
    assert code == 0, out


def test_m1_delete_agents_md_is_red(sandbox: Path):
    (sandbox / "AGENTS.md").unlink()
    code, out = _run_gate(sandbox)
    assert code == 1
    assert "LAYOUT.FILES" in _fails(out)


def test_m7_delete_plan_doc_is_red(sandbox: Path):
    (sandbox / "plan" / "02-架构与技术选型.md").unlink()
    code, out = _run_gate(sandbox)
    assert code == 1
    assert "LAYOUT.FILES" in _fails(out)


def test_m5_delete_binding_line_is_red(sandbox: Path):
    path = sandbox / "plan" / "00-README总览.md"
    lines = path.read_text(encoding="utf-8").split("\n")
    kept = [line for line in lines if not re.match(r"^>.*ai-tool-project-sprint", line)]
    assert len(kept) < len(lines)
    _write_lf(path, "\n".join(kept))
    code, out = _run_gate(sandbox)
    assert code == 1
    assert "LAYOUT.BINDING_HEAD" in _fails(out)


def test_m2_flip_one_copy_is_red(sandbox: Path):
    """自我参照的真值源守卫：只在**一个**副本里翻状态，门必须红。"""

    _replace(sandbox / "plan" / "05-里程碑与发布.md", "| M0 | ✅ |", "| M0 | ⬜ |")
    code, out = _run_gate(sandbox)
    assert code == 1
    assert "LAYOUT.STATUS" in _fails(out)


def test_m9_ledger_pending_on_done_milestone_is_red(sandbox: Path):
    """台账是第四份状态副本：把一条已 ✅ 的行挂回"待 M<k>"必须红。"""

    _replace(
        sandbox / "plan" / "00-README总览.md",
        "| 方法论装订 | `AGENTS.md` + 布局门 + 脱敏门 + `plan/00` 顶部一行 | `tools/check_sprint_layout.py` / `tools/check_desensitized.py` | 布局门全绿 + 变异逐组变红（`tests/test_layout_gate.py`） | ✅ |",
        "| 方法论装订 | `AGENTS.md` + 布局门 + 脱敏门 | `tools/check_sprint_layout.py` | 布局门全绿 | ⬜ 待 M0 验证 |",
    )
    code, out = _run_gate(sandbox)
    assert code == 1
    assert "LAYOUT.LEDGER" in _fails(out)


def test_m3_gap_cell_mentions_done_milestone_is_red(sandbox: Path):
    """缺口表的**缺口格**（第一列）提到已 ✅ 里程碑 → 红。

    变异点选在缺口格里（不是"说明"格）：按表头定位列号的判据才有区分度。
    """

    _replace(
        sandbox / "plan" / "06-交付对标与决策.md",
        "| CI 未实跑 | 无远端，工作流文件尚未首推 | 首推后回填 run id |",
        "| CI 未实跑（M0 遗留） | 无远端，工作流文件尚未首推 | 首推后回填 run id |",
    )
    code, out = _run_gate(sandbox)
    assert code == 1
    assert "LAYOUT.GAPS" in _fails(out)


def test_gap_description_column_is_not_the_gap_column(sandbox: Path):
    """反向对照：里程碑号只出现在"说明/关闭条件"列时**不得**判红。

    这条防的是"末列当缺口列"的假门（真实故障永远抓不到）与其镜像（说明列被误判）。
    """

    _replace(
        sandbox / "plan" / "06-交付对标与决策.md",
        "| CI 未实跑 | 无远端，工作流文件尚未首推 | 首推后回填 run id |",
        "| CI 未实跑 | 无远端（M0 起） | 首推后回填 run id |",
    )
    code, out = _run_gate(sandbox)
    assert "LAYOUT.GAPS" not in _fails(out), out


def test_m4_delete_done_milestone_handoff_is_red(sandbox: Path):
    """M4（M1 起的形态）：删掉**已 ✅ 里程碑**的交接单 → `LAYOUT.HANDOFFS` 红。

    M0 期这条靶子是 `HANDOFF-M1`（M0 被豁免、M1 是"下一棒"）→ 判据落在 `HANDOFF_NEXT`。
    M1 落地后 `HANDOFF-M1` 变成"已 ✅ 里程碑的收尾记录" → 判据落在 `LAYOUT.HANDOFFS`。
    **两个判据都要有各自能红的靶子**，所以这里改成断言后者，另加一条断言前者。
    """

    (sandbox / "plan" / "HANDOFF-M1.md").unlink()
    code, out = _run_gate(sandbox)
    assert code == 1
    assert "LAYOUT.HANDOFFS" in _fails(out)
    # 这条不该由 HANDOFF_NEXT 兜住（下一棒 = M2，与 M1 的交接单无关）
    assert "LAYOUT.HANDOFF_NEXT" not in _fails(out)


def test_m4_delete_next_handoff_is_red(sandbox: Path):
    """`LAYOUT.HANDOFF_NEXT` 自己的靶子：删"下一棒"的交接单。

    **不写死里程碑号**：M2 收尾后"下一棒"从 M2 变成 M3，写死 `HANDOFF-M2` 会让本测试在
    里程碑推进时变成假红（实测踩过）。靶子按门自己的判据算：`min(未完成里程碑)`。
    """

    next_handoff = _next_handoff(sandbox)
    (sandbox / "plan" / next_handoff).unlink()
    code, out = _run_gate(sandbox)
    assert code == 1
    assert "LAYOUT.HANDOFF_NEXT" in _fails(out)


def _next_handoff(root: Path) -> str:
    """按 `plan/05` §二状态表算出"下一棒"的交接单文件名（与门同源的判据）。"""

    text = (root / "plan" / "05-里程碑与发布.md").read_text(encoding="utf-8")
    done, all_milestones = set(), set()
    for line in text.split("\n"):
        match = re.match(r"^\|\s*\*{0,2}M(\d+)\b", line)
        if not match:
            continue
        cells = [c.strip() for c in line.split("|")[1:]]
        if "✅" in cells or "⬜" in cells:
            number = int(match.group(1))
            all_milestones.add(number)
            if "✅" in cells:
                done.add(number)
    pending = sorted(all_milestones - done)
    assert pending, "没有未完成里程碑——本判据无靶子"
    return f"HANDOFF-M{pending[0]}.md"


def test_doc_tools_judgement_is_not_empty(sandbox: Path):
    """`LAYOUT.DOC_TOOLS` 的阳性对照：文档里真出现了 tools/ 引用。"""

    code, out = _run_gate(sandbox)
    assert code == 0
    assert "个文档点名的 tools/ 脚本全部在位" in out


def test_doc_tools_named_but_missing_is_red(sandbox: Path):
    _replace(
        sandbox / "plan" / "05-里程碑与发布.md",
        "`py -3.12 tools/gen_fixtures.py --check`",
        "`py -3.12 tools/gen_fixtures.py --check` + `py -3.12 tools/never_implemented.py`",
    )
    code, out = _run_gate(sandbox)
    assert code == 1
    assert "LAYOUT.DOC_TOOLS" in _fails(out)


# ── 发布留档（LAYOUT.RELEASE）的两条独立判据 + "未完成即跳过"的反向 ──────────────

RELEASE_DOC = """# RELEASE-M6 · 发布留档

## 一、tag 前事实

- tag：v0.1.0（结构见下文）

## 二、tag 后追加事实

- 本节在 tag 树内只写结构，字面值写在 tag 之后的提交里。

## 三、阶段 7 出口门覆盖对账

| 出口门 | 状态 | 证据 / 不适用理由 |
| --- | --- | --- |
| 发布物本体已验 | 实现 | 真下载 + 中立目录 |
| 源码包自足 | 不适用 | 附件 = 构建产物本身 |
| CI 首推 | 待首推 | 无远端 |
"""


def _mark_release_done(sandbox: Path) -> None:
    for rel in ["plan/00-README总览.md", "README.md"]:
        path = sandbox / rel
        text = path.read_text(encoding="utf-8")
        text = re.sub(r"^(\|\s*\**M6\b[^\n]*?)\|\s*[^|]*\|", r"\1| ✅ |", text, flags=re.M)
        _write_lf(path, text)
    for rel in ["plan/05-里程碑与发布.md"]:
        path = sandbox / rel
        text = path.read_text(encoding="utf-8")
        text = text.replace("| M6 | ⬜ | — |", "| M6 | ✅ | — |")
        _write_lf(path, text)
    shutil.copy2(sandbox / "plan" / "HANDOFF-M1.md", sandbox / "plan" / "HANDOFF-M6.md")


def test_release_green_when_doc_has_both_columns_and_coverage(sandbox: Path):
    """正向对照：留档齐备时该判据本身必须 PASS（否则后面的"变红"可能只是恒红）。"""

    _mark_release_done(sandbox)
    _write_lf(sandbox / "plan" / "RELEASE-M6.md", RELEASE_DOC)
    _code, out = _run_gate(sandbox)
    assert "PASS  LAYOUT.RELEASE  两栏:True 覆盖对账小节:True" in out, out


def test_m6_remove_coverage_section_is_red(sandbox: Path):
    _mark_release_done(sandbox)
    doc = RELEASE_DOC.split("## 三、")[0]
    _write_lf(sandbox / "plan" / "RELEASE-M6.md", doc)
    code, out = _run_gate(sandbox)
    assert code == 1
    assert "LAYOUT.RELEASE" in _fails(out)


def test_m8_remove_tag_after_marker_is_red(sandbox: Path):
    """两个独立判据里的第二个：两栏齐全。去掉 §二 标题里的 "tag 后" → 必红。"""

    _mark_release_done(sandbox)
    doc = RELEASE_DOC.replace("## 二、tag 后追加事实", "## 二、追加事实")
    _write_lf(sandbox / "plan" / "RELEASE-M6.md", doc)
    code, out = _run_gate(sandbox)
    assert code == 1
    assert "LAYOUT.RELEASE" in _fails(out)


def test_m10_done_without_release_doc_is_red(sandbox: Path):
    """'发布里程碑未完成即跳过' 分支的反向：✅ 之后必须先有留档。

    **缺件态必须显式构造**（M6 实测踩到的"瞬态断言"）：本测试原先靠"仓库里**没有** `RELEASE-M6.md`"
    来表达缺档——沙箱拷的是真实仓库文件，于是留档一落盘，这条测试就自己变红（它测的是"任务还没做"，
    不是门的模式语义）。正解 = 在沙箱里**显式删掉**留档来构造缺档态，与项目进度解耦。
    判别 = "我这条测试，会不会因为'我把该做的事做完了'而变红？"——会，就说明测的是瞬态而非语义。
    """

    _mark_release_done(sandbox)
    doc = sandbox / "plan" / "RELEASE-M6.md"
    assert doc.is_file(), "沙箱里应当先有一份留档，本变异才有可删的对象（缺件态自证）"
    doc.unlink()
    code, out = _run_gate(sandbox)
    assert code == 1
    assert "LAYOUT.RELEASE" in _fails(out), out


def test_release_not_applicable_before_milestone_done(sandbox: Path):
    """正向：M6 未完成时该判据 PASS 并写明不适用（不是假绿）。"""

    code, out = _run_gate(sandbox)
    assert code == 0
    assert "收尾记录尚不适用" in out