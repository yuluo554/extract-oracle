#!/usr/bin/env python3
"""发布就绪门（publish-ready）：把"这个仓库现在就能推上 GitHub"变成可跑红的断言。

为什么要有这道门：`plan/05` 的 M6 是"发不发布"的里程碑，而"**能不能推**"是每天都该成立的
仓库事实。两者混在一起，就会出现"到发布那天才发现仓库里躺着 dist/、或藏了一个 token"。
本门只判**可上传性**，不判是否已发布（是否已发布由 `plan/RELEASE-M6.md` 与远端事实判定）。

判据（每条都有对应变异，见 `tests/test_publish_ready.py`）：
  P1 必备件在位（README / LICENSE / .gitignore / .gitattributes / AGENTS.md / plan 套件 / CI）
  P2 没有构建产物/缓存被 git 跟踪（dist/ build/ __pycache__ *.pyc *.egg-info）
  P3 `.gitignore` 覆盖构建与缓存输出
  P4 无本机绝对路径 / 用户名 / 回环代理（复用脱敏门的判定，逐条点名）
  P5 无凭据形态（GitHub token / AWS key / 私钥头 / 连接串口令）
  P6 版本单一真源（pyproject dynamic + 根模块 __version__）
  P7 工作树干净（`--allow-dirty` 时降级为报告项）
  P8 **推送包自证**：`git bundle create --all` + `git bundle verify` 必须通过
     —— 这一条证明"远端要收的那些 ref 与对象全都在本地、且包自洽"，是"可推"最硬的本地证据。

退出码：0 全绿 / 1 有 FAIL / 2 用法错误 / 3 环境缺失（非 git 工作树、无 git 可执行）。
**刻意不进 CI**：P7/P8 依赖工作树状态与完整历史，浅克隆下会翻转（判据的环境敏感性）。
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CHECKS: list[tuple[str, str, bool, str]] = []  # (id, kind[PASS/FAIL/SKIP/WARN], ok, detail)


def add(check_id: str, ok: bool, detail: str, *, skip: bool = False, warn: bool = False) -> None:
    kind = "SKIP" if skip else ("WARN" if warn else ("PASS" if ok else "FAIL"))
    CHECKS.append((check_id, kind, ok, detail))


REQUIRED = [
    "README.md",
    "LICENSE",
    ".gitignore",
    ".gitattributes",
    "AGENTS.md",
    "pyproject.toml",
    ".github/workflows/ci.yml",
    "plan/00-README总览.md",
    "plan/01-题目文档.md",
    "plan/02-架构与技术选型.md",
    "plan/03-模块详设.md",
    "plan/04-数据计划.md",
    "plan/05-里程碑与发布.md",
    "plan/06-交付对标与决策.md",
    "data/README.md",
]

ARTIFACT_DIRS = ("dist/", "dist-release/", "build/", "__pycache__/", ".pytest_cache/", ".venv/", "venv/")
ARTIFACT_SUFFIXES = (".pyc", ".pyo", ".spec", ".manifest")

SECRET_RULES = [
    ("github-token", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}")),
    ("aws-access-key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("private-key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----")),
    ("url-with-password", re.compile(r"://[^/\s:@]+:[^/\s:@]{4,}@")),
]

#: 门自身必须写出被判据禁止的模式，按路径自豁免（并把豁免份数打进结论）。
#: 同族：`tools/check_desensitized.py` 是**它自己那条门**的自豁免文件（规则字面量在它里面），
#: 这里必须复用它的豁免声明，而不是另立一套更严的口径（"门比项目已声明的豁免更严 = 门错"）。
SELF = "tools/check_publish_ready.py"
SELF_EXEMPT = ("tools/check_publish_ready.py", "tools/check_desensitized.py")


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-c", "core.quotepath=false", *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=check,
    )


def is_git_tree() -> bool:
    if not (ROOT / ".git").exists():
        return False
    proc = git("rev-parse", "--is-inside-work-tree", check=False)
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def tracked_files() -> list[str]:
    out = git("ls-files", "-z").stdout
    return [p for p in out.split("\0") if p]


def check_required() -> None:
    missing = [rel for rel in REQUIRED if not (ROOT / rel).exists()]
    add("P1.REQUIRED", not missing, f"缺: {', '.join(missing)}" if missing else f"{len(REQUIRED)} 份齐备")


def check_no_tracked_artifacts(files: list[str]) -> None:
    bad = []
    for rel in files:
        if any(rel.startswith(d) or f"/{d}" in rel for d in ARTIFACT_DIRS):
            bad.append(rel)
        elif rel.endswith(ARTIFACT_SUFFIXES):
            bad.append(rel)
    add("P2.NO_ARTIFACTS", not bad, f"被跟踪的构建/缓存产物: {', '.join(bad[:5])}" if bad else f"扫了 {len(files)} 个跟踪文件，无产物")


def check_gitignore() -> None:
    """按**整行**判规则存在，不做子串匹配。

    实测（本门首版）：`need = "dist/"` 的 `in text` 子串判定被 `.gitignore` 里的 `sdist/`
    命中——删掉真正的 `dist/` 规则后门仍然绿（"短串吃掉长串"的假门形态）。
    正解 = 逐行 `strip()` 后与规则字面量比较（允许行尾注释与 `!` 取反前缀不参与）。
    """

    path = ROOT / ".gitignore"
    if not path.exists():
        add("P3.GITIGNORE", False, "缺 .gitignore")
        return
    lines = {line.strip() for line in path.read_text(encoding="utf-8").splitlines()}
    # 归一化：`dist/` 与 `dist` 是同一规则；但 `sdist/` 归一后是 `sdist`，**不与 `dist` 混淆**
    normalized = {line.rstrip("/") for line in lines if line and not line.startswith("#")}
    need = ["__pycache__", "dist", "build", "*.egg-info", ".pytest_cache"]
    missing = [n for n in need if n not in normalized]
    add(
        "P3.GITIGNORE",
        not missing,
        f"缺规则: {', '.join(missing)}" if missing else f"{len(need)} 条规则齐备（整行匹配，扫了 {len(lines)} 行）",
    )


def check_desensitized(files: list[str]) -> None:
    """复用脱敏门的四条规则：发布就绪门不另立一套更松/更严的口径。"""

    rules = [
        ("absolute-path", re.compile(r"\b[A-Za-z]:[\\/](?:ProgramData|Users|zcode|repos?|projects?)[\\/](?!<)")),
        ("msys-user-path", re.compile(r"/[a-z]/Users/(?!<)[A-Za-z0-9._-]+/")),
        ("host-username", re.compile(r"\bASUS\b")),
        ("loopback-proxy", re.compile(r"\b127\.0\.0\.1:\d{2,5}\b")),
    ]
    hits: list[str] = []
    scanned = 0
    for rel in files:
        if rel in SELF_EXEMPT:
            continue
        path = ROOT / rel
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if "\x00" in text:
            continue
        scanned += 1
        for number, line in enumerate(text.split("\n"), start=1):
            for rule_id, pattern in rules:
                if pattern.search(line):
                    hits.append(f"{rel}:{number}: [{rule_id}] {line.strip()[:120]}")
    if scanned == 0:
        add("P4.DESENSITIZED", False, "0 个可读文本文件——判据空跑（阳性对照失败）")
        return
    add("P4.DESENSITIZED", not hits, "；".join(hits[:6]) if hits else f"扫了 {scanned} 个文本文件，0 命中（豁免 {len(SELF_EXEMPT)} 份）")


def check_secrets(files: list[str]) -> None:
    hits: list[str] = []
    for rel in files:
        if rel in SELF_EXEMPT:
            continue
        try:
            text = (ROOT / rel).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for line_no, line in enumerate(text.split("\n"), start=1):
            for rule_id, pattern in SECRET_RULES:
                if pattern.search(line):
                    hits.append(f"{rel}:{line_no}: [{rule_id}] {line.strip()[:80]}")
    add("P5.NO_SECRETS", not hits, "；".join(hits[:6]) if hits else f"扫了 {len(files)} 个跟踪文件，无凭据形态")


def check_version_source() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    init = (ROOT / "src" / "extract_oracle" / "__init__.py").read_text(encoding="utf-8")
    dynamic = 'dynamic = ["version"]' in pyproject
    attr = 'version = { attr = "extract_oracle.__version__" }' in pyproject
    literal = bool(re.search(r'^version\s*=\s*"', pyproject, re.M))
    version_declared = bool(re.search(r'^__version__\s*=\s*"[^"]+"', init, re.M))
    ok = dynamic and attr and not literal and version_declared
    add(
        "P6.VERSION_SOURCE",
        ok,
        f"dynamic={dynamic} attr={attr} 无字面量={not literal} 根模块声明={version_declared}",
    )


def check_clean_tree(allow_dirty: bool) -> None:
    out = git("status", "--porcelain").stdout.strip()
    if not out:
        add("P7.CLEAN_TREE", True, "工作树干净，无未跟踪/未提交改动")
        return
    count = len(out.splitlines())
    if allow_dirty:
        add("P7.CLEAN_TREE", True, f"{count} 处未提交改动（--allow-dirty：降级为报告项）", warn=True)
        return
    add("P7.CLEAN_TREE", False, f"{count} 处未提交改动（推送前必须提交或 stash）")


def check_pushable_bundle() -> None:
    """`git bundle --all` + `verify`：证明远端会收到的那些 ref 与对象在本地齐备且自洽。"""

    with tempfile.TemporaryDirectory() as tmp:
        bundle = Path(tmp) / "pushable.bundle"
        created = git("bundle", "create", str(bundle), "--all", check=False)
        if created.returncode != 0:
            add("P8.PUSHABLE", False, f"bundle create 失败: {created.stderr.strip()[:200]}")
            return
        verified = git("bundle", "verify", str(bundle), check=False)
        size = bundle.stat().st_size
        refs = git("show-ref", check=False).stdout.strip().splitlines()
        if verified.returncode != 0:
            add("P8.PUSHABLE", False, f"bundle verify 失败: {verified.stderr.strip()[:200]}")
            return
        add(
            "P8.PUSHABLE",
            True,
            f"bundle {size} 字节、{len(refs)} 个 ref 自洽（远端可收的全部对象在本地）",
        )


def run(allow_dirty: bool) -> int:
    if not is_git_tree():
        print("发布就绪门：当前目录不是 git 工作树（SKIP 全部判据）")
        return 3

    files = tracked_files()
    if not files:
        print("发布就绪门：git 里没有任何跟踪文件（判据空跑）")
        return 1

    for step, args in (
        (check_required, ()),
        (lambda: check_no_tracked_artifacts(files), ()),
        (check_gitignore, ()),
        (lambda: check_desensitized(files), ()),
        (lambda: check_secrets(files), ()),
        (check_version_source, ()),
        (lambda: check_clean_tree(allow_dirty), ()),
        (check_pushable_bundle, ()),
    ):
        try:
            step(*args)
        except Exception as exc:  # 门永不崩
            add(getattr(step, "__name__", "step"), False, f"{exc.__class__.__name__}: {exc}")

    failed = [c for c in CHECKS if c[1] == "FAIL"]
    print("发布就绪门（可上传性） · 不判是否已发布")
    print("=" * 56)
    for check_id, kind, _ok, detail in CHECKS:
        print(f"{kind:<4}  {check_id}  {detail}")
    print("=" * 56)
    print(f"这轮扫到：跟踪文件 {len(files)} / 判据 {len(CHECKS)}")
    print(f"结论: {'全绿' if not failed else f'{len(failed)} 项 FAIL'}")
    return 0 if not failed else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="check_publish_ready")
    parser.add_argument("--allow-dirty", action="store_true", help="允许未提交改动（降级为 WARN）")
    args = parser.parse_args(argv)
    return run(args.allow_dirty)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
