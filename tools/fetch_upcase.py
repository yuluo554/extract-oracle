#!/usr/bin/env python3
"""取 NTFS `$UpCase` 表（M1 落地；当前为**显式拒绝**的骨架）。

为什么先落一个会拒绝的骨架而不是留空：`plan/02` §四 把表定义为"判定口径的数据来源"，
而 `AGENTS.md`/`HANDOFF-M1` 已经点名了本脚本。按布局门 `LAYOUT.DOC_TOOLS` 的纪律，
被文档点名的工具必须有实物——**一个显式说"我还不能做"的脚本，比一个不存在的引用诚实**。

真实实现（M1）两条通道，二选一，由 `--source` 指定：
- `volume-read`：打开卷句柄取 `$UpCase` 元文件（需管理员权限）；
- `host-probe`：在本机卷上逐个字符对实测折叠关系，生成表并记录探测环境。

产物契约见 `plan/02` §四：`data/platforms/ntfs-upcase.bin` + `data/platforms/meta.json`，
`meta.json.source` 只允许 `volume_read` / `host_probe`——**`casefold` 不是合法取值**。

退出码（与 `data/README.md` §4.1 一致）：0 成功 / 3 口径或能力缺失 / 4 用法错误。
"""

from __future__ import annotations

import argparse
import sys

EXIT_OK = 0
EXIT_CAPABILITY_MISSING = 3
EXIT_USAGE = 4

PLANNED_OUTPUTS = ("data/platforms/ntfs-upcase.bin", "data/platforms/meta.json")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fetch_upcase", description="取 NTFS $UpCase 表（M1）")
    parser.add_argument("--source", choices=("volume-read", "host-probe"), required=True)
    parser.add_argument("--out", default="data/platforms")
    parser.add_argument("--volume", default=None, help="volume-read 时的卷标，如 C:")
    args = parser.parse_args(argv)

    if args.source == "volume-read" and not args.volume:
        print("fetch_upcase: --source volume-read 需要 --volume", file=sys.stderr)
        return EXIT_USAGE

    print(
        "fetch_upcase: 尚未实现（M1 落地）。\n"
        f"  计划产物: {', '.join(PLANNED_OUTPUTS)}\n"
        f"  计划来源: {args.source.replace('-', '_')}\n"
        "  本脚本拒绝产出占位表——用 casefold 近似或编造表都会让 MOD-3 的判定失真。",
        file=sys.stderr,
    )
    return EXIT_CAPABILITY_MISSING


if __name__ == "__main__":
    sys.exit(main())
