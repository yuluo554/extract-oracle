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


def _is_real_bash(path: str) -> bool:
    """这个 `bash` 是真 bash 吗？（`$BASH_VERSION` 非空即真）

    为什么必须验：Windows 上 `C:\\Windows\\System32\\bash.exe` 是 **WSL 的启动器**，不是 bash
    ——`shutil.which("bash")` 会按 PATH 顺序先命中它，然后每条命令都变成
    "Windows Subsystem for Linux has no installed distributions"（CI 实测的 rc=1）。
    判据落"它能报出自己的 `$BASH_VERSION`"，不落路径猜测。
    """

    try:
        proc = subprocess.run(
            [path, "--noprofile", "--norc", "-c", "printf %s \"$BASH_VERSION\""],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0 and proc.stdout.strip()[:1].isdigit()


def _find_bash() -> str | None:
    """按序找一个**真的** bash：PATH 上的 → 环境变量 → Git for Windows 的固定位置。

    `C:\\Program Files\\Git\\bin\\bash.exe` 与 `…\\usr\\bin\\bash.exe` 是 GitHub `windows-latest`
    上 Git Bash 的固定位置（该 runner 的 `shell: bash` 用的就是它）；本机 Git 装在别处时用
    `ORACLE_BASH` 指定（与 `PROBE_7Z`/`PROBE_UNZIP` 同一族的显式覆盖）。
    """

    candidates = [os.environ.get("ORACLE_BASH"), shutil.which("bash")]
    if os.name == "nt":
        candidates += [
            r"C:\Program Files\Git\bin\bash.exe",
            r"C:\Program Files\Git\usr\bin\bash.exe",
        ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file() and _is_real_bash(candidate):
            return candidate
    return None


def _bash_preamble() -> str:
    """把 `extract-oracle` 定义成 **bash 函数**（等价于 console script，但不依赖 PATH 与 shebang）。

    为什么不用"写一个可执行 shim 文件"（首版就是那么做的，CI 实测踩到）：
    shim 的 `#!/bin/sh` 在 **Windows runner** 上被解析成 **WSL 的启动器**（`/bin/sh` 不属于
    Git Bash），于是脚本里每个 `extract-oracle` 都变成
    `Windows Subsystem for Linux has no installed distributions`、整步 rc=1 ——
    测出来的是"宿主怎么解释 shebang"，**不是冒烟步本身**。
    函数形态没有任何文件被执行，因此与平台无关；`"$@"` 也保住了参数与退出码。
    """

    interpreter = sys.executable.replace("\\", "/")
    return f'extract-oracle() {{ "{interpreter}" -m extract_oracle "$@"; }}\n'


@pytest.mark.parametrize("name,script", _smoke_steps(), ids=[n for n, _ in _smoke_steps()])
def test_smoke_step_runs_under_github_bash_flags(name: str, script: str, tmp_path: Path) -> None:
    """实跑：`bash -e -o pipefail`（GitHub 的原样调用）下每个冒烟步必须 rc=0。

    **按 GitHub 的形态跑**，不是 `bash -c` 的默认形态——`-e`/`pipefail` 正是让那两类缺陷
    暴露出来的两个开关；用默认形态跑会得出"全绿"的假结论。
    """

    bash = _find_bash()
    if bash is None:
        pytest.skip("本机没有**真的** bash（Windows 上 System32\\bash.exe 是 WSL 启动器，不算）")

    env = {
        **os.environ,
        "PYTHONUTF8": "1",
        "ORACLE_REQUIRE_TOOLS": "1",
        "PYTHONPATH": str(REPO / "src"),
    }
    proc = subprocess.run(
        [bash, "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", _bash_preamble() + script],
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

def test_find_bash_rejects_the_wsl_launcher(monkeypatch, tmp_path):
    """`_find_bash` 必须**拒收** Windows 的 WSL 启动器（CI 实测：它就是那条 rc=1 的成因）。

    判据不落"路径里有没有 System32"这种猜测，而是**问它要 `$BASH_VERSION`**：
    WSL 启动器报不出来（且它会说 "no installed distributions"）。
    这里用一个**故意不是 bash 的可执行文件**扮演它（`cmd /c exit 0` 类：能跑、但不认 `-c` 语义），
    并断言 `_find_bash()` 会跳过它去取一个真 bash（本机/GitHub runner 上都有）。
    """

    fake_wsl = tmp_path / ("bash.exe" if os.name == "nt" else "bash")
    fake_wsl.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8", newline="\n")
    fake_wsl.chmod(0o755)
    # 用 `ORACLE_BASH` 提供一个**已知可用**的真 bash 作对照：断言的是
    # "拒收假 bash + 仍能取到真 bash"，而不是"这台机器恰好把 Git 装在固定位置"。
    known = _find_bash()
    if known is None:
        pytest.skip("本机没有真 bash（无法构造'拒收之后仍能取到'的对照）")
    monkeypatch.setenv("ORACLE_BASH", known)
    monkeypatch.setattr(shutil, "which", lambda name: str(fake_wsl) if name == "bash" else None)

    assert _is_real_bash(str(fake_wsl)) is False, "假 bash 不该被判成真 bash"
    found = _find_bash()
    assert found is not None, "拒收假 bash 之后必须仍能取到 ORACLE_BASH 指定的真 bash"
    assert Path(found).resolve() != fake_wsl.resolve(), "拒收假 bash 后仍取到了它"


def test_find_bash_reports_the_real_one_on_this_host():
    """正向对照：本机（或 runner）上能找到真 bash 时，它必须能报出 `$BASH_VERSION`。"""

    found = _find_bash()
    if found is None:
        pytest.skip("本机没有真 bash")
    assert _is_real_bash(found)
