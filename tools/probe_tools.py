#!/usr/bin/env python3
"""四工具对照实测（M1 落地；当前为**显式拒绝**的骨架）。

对照对象：Python `zipfile` / Info-ZIP `unzip` / 7-Zip / libarchive。
每格必须留"命令 + 输出节选"，M6 定稿成 `docs/divergence.md`——**手抄表不算证据**。

本脚本的纪律（`plan/01` §2 MOD-1 依据纪律）：
- 只记录**实际观察到的行为**，不推断；
- 工具缺失 → 该格记 `tool_unavailable` 并整体退出码 3（**不静默跳过**，否则矩阵看起来"全绿"）；
- 输出落 `data/tool-matrix/<fixture>.json`，确定性（无时间戳、无绝对路径）。

退出码：0 全部格实测完成 / 3 工具或 fixture 缺失 / 4 用法错误。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

EXIT_OK = 0
EXIT_CAPABILITY_MISSING = 3
EXIT_USAGE = 4

TOOLS = ("python-zipfile", "info-zip-unzip", "7zip", "libarchive")
PLANNED_OUTPUT = "data/tool-matrix/<fixture>.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="probe_tools", description="四工具行为对照（M1）")
    parser.add_argument("fixtures", nargs="*", default=["data/fixtures/mismatch_name.zip"])
    parser.add_argument("--out", default="data/tool-matrix")
    args = parser.parse_args(argv)

    missing = [name for name in args.fixtures if not Path(name).exists()]
    if missing:
        print(f"probe_tools: fixture 不存在: {', '.join(missing)}", file=sys.stderr)
        return EXIT_USAGE

    print(
        "probe_tools: 尚未实现（M1 落地）。\n"
        f"  对照工具: {', '.join(TOOLS)}\n"
        f"  计划产物: {PLANNED_OUTPUT}\n"
        "  本脚本拒绝产出空矩阵——空矩阵会让人以为'四个工具都正常'。",
        file=sys.stderr,
    )
    return EXIT_CAPABILITY_MISSING


if __name__ == "__main__":
    sys.exit(main())
