"""Python floor 守门：本项目声明 `requires-python >= 3.12`，**源码里不得出现高于 floor 的写法**。

> **文件名的来历与本次改写**（2026-10-23）：本文件原守的是当时的 floor `requires-python >= 3.9`，
> 判据是"禁 3.10 才加的 `Path.write_text(newline=…)` 一类签名"。
> 2026-10-23 抬 floor 到 3.12 后，**那条判据失去意义**（`newline=` 在 3.12 上完全合法），
> 按迭代路线选项③**保留本文件、把判据换成「不要无意中抬 floor」**：
> floor 声明 3.12，而有人写了 3.13 才有的 API，就在本地先红一次，而不是只在 CI 的 3.12 腿上红。
> 文件名保持不动，因为 `plan/05` §五 U27 与 `tools/` 的注释都以它指代这条守门（那些是 M6 的实测记录）。
> 旧判据的完整动机（两次真实 3.9 事故）仍在 U27 与 `plan/05` §5.1 里，**不删**。

判据（**全部静态**——CI 的 3.13 腿也要能跑绿，所以判据不依赖"跑测试的解释器版本"）：

1. **floor 从 `pyproject.toml` 机器读出**（不手抄）：解析 `requires-python` 的 `>=X.Y`。
2. **高于 floor 的 API 表**：每条声明 `since=(major, minor)`；自证这张表**确实高于** floor
   （否则就是把 floor 自身的 API 误列进来，判据会变成"门比项目声明更严 = 门错"）。
3. **AST 扫描** `tests/` + `src/` + `tools/`：禁掉上表的 `owner.attr` 属性访问与
   `from owner import attr` 形态。
4. **负控**：喂一段含被禁写法的合成源码，审计函数必须报出它（证明这条门**会红**）。
5. **非空跑自证**：扫描面必须同时覆盖 `tests/` 与 `src/`（只扫一侧会漏掉另一半）。

**刻意窄的一处**（沿用原判据"只抓会炸的那类"的取舍）：**字符串形态**的注解（`x: "typing.TypeIs"`）
扫不到 —— 那种写法在运行期不炸，只会让 `get_type_hints()` 拿不到类型；本判据只管会破坏 floor 承诺的那一类。
"""

from __future__ import annotations

import ast
import re
import tomllib
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
PYPROJECT = REPO / "pyproject.toml"
SOURCES = sorted(
    [*(REPO / "tests").glob("*.py"), *(REPO / "src" / "extract_oracle").rglob("*.py"), *(REPO / "tools").glob("*.py")]
)

#: 高于 floor 的 API 表：键 = `(owner, attr)`（owner 取点号路径的**倒数第二段**，见 `_scan_dotted`），
#: 值 = 该 API 首次出现的 `(major, minor)`。
#: 表里全部是 **3.13** 才加的（floor = 3.12），每一条都在本机 3.12.10 上实测 `hasattr(...) == False`
#: （见 `test_above_floor_api_is_absent_from_the_floor_interpreter` 的同族探针，以及 `01-迭代路线` 批 1）。
#: 键取"倒数第二段"是为了同时接住 `os.path.isreserved` 与 `from os import path; path.isreserved` 两种写法。
ABOVE_FLOOR_APIS: dict[tuple[str, str], tuple[int, int]] = {
    ("warnings", "deprecated"): (3, 13),
    ("typing", "TypeIs"): (3, 13),
    ("typing", "ReadOnly"): (3, 13),
    ("typing", "NoDefault"): (3, 13),
    ("math", "fma"): (3, 13),
    ("path", "isreserved"): (3, 13),  # os.path.isreserved
    ("glob", "translate"): (3, 13),
    ("copy", "replace"): (3, 13),
}


def _declared_floor() -> tuple[int, int]:
    """从 `pyproject.toml` 读出 floor（**不手抄**：手抄的值会与声明脱钩）。"""

    doc = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    rp = (doc.get("project") or {}).get("requires-python") or ""
    match = re.search(r">=\s*(\d+)\.(\d+)", rp)
    assert match, f"pyproject 的 requires-python 解析不出下界：{rp!r}"
    return int(match.group(1)), int(match.group(2))


