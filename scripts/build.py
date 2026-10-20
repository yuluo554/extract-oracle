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
import shutil
import subprocess
import sys
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
        str(ROOT / "src" / "extract_oracle" / "__main__.py"),
    ]
    print("running:", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=ROOT)

    exe = args.dist / (f"{NAME}.exe" if sys.platform == "win32" else NAME)
    if not exe.exists():
        print(f"FAIL  产物不存在: {exe}")
        return 1

    # 产物自报版本必须与根模块一致（版本号第三条断言，前两条见 tests/）
    out = subprocess.run([str(exe), "--version"], capture_output=True, text=True, check=True)
    reported = out.stdout.strip()
    if __version__ not in reported:
        print(f"FAIL  产物自报版本不含 {__version__}: {reported!r}")
        return 1
    print(f"OK    {exe}  (self-reported: {reported})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
