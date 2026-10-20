"""K10 的 AST 守门：判定模块互不 import；`rules` 不得 import `cli`。

`plan/02` §二 的依赖方向是 `cli → rules → archive`，**单向**。这条纪律用运行时 import
测不出来（Python 不在乎谁 import 谁，环也能跑），所以判据必须落在**语法树**上。

四条判据：

1. `rules/*` 之间零互相 import（防环形依赖，也让每个模块能对合成输入单测）；
2. `rules/*` 不得 import `cli`（判定层不知道 CLI 存在）；
3. `zip_reader`（字节层）不得 import `rules`（字节层不做判定，`plan/02` §一 第一条）；
4. `rules/*` 不得出现 `casefold` / `.lower()` / `.upper()` 调用（`plan/00` 决策 ③：
   M2–M5 不得用近似法替代真实折叠表）。

第 4 条在这里而不是在 MOD-3 里：它是**跨里程碑的禁令**，越早立越省事——M2 写的模块
一旦埋进 `casefold`，M3 接手时很难发现。
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "src" / "extract_oracle"
RULES = SRC / "rules"


def _rule_modules() -> list[Path]:
    return sorted(RULES.glob("*.py"))


def _imports(path: Path) -> set[str]:
    """该文件 import 的模块全名（相对 import 还原成 `extract_oracle.x.y`）。"""

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    package = "extract_oracle.rules" if path.parent == RULES else "extract_oracle"
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package.rsplit(".", node.level - 1)[0] if node.level > 1 else package
                module = f"{base}.{node.module}" if node.module else base
            else:
                module = node.module or ""
            found.add(module)
            for alias in node.names:
                found.add(f"{module}.{alias.name}")
    return found


def test_rules_modules_are_discovered():
    """非空跑自证：一个模块都没扫到，说明判据是空的。"""

    assert {path.name for path in _rule_modules()} >= {"__init__.py", "structure.py", "encoding.py"}


@pytest.mark.parametrize("path", _rule_modules(), ids=lambda p: p.name)
def test_rules_do_not_import_each_other(path: Path):
    """判定模块之间零依赖（共享形状契约在包根 `findings.py`，那不是判定模块）。"""

    siblings = {f"extract_oracle.rules.{other.stem}" for other in _rule_modules() if other != path}
    siblings.discard(f"extract_oracle.rules.{path.stem}")
    offenders = sorted(
        name for name in _imports(path) if any(name == s or name.startswith(s + ".") for s in siblings)
    )
    assert offenders == [], f"{path.name} 引用了其他判定模块: {offenders}"


@pytest.mark.parametrize("path", _rule_modules(), ids=lambda p: p.name)
def test_rules_do_not_import_cli(path: Path):
    offenders = sorted(name for name in _imports(path) if name.startswith("extract_oracle.cli"))
    assert offenders == [], f"{path.name} 引用了 CLI: {offenders}"


def test_byte_layer_does_not_import_rules():
    """`plan/02` §一：字节层不做判定。`zip_reader` 引用 `rules` 即边界破了。"""

    offenders = sorted(name for name in _imports(SRC / "zip_reader.py") if ".rules" in name)
    assert offenders == [], f"zip_reader 引用了判定层: {offenders}"


@pytest.mark.parametrize("path", _rule_modules(), ids=lambda p: p.name)
def test_rules_do_not_use_approximate_casing(path: Path):
    """决策 ③ 的 AST 形态：`casefold` 与大小写转换调用一律不许出现在判定层。

    真实的折叠只能来自 `data/platforms/ntfs-upcase.bin`（M3 接入）。
    用 `str.lower()`/`casefold()` 近似会在 `ǅ/Ǆ` 上产出假阳性（`data/README.md` §1.3.3）。
    """

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in {"casefold", "lower", "upper"}:
            offenders.append(f"{node.attr}() @ line {node.lineno}")
        if isinstance(node, ast.Name) and node.id in {"casefold"}:
            offenders.append(f"name {node.id} @ line {node.lineno}")
    assert offenders == [], f"{path.name} 用了近似大小写: {offenders}"


def test_no_network_imports_in_any_module():
    """零网络（`plan/00` 硬纪律②）的静态面：交付态代码里不得有网络库 import。"""

    banned = {
        "socket",
        "ssl",
        "http",
        "urllib",
        "urllib3",
        "requests",
        "httpx",
        "ftplib",
        "telnetlib",
        "smtplib",
    }
    offenders: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        for name in _imports(path):
            root = name.split(".")[0]
            if root in banned:
                offenders.append(f"{path.name} → {name}")
    assert offenders == [], f"交付态代码引用了网络库: {offenders}"
