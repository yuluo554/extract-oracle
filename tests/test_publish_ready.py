"""发布就绪门自身的变异验证：8 条判据，逐条必须能红。

若某条变异后门仍绿，说明该判据是假门（skill 的"变异验证"纪律：判据有几个，变异就要几组）。
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
GATE_REL = "tools/check_publish_ready.py"


def _copy_repo(dest: Path) -> Path:
    """带 .git 的浅副本：P7/P8 依赖 git 状态，必须真拷一份 git 仓库（不是假目录）。"""

    root = dest / "repo"
    shutil.copytree(
        REPO,
        root,
        ignore=shutil.ignore_patterns(
            ".git", "build", "dist", "dist-release", "__pycache__", ".pytest_cache", "*.egg-info"
        ),
    )
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=gate-test",
            "-c",
            "user.email=gate-test@example.invalid",
            "commit",
            "-q",
            "-m",
            "sandbox baseline",
        ],
        cwd=root,
        check=True,
    )
    return root


def _run(root: Path, *args: str) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(root / GATE_REL), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return proc.returncode, proc.stdout + proc.stderr


def _fails(out: str) -> list[str]:
    return [line.split()[1] for line in out.splitlines() if line.startswith("FAIL")]


def _write_lf(path: Path, text: str) -> None:
    """显式 LF 写盘，**Python 3.9 兼容**。

    为什么不用 `Path.write_text` 的 `newline=` 参数（写在这里会连注释一起被判据扫到，
    所以刻意不写出完整调用式）：那个参数是 **3.10** 才加的，而本项目
    `requires-python >= 3.9` —— CI 首推首跑实测：3.9 通道上 14 条测试报
    `TypeError: write_text() got an unexpected keyword argument 'newline'`。
    判别 = **"我用的是不是 3.9 就有的写法？"**（这是 `plan/05` §五 U10 从"未实跑"变成"实跑结论"的那一格）。
    """

    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def _replace(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, f"变异锚点失配（变异没发生）: {old!r}"
    _write_lf(path, text.replace(old, new, 1))


@pytest.fixture()
def sandbox(tmp_path: Path) -> Path:
    return _copy_repo(tmp_path)


def test_baseline_is_green(sandbox: Path):
    code, out = _run(sandbox)
    assert code == 0, out


def test_p1_missing_readme_is_red(sandbox: Path):
    (sandbox / "README.md").unlink()
    code, out = _run(sandbox, "--allow-dirty")
    assert code == 1
    assert "P1.REQUIRED" in _fails(out)


def test_p2_tracked_artifact_is_red(sandbox: Path):
    dist = sandbox / "dist"
    dist.mkdir()
    (dist / "extract-oracle.exe").write_bytes(b"MZ fake")
    subprocess.run(["git", "add", "-f", "dist/extract-oracle.exe"], cwd=sandbox, check=True)
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "-m", "add artifact"],
        cwd=sandbox,
        check=True,
    )
    code, out = _run(sandbox)
    assert code == 1
    assert "P2.NO_ARTIFACTS" in _fails(out)


def test_p3_weak_gitignore_is_red(sandbox: Path):
    """删掉真正的 `dist/` 规则必须红——注意 `.gitignore` 里还有 `sdist/`，
    子串判定会被它命中（"短串吃掉长串"），所以本判据必须整行/归一化后比较。"""

    _replace(sandbox / ".gitignore", "\ndist/\n", "\n")
    code, out = _run(sandbox, "--allow-dirty")
    assert code == 1
    assert "P3.GITIGNORE" in _fails(out)
    assert "dist" in out


def test_p4_host_path_is_red(sandbox: Path):
    # 字面量在运行期拼出来：测试文件本身也在门的扫描面里，**不把 tests/ 加进豁免**
    # （否则"门比项目已声明的豁免更严 = 门错"会被反向滥用成"门给自己开后门"）。
    leak_text = "路径: " + "D:" + "/Program" + "Data/secret/x\n"
    leak = sandbox / "plan" / "LEAK.md"
    _write_lf(leak, leak_text)
    subprocess.run(["git", "add", "-A"], cwd=sandbox, check=True)
    code, out = _run(sandbox, "--allow-dirty")
    assert code == 1
    assert "P4.DESENSITIZED" in _fails(out)


def test_p4_desensitization_gate_self_exemption_is_reused(sandbox: Path):
    """反向：脱敏门脚本自带规则字面量，必须被豁免（否则门比项目已声明的豁免更严 = 门错）。"""

    code, out = _run(sandbox)
    assert code == 0, out
    assert "0 命中" in out


def test_p5_secret_forms_are_red(sandbox: Path):
    # 逐形态注入：token / 私钥头 / 带口令的 URL（字面量运行期拼接，见上一条的理由）
    samples = {
        "tok.md": "ghp_" + "A" * 36 + "\n",
        "key.md": "-----BEGIN RSA " + "PRIVATE KEY-----\n",
        "url.md": "https://user:supersecret" + "@example.com/x\n",
    }
    for name, body in samples.items():
        path = sandbox / "plan" / name
        _write_lf(path, body)
        subprocess.run(["git", "add", "-A"], cwd=sandbox, check=True)
        code, out = _run(sandbox, "--allow-dirty")
        assert code == 1, f"{name} 未触发 P5: {out}"
        assert "P5.NO_SECRETS" in _fails(out), out
        path.unlink()
        subprocess.run(["git", "add", "-A"], cwd=sandbox, check=True)


def test_p6_version_literal_is_red(sandbox: Path):
    path = sandbox / "pyproject.toml"
    _replace(path, 'dynamic = ["version"]', 'version = "0.1.0"')
    subprocess.run(["git", "add", "-A"], cwd=sandbox, check=True)
    code, out = _run(sandbox, "--allow-dirty")
    assert code == 1
    assert "P6.VERSION_SOURCE" in _fails(out)


def test_p7_dirty_tree_is_red_and_allow_dirty_downgrades(sandbox: Path):
    _write_lf(sandbox / "plan" / "WIP.md", "wip\n")
    code, out = _run(sandbox)
    assert code == 1
    assert "P7.CLEAN_TREE" in _fails(out)

    code2, out2 = _run(sandbox, "--allow-dirty")
    assert code2 == 0, out2
    assert "WARN  P7.CLEAN_TREE" in out2


def test_p8_bundle_is_actually_verified(sandbox: Path):
    """P8 正向自证：报告里的 ref 数必须等于真实 ref 数（防判据空跑）。"""

    code, out = _run(sandbox)
    assert code == 0, out
    real_refs = subprocess.run(
        ["git", "show-ref"], cwd=sandbox, capture_output=True, text=True, check=True
    ).stdout.strip().splitlines()
    assert f"{len(real_refs)} 个 ref 自洽" in out


def test_non_git_tree_returns_environment_missing(tmp_path: Path):
    """"这台机器做不了"与"事情还没做完"必须是两个退出码（3 vs 1）。"""

    root = tmp_path / "nogit"
    (root / "tools").mkdir(parents=True)
    shutil.copy2(REPO / GATE_REL, root / GATE_REL)
    code, out = _run(root)
    assert code == 3, out
    assert "不是 git 工作树" in out
