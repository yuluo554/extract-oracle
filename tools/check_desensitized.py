#!/usr/bin/env python3
"""脱敏门：本机绝对路径 / 用户名 / 回环代理端口，零命中才允许发布。

与布局门并排进 CI 的 layout job。为什么是门而不是一次 grep：发布之后任何一次改动
都可能把本机路径带回来（`references/templates/check-desensitized.mjs` 实测 7 处真泄露）。

四条规则（每条配一组注入变异，见 `plan/05`）：
  V1 `D:/ProgramData/<x>`            → absolute-path
  V2 `C:\\Users\\<真实用户名>\\x`     → absolute-path + host-username
  V3 `/c/Users/<真实用户名>/x`        → msys-user-path
  V4 `127.0.0.1:7897`                → loopback-proxy

三条实测口径：① 占位符必须放行（`C:\\Users\\<user>\\…` / `<repo>`）；② 公开镜像不是私有代理
（只认回环/私网）；③ 门要豁免自己并把豁免份数打进结论行。

退出码：0 零命中 / 1 有命中 / 2 用法错误。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SELF = "tools/check_desensitized.py"

#: `update/` 是**迭代交接目录**（诊断方只写、执行方续写），不是交付面 —— 它不随仓库分发，
#: 所以门不扫它（实测：不排除时，往 `update/` 写一条盘符路径会让整仓隐私门 exit 1）。
SKIP_DIRS = {".git", ".tmp", "dist", "dist-release", "node_modules", ".cache", ".venv", "venv", "build", "__pycache__", ".pytest_cache", "update"}
SKIP_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".zip", ".gz", ".exe", ".dll", ".pdf", ".woff", ".woff2", ".bin"}

RULES = [
    ("absolute-path", re.compile(r"\b[A-Za-z]:[\\/](?:ProgramData|Users|zcode|repos?|projects?)[\\/](?!<)")),
    ("msys-user-path", re.compile(r"/[a-z]/Users/(?!<)[A-Za-z0-9._-]+/")),
    # 本机用户名（实测值；换机器改这一行，别用环境实算——runner 上叫 runner）
    ("host-username", re.compile(r"\bASUS\b")),
    ("loopback-proxy", re.compile(r"\b127\.0\.0\.1:\d{2,5}\b")),
]


def walk(directory: Path):
    for entry in sorted(directory.iterdir()):
        if entry.name == ".git":
            continue  # 目录形态与 worktree 文件形态一起挡
        if entry.is_dir():
            if entry.name in SKIP_DIRS:
                continue
            yield from walk(entry)
            continue
        if not entry.is_file():
            continue
        if entry.suffix in SKIP_EXTS:
            continue
        yield entry


def main(argv: list[str]) -> int:
    if argv:
        sys.stderr.write("check_desensitized: 不接参数\n")
        return 2

    hits: list[str] = []
    scanned = 0
    for path in walk(ROOT):
        rel = path.relative_to(ROOT).as_posix()
        if rel == SELF:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if "\x00" in text:
            continue
        scanned += 1
        for number, line in enumerate(text.split("\n"), start=1):
            for rule_id, pattern in RULES:
                if pattern.search(line):
                    hits.append(f"{rel}:{number}: [{rule_id}] {line.strip()[:160]}")

    if hits:
        print(f"脱敏门：{len(hits)} 处命中（扫了 {scanned} 个文本文件，豁免 {SELF}）")
        for hit in hits:
            print(f"FAIL  {hit}")
        return 1
    print(f"脱敏门：扫了 {scanned} 个文本文件，0 命中（豁免 {SELF}）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
