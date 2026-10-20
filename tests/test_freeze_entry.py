"""冻结态入口契约：源码态绿 ≠ 产物态绿。

M0 首次打包实测到的真缺陷：以 `src/extract_oracle/__main__.py` 作为 PyInstaller 入口时，
该文件被当作**顶层脚本**执行（`__package__ is None`），`from .cli import main` 抛
`ImportError: attempted relative import with no known parent package`——脚本态、全部测试全绿，
产物一运行就崩。本文件把"入口必须是绝对导入的薄壳"钉成常驻断言。
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENTRY = REPO / "scripts" / "entry.py"
BUILD = REPO / "scripts" / "build.py"


def test_freeze_entry_uses_absolute_import_only():
    tree = ast.parse(ENTRY.read_text(encoding="utf-8"))
    relative = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and (node.level or 0) > 0
    ]
    assert relative == [], "冻结态入口不得使用相对导入（PyInstaller 按顶层脚本执行它）"
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert "extract_oracle.cli" in imported


def test_build_script_points_at_the_absolute_entry():
    """反向：构建脚本若拿 `src/extract_oracle/__main__.py` 当入口，本断言必红。

    判据只看"它把哪个文件交给了 PyInstaller"，不扫全文——构建脚本的注释里**必须**能
    解释这个坑（写清 `__main__.py` 为何不行），扫全文会把那条解释判成违规（判据张冠李戴）。
    """

    lines = [
        line.strip()
        for line in BUILD.read_text(encoding="utf-8").splitlines()
        if "entry.py" in line or "__main__.py" in line
    ]
    assert lines, "构建脚本里找不到入口声明"
    # 非注释行（真正的参数行）
    code_lines = [line for line in lines if not line.startswith("#")]
    assert any("entry.py" in line for line in code_lines), "构建脚本必须使用 scripts/entry.py 作为入口"
    assert not any("__main__.py" in line for line in code_lines), "不得把 __main__.py 当冻结入口"


def test_build_script_fails_loudly_on_self_check():
    """产物自检失败不得被当成成功（此前 `check=True` 直接抛栈，rc 语义也不对）。"""

    text = BUILD.read_text(encoding="utf-8")
    assert "out.returncode != 0" in text
    assert "return 1" in text
