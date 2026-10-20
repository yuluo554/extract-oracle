#!/usr/bin/env python3
"""冻结态入口（PyInstaller 专用）。

为什么不能直接拿 `src/extract_oracle/__main__.py` 当脚本入口：PyInstaller 会把该文件当作
**顶层脚本**执行（`__package__ is None`），于是 `from .cli import main` 抛
`ImportError: attempted relative import with no known parent package`。
实测于 M0 首次打包（脚本态全绿、冻结态直接起不来——"源码态绿 ≠ 产物态绿"）。

本文件用**绝对导入**，构建脚本以它作为入口。
"""

from __future__ import annotations

import sys

from extract_oracle.cli import main

if __name__ == "__main__":
    sys.exit(main())
