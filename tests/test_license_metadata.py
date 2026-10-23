# -*- coding: utf-8 -*-
"""许可证元数据形态守门（PEP 639，SI-013）。

背景：`license = { text = "MIT" }` / `{ file = "LICENSE" }` 这种 TOML 表形态已被
setuptools 弃用，硬期限 **2027-02-18**（实测 setuptools 84.2.1）：

    `project.license` as a TOML table is deprecated
    Please use a simple string containing a SPDX expression for `project.license`.
    You can also use `project.license-files`. (Both options available on setuptools>=77.0.0).

改用 SPDX 字符串有两个连带约束，本测试一并钉死：

1. **构建后端下限必须 >=77** —— 否则 pyproject 不生效（旧 setuptools 不认 string 形态）；
2. **不能保留 `License ::` classifier** —— setuptools>=77 会**硬报错**而不是警告：
   `InvalidConfigError: License classifiers have been superseded by license expressions`；
3. **requires-python 必须 >=3.12** —— 两个下界叠加后取更严的那个：① setuptools>=77 自身要求
   Python>=3.9（实测 `pip index versions setuptools --python-version 3.8` → LATEST 75.3.4）；
   ② 本项目 2026-10-23 的决定把 floor 从 3.9（**已于 2025-10 EOL**）抬到 3.12。
   这条是把两个下界一起写成机检，防止有人只改其中一处就提交。

第 5~7 条是**审计函数自身的负控**：喂合成的错误输入，必须报错。没有这组，
上面的断言只证明「当前文件是对的」，不证明「这个门会红」。
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = REPO_ROOT / "pyproject.toml"

#: floor 下界的机检值。改这个值等于改项目对外的 Python 承诺 —— 与
#: `tests/test_py39_compat.py`（守"源码里不得出现高于 floor 的 API"）成对。
REQUIRED_FLOOR = (3, 12)


def _load_toml(text):
    """用标准库 `tomllib`（floor 3.12 起它就在标准库里）。

    历史：3.9 通道存在时这里还有一条 `pytest.importorskip("tomli")` 的回退分支
    （配合 `pyproject` 的 `tomli>=2; python_version < '3.11'` 条件依赖）。
    floor 抬到 3.12 后该分支**永不成立**、条件依赖也已删除，故一并去掉 —— 死分支留着会
    让人以为"这个门还支持更老的解释器"。
    """
    return tomllib.loads(text)


def audit_pyproject(text):
    """返回违规描述列表（空 = 合规）。纯函数，供负控直接喂合成文本。"""
    problems = []
    doc = _load_toml(text)
    project = doc.get("project") or {}

    lic = project.get("license")
    if isinstance(lic, dict):
        problems.append(
            "project.license 仍是 TOML 表形态 %r（PEP 639 已弃用，硬期限 2027-02-18）" % (lic,)
        )
    elif not isinstance(lic, str) or not lic.strip():
        problems.append("project.license 缺失或不是 SPDX 表达式字符串：%r" % (lic,))

    files = project.get("license-files")
    if files != ["LICENSE"]:
        problems.append("project.license-files 应为 [\"LICENSE\"]，实际 %r" % (files,))

    # 不锚行首：classifiers 可能是单行数组，也可能逐行写
    if re.search(r'"License ::', text):
        problems.append(
            "classifiers 里仍有 `License ::` 条目 —— setuptools>=77 会以 "
            "InvalidConfigError 硬失败，不只是警告"
        )

    build = doc.get("build-system") or {}
    requires = build.get("requires") or []
    backend = build.get("build-backend") or ""
    setuptools_reqs = [r for r in requires if r.strip().lower().startswith("setuptools")]
    if "setuptools" in backend:
        if not setuptools_reqs:
            problems.append("build-system.requires 未声明 setuptools")
        else:
            for spec in setuptools_reqs:
                m = re.search(r">=\s*(\d+)", spec)
                if not m or int(m.group(1)) < 77:
                    problems.append(
                        "setuptools 下限 %r < 77 —— SPDX 字符串形态要 >=77 才生效" % (spec,)
                    )

    rp = project.get("requires-python") or ""
    m = re.search(r">=\s*(\d+)\.(\d+)", rp)
    if not m:
        problems.append("requires-python 缺失或无法解析：%r" % (rp,))
    elif (int(m.group(1)), int(m.group(2))) < REQUIRED_FLOOR:
        problems.append(
            "requires-python=%r 低于 %d.%d —— 本项目 floor 是 %d.%d（Python 3.9 已于 2025-10 EOL）"
            % (rp, *REQUIRED_FLOOR, *REQUIRED_FLOOR)
        )
    return problems


# ---- 对真实仓文件的断言 ----


def test_repo_pyproject_is_pep639_compliant():
    problems = audit_pyproject(PYPROJECT.read_text(encoding="utf-8"))
    assert problems == [], "许可证元数据不合规：\n  - " + "\n  - ".join(problems)


def test_license_file_exists_on_disk():
    """license-files 指向的文件必须真的在仓库里（否则 wheel 里也是空的）。"""
    assert (REPO_ROOT / "LICENSE").is_file()


# ---- 审计函数自身的负控（证明这个门会红）----

GOOD = '''\
[build-system]
requires = ["setuptools>=77"]
build-backend = "setuptools.build_meta"

[project]
name = "x"
requires-python = ">=3.12"
license = "MIT"
license-files = ["LICENSE"]
'''


def test_auditor_accepts_compliant_input():
    assert audit_pyproject(GOOD) == []


def test_auditor_flags_legacy_license_table():
    bad = GOOD.replace('license = "MIT"\nlicense-files = ["LICENSE"]',
                       'license = { text = "MIT" }')
    problems = audit_pyproject(bad)
    assert any("TOML 表形态" in p for p in problems), problems


def test_auditor_flags_license_classifier():
    bad = GOOD.replace('license-files = ["LICENSE"]',
                       'license-files = ["LICENSE"]\nclassifiers = ["License :: OSI Approved :: MIT License"]')
    problems = audit_pyproject(bad)
    assert any("License ::" in p for p in problems), problems


def test_auditor_flags_setuptools_below_77():
    bad = GOOD.replace("setuptools>=77", "setuptools>=61")
    problems = audit_pyproject(bad)
    assert any("< 77" in p for p in problems), problems


def test_auditor_flags_python_below_floor():
    """低 floor 与 SPDX 是自相矛盾的组合（3.8 装不到 setuptools>=77），必须在 pyproject 层面判红。"""

    bad = GOOD.replace('requires-python = ">=3.12"', 'requires-python = ">=3.8"')
    problems = audit_pyproject(bad)
    assert any("低于 3.12" in p for p in problems), problems


def test_auditor_flags_eol_python_39():
    """3.9 已 EOL（2025-10），即使它能装 setuptools>=77 也不该再被声明为 floor（本迭代的靶子）。"""

    bad = GOOD.replace('requires-python = ">=3.12"', 'requires-python = ">=3.9"')
    problems = audit_pyproject(bad)
    assert any("低于 3.12" in p for p in problems), problems
