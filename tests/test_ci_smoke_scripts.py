"""CI 冒烟步的**形态**守门：静态判据 + 用 GitHub 的 shell 标志实跑。

两条常驻断言（`plan/05` §5.3 的实测来源）：

1. **静态**：冒烟步里**不得**把输出管道喂给 `grep -q` —— 在 `pipefail` 下 `grep -q` 提前退出
   会让上游 `echo` 收 SIGPIPE，管道返回 141，于是"命中了却走兜底分支"（macOS 上实测到的假红）。
2. **实跑**：把每个冒烟步的脚本原样交给 `bash --noprofile --norc -e -o pipefail` 跑一遍
   （**与 GitHub 的调用完全一致**），必须 rc=0。

为什么两条都要有：静态那条抓"写法回潮"，实跑那条抓"改了判据但语义变了"——
只写静态会放过"here-string 写错模式"，只写实跑会在写法回潮时**偶发**变红（输出小时不触发 SIGPIPE）。

**只用标准库解析 workflow**：本项目承诺**零运行时依赖**，`PyYAML` 不是依赖（CI 首跑实测：
`ModuleNotFoundError: No module named 'yaml'` 让整个测试模块在收集期就挂掉）。
所以这里按缩进做最小结构解析——判据只关心"有哪些 job、每个 job 有几个 step、哪些 step 是冒烟步"。
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
WORKFLOW = REPO / ".github" / "workflows" / "ci.yml"

#: `- name:` / `- uses:` 开头的行 = 一个 step 的第一行（本文件的 workflow 风格固定为这种写法）。
STEP_RE = re.compile(r"^(\s*)- (?:name|uses):", re.M)
JOB_RE = re.compile(r"^  ([A-Za-z0-9_-]+):$", re.M)


def _workflow_text() -> str:
    assert WORKFLOW.is_file(), "缺 .github/workflows/ci.yml"
    return WORKFLOW.read_text(encoding="utf-8")


def _job_blocks() -> dict[str, str]:
    """按两空格缩进的 `jobs:` 子键切出各 job 的文本块（最小解析，够用即可）。"""

    text = _workflow_text()
    assert "\njobs:\n" in text, "workflow 里找不到 `jobs:`"
    body = text.split("\njobs:\n", 1)[1]
    starts = [(m.group(1), m.start()) for m in JOB_RE.finditer(body)]
    blocks: dict[str, str] = {}
    for index, (name, start) in enumerate(starts):
        end = starts[index + 1][1] if index + 1 < len(starts) else len(body)
        blocks[name] = body[start:end]
    return blocks


def _smoke_steps() -> list[tuple[str, str]]:
    """抽出所有"名字含 smoke"的 step：(job/name, 脚本)。脚本取 `run: |` 之后到下一个 step 之前。"""

    found: list[tuple[str, str]] = []
    for job_name, block in _job_blocks().items():
        # 每个 step 从 `      - ` 开始
        chunks = re.split(r"^      - ", block, flags=re.M)[1:]
        for chunk in chunks:
            name_match = re.search(r"name:\s*(.+)", chunk)
            if not name_match or "smoke" not in name_match.group(1).lower():
                continue
            if "run:" not in chunk:
                continue
            script = chunk.split("run:", 1)[1]
            if script.lstrip().startswith("|"):
                script = script.lstrip()[1:]
            lines = script.split("\n")
            dedented = []
            for line in lines:
                if line.strip() and not line.startswith(" " * 10) and dedented:
                    break
                dedented.append(line[10:] if line.startswith(" " * 10) else line)
            found.append((f"{job_name}/{name_match.group(1).strip()}", "\n".join(dedented).strip("\n")))
    return found


def test_workflow_has_the_expected_jobs_and_step_counts():
    """结构断言：3 个 job，step 数 5 / 14 / 5。

    为什么值得有：step `name` 里带裸 `: ` 会让 GitHub **直接不建 job**（run 显示 failure 而
    `jobs=0`，文件字节与语法都正常）——所以"能被本地解析"本身要有一条常驻断言。
    """

    blocks = _job_blocks()
    assert list(blocks) == ["gate", "test", "artifact"], list(blocks)
    counts = {name: len(STEP_RE.findall(block)) for name, block in blocks.items()}
    assert counts == {"gate": 5, "test": 14, "artifact": 5}, counts


def test_smoke_steps_are_discovered():
    """非空跑自证：一条都没抽到 = 抽取面坏了（而不是"没有冒烟步"）。"""

    steps = _smoke_steps()
    assert len(steps) >= 5, f"只抽到 {len(steps)} 个冒烟步: {[n for n, _ in steps]}"
    names = [name for name, _ in steps]
    for expected in (
        "Structure findings smoke",
        "Fold findings smoke",
        "Accessibility smoke",
        "Encoding smoke",
        "Container and budget smoke",
    ):
        assert any(name.endswith(expected) for name in names), f"缺冒烟步 {expected}: {names}"


@pytest.mark.parametrize("name,script", _smoke_steps(), ids=[n for n, _ in _smoke_steps()])
def test_smoke_step_does_not_pipe_into_grep(name: str, script: str) -> None:
    """静态：`… | grep -q` 在 `pipefail` 下会因 SIGPIPE 撒谎（见模块 docstring）。"""

    offenders = [
        line.strip()
        for line in script.splitlines()
        if re.search(r"\|\s*grep", line) and not line.strip().startswith("#")
    ]
    assert offenders == [], (
        f"{name} 里把输出管道喂给了 grep（改用 here-string：`grep -q PAT <<<\"$var\"`）：{offenders}"
    )


def _console_shim(directory: Path) -> Path:
    """造一个 `extract-oracle` 可执行 shim（等价于 console script，避免依赖 pip 安装态）。"""

    shim = directory / "extract-oracle"
    interpreter = sys.executable.replace("\\", "/")
    with open(shim, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(f'#!/bin/sh\nexec "{interpreter}" -m extract_oracle "$@"\n')
    shim.chmod(0o755)
    return shim


@pytest.mark.parametrize("name,script", _smoke_steps(), ids=[n for n, _ in _smoke_steps()])
def test_smoke_step_runs_under_github_bash_flags(name: str, script: str, tmp_path: Path) -> None:
    """实跑：`bash -e -o pipefail`（GitHub 的原样调用）下每个冒烟步必须 rc=0。

    **按 GitHub 的形态跑**，不是 `bash -c` 的默认形态——`-e`/`pipefail` 正是让那两类缺陷
    暴露出来的两个开关；用默认形态跑会得出"全绿"的假结论。
    """

    if shutil.which("bash") is None:
        pytest.skip("本机没有 bash（Windows 裸环境）；CI 的三个平台都有")

    _console_shim(tmp_path)
    env = {
        **os.environ,
        "PYTHONUTF8": "1",
        "ORACLE_REQUIRE_TOOLS": "1",
        "PYTHONPATH": str(REPO / "src"),
        "PATH": str(tmp_path) + os.pathsep + os.environ.get("PATH", ""),
    }
    proc = subprocess.run(
        ["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        cwd=str(REPO),
        timeout=300,
    )
    assert proc.returncode == 0, (
        f"{name} 在 GitHub 的 bash 标志下失败（rc={proc.returncode}）：\n"
        f"{proc.stdout[-1500:]}\n{proc.stderr[-1500:]}"
    )
    assert "smoke OK" in proc.stdout or name.endswith("Console script smoke"), proc.stdout[-800:]