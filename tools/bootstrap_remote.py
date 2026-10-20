#!/usr/bin/env python3
"""建仓 + 首推（M6 前的最后一步；**默认 dry-run**）。

为什么默认 dry-run：建公开仓库是**对外动作**，且推送后无法"撤回成没发生"。
脚本把动作序列写死，让"我要推"变成一个显式参数，而不是一次手滑。

动作序列（与 `plan/05` §四 对齐，但**不含 tag/Release**——那些属 M6）：
  1. 发布就绪门（`tools/check_publish_ready.py`）必须全绿
  2. `gh auth status` 必须已登录
  3. `gh repo create <owner>/<repo> --public --source . --remote origin`（不存在时）
  4. `git push -u origin <branch>`
  5. 回读远端 sha 与本地 sha 比对（**推送成功的判据是 sha 相等，不是 push 的退出码**）
  6. `gh run list` 取该 sha 的 run，等首轮结束并打印结论

用法：
    py -3.12 tools/bootstrap_remote.py --repo <owner>/<repo>            # dry-run，只打印计划
    py -3.12 tools/bootstrap_remote.py --repo <owner>/<repo> --apply    # 真执行

退出码：0 成功（或 dry-run 通过）/ 1 有步骤失败 / 2 用法错误 / 3 环境缺失（gh 未登录、门未绿）。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2
EXIT_ENV = 3


def run(cmd: list[str], *, check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", check=check)


def say(step: str, detail: str) -> None:
    print(f"[{step}] {detail}")


def gate_ok() -> bool:
    proc = run([sys.executable, str(ROOT / "tools" / "check_publish_ready.py")])
    sys.stdout.write(proc.stdout)
    return proc.returncode == 0


def gh_ready() -> bool:
    proc = run(["gh", "auth", "status"])
    return proc.returncode == 0


def repo_exists(full: str) -> bool:
    proc = run(["gh", "api", f"repos/{full}", "--jq", ".full_name"])
    return proc.returncode == 0


def local_sha(branch: str) -> str:
    return run(["git", "rev-parse", branch]).stdout.strip()


def remote_sha(full: str, branch: str) -> str | None:
    proc = run(["gh", "api", f"repos/{full}/commits/{branch}", "--jq", ".sha"])
    return proc.stdout.strip() if proc.returncode == 0 else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bootstrap_remote")
    parser.add_argument("--repo", required=True, help="<owner>/<repo>")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--apply", action="store_true", help="真执行（默认 dry-run）")
    parser.add_argument("--wait-seconds", type=int, default=0, help="首推后等待 CI 的秒数（0 = 不等待）")
    args = parser.parse_args(argv)

    if "/" not in args.repo:
        say("usage", "--repo 必须是 <owner>/<repo>")
        return EXIT_USAGE

    say("1/6", "发布就绪门")
    if not gate_ok():
        say("1/6", "门未全绿 → 拒绝推送（先修门，不要靠 --apply 绕过）")
        return EXIT_ENV

    say("2/6", "gh 登录状态")
    if not gh_ready():
        say("2/6", "gh 未登录 → 环境缺失")
        return EXIT_ENV

    exists = repo_exists(args.repo)
    say("3/6", f"仓库 {args.repo} {'已存在' if exists else '不存在（将创建 public）'}")

    plan = [
        ["gh", "repo", "create", args.repo, "--public", "--source", ".", "--remote", "origin"],
        ["git", "push", "-u", "origin", args.branch],
    ]
    for cmd in plan:
        say("plan", " ".join(cmd))

    if not args.apply:
        say("dry-run", "未执行任何写操作（加 --apply 才真推）")
        return EXIT_OK

    if not exists:
        proc = run(plan[0])
        if proc.returncode != 0:
            say("3/6", f"建仓失败: {proc.stderr.strip()[:400]}")
            return EXIT_FAILED
        say("3/6", "建仓完成")

    say("4/6", "推送")
    proc = run(plan[1])
    if proc.returncode != 0:
        # 已知形态：直连失败但可能已成功 → 用 sha 相等判定，不看退出码
        say("4/6", f"push 返回 {proc.returncode}，按 sha 复核")
        sys.stderr.write(proc.stderr[-800:] + "\n")

    say("5/6", "sha 对账（推送成功的判据）")
    want = local_sha(args.branch)
    got = remote_sha(args.repo, args.branch)
    if got != want:
        say("5/6", f"远端 sha 不等：local={want[:12]} remote={(got or 'None')[:12]}")
        return EXIT_FAILED
    say("5/6", f"远端 sha == 本地 sha ({want[:12]})")

    say("6/6", "CI")
    if args.wait_seconds > 0:
        import time

        time.sleep(args.wait_seconds)
    proc = run(
        [
            "gh",
            "run",
            "list",
            "--json",
            "databaseId,headSha,event,conclusion,workflowName",
            "--limit",
            "10",
        ]
    )
    if proc.returncode != 0:
        say("6/6", "取 run 列表失败（可在 GitHub 页面查看）")
        return EXIT_FAILED
    runs = [r for r in json.loads(proc.stdout or "[]") if r.get("headSha") == want]
    if not runs:
        say("6/6", f"该 sha 尚无 run（CI 可能刚排队）: {want[:12]}")
        return EXIT_FAILED
    for item in runs:
        say("6/6", f"{item['workflowName']} event={item['event']} conclusion={item['conclusion']}")
    if any(item.get("conclusion") not in ("success", "skipped") for item in runs):
        say("6/6", "存在未成功的 run（首推红是诊断，不是失败——照实记录再修）")
        return EXIT_FAILED
    say("6/6", "全部 run 成功")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