def _dotted(node: ast.AST) -> str | None:
    """把属性链摊平成点号名（`os.path.isreserved`）；根不是 `Name`（如 `a().b`）则返回 None。"""

    parts: list[str] = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
        return ".".join(reversed(parts))
    return None


def scan_source(text: str, rel: str) -> list[str]:
    """返回该源码里所有"高于 floor 的 API"用法描述（空 = 合规）。纯函数，供负控喂合成源码。"""

    tree = ast.parse(text, filename=rel)
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            dotted = _dotted(node)
            if not dotted:
                continue
            parts = dotted.split(".")
            if len(parts) >= 2 and (parts[-2], parts[-1]) in ABOVE_FLOOR_APIS:
                since = ABOVE_FLOOR_APIS[(parts[-2], parts[-1])]
                hits.append(f"{rel}:{node.lineno}: {dotted}（{since[0]}.{since[1]} 才加的 API）")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            owner = module.split(".")[-1] if module else ""
            for alias in node.names:
                key = (owner, alias.name)
                if key in ABOVE_FLOOR_APIS:
                    since = ABOVE_FLOOR_APIS[key]
                    hits.append(
                        f"{rel}:{node.lineno}: from {module} import {alias.name}"
                        f"（{since[0]}.{since[1]} 才加的 API）"
                    )
    return hits


def _scanned_sources() -> list[Path]:
    assert SOURCES, "没扫到任何源文件（抽取面坏了）"
    return SOURCES


@pytest.mark.parametrize("path", _scanned_sources(), ids=lambda p: str(p.relative_to(REPO)))
def test_no_api_above_the_declared_floor(path: Path) -> None:
    """源码里不得出现高于 floor 的 API —— 否则本地绿、CI 的 floor 腿红（差别只是"谁先发现"）。"""

    rel = path.relative_to(REPO).as_posix()
    hits = scan_source(path.read_text(encoding="utf-8"), rel)
    assert hits == [], "以下用法高于声明的 Python floor（改用 floor 上就有的写法）：\n" + "\n".join(hits)


def test_banned_table_is_strictly_above_the_declared_floor() -> None:
    """自证：表里每一条都必须**严格高于** floor（不是把 floor 自身的 API 误列进来）。"""

    floor = _declared_floor()
    assert ABOVE_FLOOR_APIS, "被禁 API 表是空的——判据空跑"
    not_above = sorted(key for key, since in ABOVE_FLOOR_APIS.items() if since <= floor)
    assert not_above == [], f"这些条目不高于 floor {floor}（门比项目声明更严 = 门错）：{not_above}"


def test_floor_is_at_least_312() -> None:
    """本次迭代的 floor 决定（3.9 已于 2025-10 EOL）不许悄悄回退。"""

    assert _declared_floor() >= (3, 12), f"floor 被退回 {_declared_floor()}（3.9 已 EOL）"


# ---- 审计函数自身的正/负控（证明这条门会红，也证明它不误报）----


def test_auditor_flags_above_floor_api() -> None:
    """负控：3.13 才有的 API 必须被抓到。"""

    hits = scan_source("import copy\nx = copy.replace(obj, a=1)\n", "<synthetic>")
    assert hits, "负控失败：高于 floor 的 API 没被抓到（假门形态）"


def test_auditor_flags_above_floor_import_form() -> None:
    """负控（import 形态）：`from typing import TypeIs` 也要抓到。"""

    hits = scan_source("from typing import TypeIs\n", "<synthetic>")
    assert hits, "负控失败：`from … import` 形态没被抓到"


def test_auditor_accepts_floor_api() -> None:
    """正控：floor（3.12）上就有的 API 不得被误报。"""

    assert scan_source("import itertools\nx = itertools.batched([1, 2], 1)\n", "<synthetic>") == []


def test_scanned_sources_include_tests_and_src():
    """非空跑自证：扫描面必须同时覆盖 `tests/` 与 `src/`（只扫一侧会漏掉另一半）。"""

    rels = [path.relative_to(REPO).as_posix() for path in SOURCES]
    assert any(rel.startswith("tests/") for rel in rels), "扫描面缺 tests/"
    assert any(rel.startswith("src/") for rel in rels), "扫描面缺 src/"
    assert len(rels) >= 20, f"只扫到 {len(rels)} 个文件（抽取面疑似坏了）"