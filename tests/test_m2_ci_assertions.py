"""把 `data/tool-matrix/` 的结论固化成断言（`plan/HANDOFF-M2.md` §3 第 5 条）。

为什么要有这一层：`tests/test_tool_behaviour.py` 在本机真跑工具（依赖 `unzip`/`7z` 是否装了）；
本文件断言的是**盘上矩阵记录**的结论，任何 runner 都能跑。两者互补：

- 真跑层回答"本机现在还是这样吗"；
- 矩阵层回答"我们**宣称**的分歧方向与入仓证据一致吗"。

纪律（R4，`plan/05` §七）：**只锁分歧方向**（谁写哪个名字 / 谁拒绝），不锁 stderr 文案。
纪律（K01）：矩阵里不得出现本机绝对路径（`probe_tools._sanitize` 已清洗，这里反向钉住）。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
MATRIX = REPO / "data" / "tool-matrix"

#: 本文件断言的四个结构样本 → 期望的**落盘名集合**与**拒绝者**。
#: 这是 `plan/03` §MOD-1 验收表的机器可读形式，也是"预言是否属实"的自证。
EXPECTED: dict[str, dict] = {
    "mismatch_name.zip": {
        "written": {
            "python-zipfile": [],
            "info-zip-unzip": ["evil.txt"],
            "7zip": ["allowed.txt"],
            "libarchive": ["allowed.txt"],
        },
        "refused": ["python-zipfile"],
        "distinct_written_sets": 3,
    },
    "overlap.zip": {
        "written": {
            "python-zipfile": [],
            "info-zip-unzip": ["a.txt", "b.txt"],
            "7zip": ["a.txt", "b.txt"],
            "libarchive": ["a.txt", "b.txt"],
        },
        "refused": ["python-zipfile"],
        "distinct_written_sets": 2,
    },
    "crc_diverge.zip": {
        # 四个工具都**写出了** `crc.txt`（Python 先落盘再校验 CRC，然后抛异常）——
        # 所以这里的 `refused` 指的是"工具报错"，不是"没产物"。
        "written": {
            "python-zipfile": ["crc.txt"],
            "info-zip-unzip": ["crc.txt"],
            "7zip": ["crc.txt"],
            "libarchive": ["crc.txt"],
        },
        "refused": ["python-zipfile"],
        "distinct_written_sets": 1,
    },
    "wrong_count.zip": {
        "written": {
            "python-zipfile": ["alpha.txt", "beta.txt"],
            "info-zip-unzip": ["alpha.txt", "beta.txt"],
            "7zip": ["alpha.txt", "beta.txt"],
            "libarchive": ["alpha.txt", "beta.txt"],
        },
        "refused": [],
        "distinct_written_sets": 1,
    },
}


def _record(name: str) -> dict:
    path = MATRIX / f"{name}.json"
    assert path.exists(), f"缺矩阵记录: {path.name}（跑 tools/probe_tools.py 重生成）"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("fixture", sorted(EXPECTED))
def test_matrix_written_names_match_claim(fixture: str):
    """`mismatch_name` 上 unzip 取 CD、7-Zip 与 libarchive 取 LFH —— 这是全项目的核心分歧。"""

    record = _record(fixture)
    actual = {tool: record["cells"][tool]["written"] for tool in record["cells"]}
    assert actual == EXPECTED[fixture]["written"], f"{fixture} 落盘名与宣称不符"


@pytest.mark.parametrize("fixture", sorted(EXPECTED))
def test_matrix_refused_tools_match_claim(fixture: str):
    record = _record(fixture)
    assert record["agreement"]["refused"] == EXPECTED[fixture]["refused"]
    assert record["agreement"]["distinct_written_sets"] == EXPECTED[fixture]["distinct_written_sets"]


def test_overlap_is_refused_by_python_only():
    """`overlap.zip` 的分歧方向：**一个拒绝、三个照解**（不是"四个都报错"）。"""

    record = _record("overlap.zip")
    assert record["cells"]["python-zipfile"]["status"] == "refused"
    for tool in ("info-zip-unzip", "7zip", "libarchive"):
        assert record["cells"][tool]["exit_code"] == 0, tool


def test_crc_and_size_diverge_show_up_as_nonzero_exit_codes():
    """CRC/SIZE 双头不一致：文件都写出来了，分歧落在退出码上（7-Zip=2 / libarchive=1）。

    Python 的差异只出现在 **CRC** 那一份（`extractall` 边写边校验，抛 `BadZipFile`）；
    `size_diverge` 它照收（rc=0）——这条区别本身也是"分歧方向"的一部分。
    """

    crc = _record("crc_diverge.zip")
    assert crc["cells"]["7zip"]["exit_code"] == 2
    assert crc["cells"]["libarchive"]["exit_code"] == 1
    assert crc["cells"]["info-zip-unzip"]["exit_code"] == 0
    assert crc["cells"]["python-zipfile"]["status"] == "refused"

    size = _record("size_diverge.zip")
    assert size["cells"]["7zip"]["exit_code"] == 2
    assert size["cells"]["libarchive"]["exit_code"] == 1
    assert size["cells"]["info-zip-unzip"]["exit_code"] == 0
    assert size["cells"]["python-zipfile"]["status"] == "ok"


def test_alias_lfh_is_accepted_by_all_four():
    """flag 双头不一致是**最温和**的一种：四个工具都写出同名文件，只有 unzip 的 rc=1。"""

    record = _record("alias_lfh.zip")
    assert record["agreement"]["tools_agree"] is True
    assert record["cells"]["info-zip-unzip"]["exit_code"] == 1
    assert record["cells"]["7zip"]["exit_code"] == 0
    assert record["cells"]["libarchive"]["exit_code"] == 0


def test_matrix_has_no_host_absolute_paths():
    """K03/K09：矩阵是入仓产物，不得带本机绝对路径（`_sanitize` 的回归钉）。"""

    import re

    offenders = []
    for path in sorted(MATRIX.glob("*.json")):
        text = path.read_text(encoding="utf-8")
        if re.search(r"\b[A-Za-z]:[\\/]", text) or "/home/" in text or "/Users/" in text:
            offenders.append(path.name)
    assert offenders == []


def test_summary_lists_every_fixture():
    """`_summary.json` 是矩阵的目录：少一份 = 有人删了记录却没重跑脚本。"""

    summary = json.loads((MATRIX / "_summary.json").read_text(encoding="utf-8"))
    recorded = sorted(path.stem for path in MATRIX.glob("*.json") if path.name != "_summary.json")
    assert summary["fixtures"] == recorded
    assert len(summary["rows"]) == len(recorded)
