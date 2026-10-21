#!/usr/bin/env python3
"""单文件可执行构建（PyInstaller onefile）。

口径（`plan/02` §三）：
- 版本号取自 `extract_oracle.__version__`（单一真源），构建后断言产物自报一致；
- **PyInstaller 产物含构建期 PE 时间戳 → 同机两次构建 sha256 不同是设计如此**，
  发布对账只做"树一致才哈希强对账"，换机构建只验结构口径；
- 构建在干净工作目录里跑（`--workpath` / `--specpath` / `--distpath` 全部显式给出）。

用法：
    py -3.12 scripts/build.py [--dist dist] [--clean]
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from extract_oracle import __version__  # noqa: E402

NAME = "extract-oracle"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="build")
    parser.add_argument("--dist", type=Path, default=ROOT / "dist")
    parser.add_argument("--clean", action="store_true", help="先删 build/ 与 dist/")
    args = parser.parse_args(argv)

    build_dir = ROOT / "build" / "pyinstaller"
    if args.clean:
        for path in (build_dir, args.dist):
            if path.exists():
                shutil.rmtree(path)

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--noconfirm",
        "--clean",
        "--name",
        NAME,
        "--distpath",
        str(args.dist),
        "--workpath",
        str(build_dir),
        "--specpath",
        str(build_dir),
        "--paths",
        str(ROOT / "src"),
        # 平台语义表是**运行期数据**（`platforms.py::candidate_dirs` 的 `_MEIPASS` 分支就是为它写的）：
        # 不随包分发，冻结态的 `check` / `platforms --verify` 会在中立目录里退 3
        # （`platform_missing`）。M6 首次在中立目录冒烟时实测到这一格，故把 `data/platforms/`
        # 里的两个文件打进产物（DEST 必须是 `data/platforms`，与 `candidate_dirs` 对齐）。
        "--add-data",
        f"{ROOT / 'data' / 'platforms'}{os.pathsep}data/platforms",
        # 入口必须是**绝对导入**的薄壳：PyInstaller 把入口当顶层脚本执行，
        # `__main__.py` 里的相对导入会抛 ImportError（M0 首次打包实测）。
        str(ROOT / "scripts" / "entry.py"),
    ]
    print("running:", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=ROOT)

    exe = args.dist / (f"{NAME}.exe" if sys.platform == "win32" else NAME)
    if not exe.exists():
        print(f"FAIL  产物不存在: {exe}")
        return 1

    # 产物自报版本必须与根模块一致（版本号第三条断言，前两条见 tests/）
    # `errors="replace"`：子进程在非 UTF-8 控制台上的输出可能不是合法 UTF-8，
    # 不加这个参数会让读取线程抛 UnicodeDecodeError（实测于 M6 首次跑 `platforms --verify`）。
    out = subprocess.run([str(exe), "--version"], capture_output=True, text=True, errors="replace")
    reported = out.stdout.strip()
    if out.returncode != 0 or __version__ not in reported:
        print(f"FAIL  产物自检失败（rc={out.returncode}）")
        print(f"  stdout: {reported!r}")
        print(f"  stderr: {out.stderr.strip()[:800]!r}")
        return 1
    print(f"OK    {exe}  (self-reported: {reported})")

    # 第二条产物自检：**在中立工作目录里**证明平台表随包分发且 `sha256` 对得上。
    # 为什么必须换 cwd：冻结态若只从 `Path.cwd()/data/platforms` 找表，在仓库根跑会**假装**通过，
    # 换到干净机器就退 3（M6 实测到的正是这一格）。所以这条断言把 cwd 换成空目录。
    with tempfile.TemporaryDirectory(prefix="oracle-buildcheck-") as neutral:
        verified = subprocess.run(
            [str(exe), "platforms", "--verify"],
            capture_output=True,
            text=True,
            errors="replace",
            cwd=neutral,
        )
    if verified.returncode != 0:
        print(f"FAIL  中立目录里平台表校验失败（rc={verified.returncode}）——产物未自带平台表？")
        print(f"  stdout: {verified.stdout.strip()[:800]!r}")
        print(f"  stderr: {verified.stderr.strip()[:800]!r}")
        return 1
    print("OK    中立目录 platforms --verify 通过（平台表随包分发）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
