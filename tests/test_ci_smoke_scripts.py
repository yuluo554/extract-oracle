"""CI 冒烟步的**形态**守门：静态判据 + 用 GitHub 的 shell 标志实跑。

两条常驻断言（`plan/05` §5.3 的实测来源）：

1. **静态**：冒烟步里**不得**出现 `echo "$var" | grep -q …` —— 在 `pipefail` 下 `grep -q` 提前退出
   会让上游 `echo` 收 SIGPIPE，管道返回 141，于是"命中了却走 `||` 分支"（macOS 上实测到的假红）。
2. **实跑**：把每个冒烟步的脚本原样交给 `bash --noprofile --norc -e -o pipefail` 跑一遍
   （**与 GitHub 的调用完全一致**），必须 rc=0。

为什么这两条都要有：静态那条抓"写法回潮"，实跑那条抓"改了判据但语义变了"——
只写静态会放过"here-string 写错模式"，只写实跑会在写法回潮时**偶发**变红（输出小时不触发 SIGPIPE）。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
WORKFLOW = REPO / ".github" / "workflows" / "ci.yml"


def _workflow() -> dict:
    assert WORKFLOW.is_file(), "缺 .github/workflows/ci.yml"
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _smoke_steps() -> list[tuple[str, str]]:
    workflow = _workflow()
    steps = []
    for job_name, job in workflow["jobs"].items():
        for step in job["steps"]:
            name = step.get("name", "")
            if "smoke" in name.lower() and "run" in step:
                steps.append((f"{job_name}/{name}", step["run"]))
    return steps


def test_workflow_parses_with_the_expected_job_and_step_counts():
    """`yaml.safe_load` + job/step 数：step `name` 里有裸 `: ` 会让 GitHub 直接不建 job。"""

    workflow = _workflow()
    assert list(workflow["jobs"]) == ["gate", "test", "artifact"]
    counts = {name: len(job["steps"]) for name, job in workflow["jobs"].items()}
    assert counts == {"gate": 5, "test": 14, "artifact": 5}, counts


def test_smoke_steps_are_discovered():
    """非空跑自证：一条都没抽到 = 抽取面坏了（而不是"没有冒烟步"）。"""

    steps = _smoke_steps()
    assert len(steps) >= 5, f"只抽到 {len(steps)} 个冒烟步: {[n for n, _ in steps]}"


@pytest.mark.parametrize("name,script", _smoke_steps(), ids=[n for n, _ in _smoke_steps()])
def test_smoke_step_has_no_pipe_into_grep(name: str, script: str) -> None:
    """静态：`| grep -q` 在 `pipefail` 下会因 SIGPIPE 撒谎（见模块 docstring）。"""

    offenders = [
        line.strip()
        for line in script.splitlines()
        if "| grep" in line and not line.strip().startswith("#")
    ]
    assert offenders == [], (
        f"{name} 里出现了 `| grep`（改用 here-string：`grep -q PAT <<<\"$var\"`）：{offenders}"
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

    **按 GitHub 的形态跑**，不是 `bash -c` 的默认形态——`-e`/`pipefail` 正是让上面那两类缺陷
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
    assert proc.returncode == 0, f"{name} 在 GitHub 的 bash 标志下失败（rc={proc.returncode}）：\n{proc.stdout[-1500:]}\n{proc.stderr[-1500:]}"
    assert "smoke OK" in proc.stdout or name.endswith("Console script smoke"), proc.stdout[-800:]