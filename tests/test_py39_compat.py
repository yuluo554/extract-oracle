"""Python 3.9 兼容守门：`requires-python >= 3.9` 的仓库里，**测试**也要守住 3.9。

为什么值得单独一条：CI 首推首跑实测过两次**同一类**事故——
`Path.write_text(..., newline="\\n")` 是 **3.10** 才加的签名，而它在
`tests/` 里出现时，3.9 三格各报十几条 `TypeError`；修完之后**新写的测试又写了一次**
（`test_ci_smoke_scripts.py`），于是 3.9 三格再次红。判别 = **"我这次改的是代码还是测试？
3.9 通道对两者一样严格。"**

判据落**语法树 + 常量**，不落"人记得住"：
1. 任何 `.write_text(...)` / `.read_text(...)` 调用不得出现 `newline=` 关键字；
2. 任何 `.write_text(...)` 不得出现 `errors=` 关键字（同样是 3.10 才加的）；
3. 兜底：`tests/` 与 `src/` 里不得出现 `from __future__ import annotations` **之外**的
   3.10+ 专属语法（`match` 语句、`X | Y` 运行时联合类型不做静态判定——它们已被
   `from __future__ import annotations` 与项目约定覆盖，这里只守会**在运行期炸**的那类）。

第 3 条刻意窄：只抓"调用参数签名"这类**运行期必炸**的形态，避免把合法写法误判。
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SOURCES = sorted(
    [*(REPO / "tests").glob("*.py"), *(REPO / "src" / "extract_oracle").rglob("*.py"), *(REPO / "tools").glob("*.py")]
)

#: 3.10 才加进 `Path.write_text/read_text` 的关键字（运行期直接 `TypeError`）。
BANNED_KWARGS = {"write_text": {"newline", "errors"}, "read_text": {"errors"}}


def _scanned_sources() -> list[Path]:
    assert SOURCES, "没扫到任何源文件（抽取面坏了）"
    return SOURCES


@pytest.mark.parametrize("path", _scanned_sources(), ids=lambda p: str(p.relative_to(REPO)))
def test_no_python310_only_path_text_kwargs(path: Path) -> None:
    """`write_text(newline=…)` / `read_text(errors=…)` 在 3.9 上是 `TypeError`（运行期必炸）。"""

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute):
            continue
        banned = BANNED_KWARGS.get(func.attr)
        if not banned:
            continue
        for keyword in node.keywords:
            if keyword.arg in banned:
                offenders.append(f"{path.relative_to(REPO)}:{node.lineno}: .{func.attr}({keyword.arg}=…)")
    assert offenders == [], (
        "这些调用在 Python 3.9 上会抛 TypeError（改用 `open(path, 'w', encoding='utf-8', newline='\\n')`）：\n"
        + "\n".join(offenders)
    )


def test_scanned_sources_include_tests_and_src():
    """非空跑自证：扫描面必须同时覆盖 `tests/` 与 `src/`（只扫一侧会漏掉另一半）。"""

    rels = [path.relative_to(REPO).as_posix() for path in SOURCES]
    assert any(rel.startswith("tests/") for rel in rels), "扫描面缺 tests/"
    assert any(rel.startswith("src/") for rel in rels), "扫描面缺 src/"
    assert len(rels) >= 20, f"只扫到 {len(rels)} 个文件（抽取面疑似坏了）"