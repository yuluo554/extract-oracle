"""fixture 与真值的对账（K01/K05/K06）。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import gen_fixtures  # noqa: E402

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "data" / "fixtures"
TRUTH_DIR = FIXTURE_DIR / "truth"

#: fixture 产物的扩展名（`.epub` 自 M1 起由生成器产出，仍是 ZIP 容器）。
FIXTURE_SUFFIXES = {".zip", ".epub"}

#: 真值文件只允许这些键（出现 `observed_*` 即红——真值禁观测，K01）。
#:
#: 扩键**必须先改这里**：M1 加了 `expected_encoding`（编码推断的期望）与
#: `expected_names`（四工具落盘名的期望）——两者都是"输入 + 期望"，不承载观测值。
ALLOWED_TRUTH_KEYS = {
    "fixture",
    "expected_findings",
    "expected_collisions",
    "expected_accessibility",
    "expected_encoding",
    "expected_names",
    "note",
}


def _truth_files() -> list[Path]:
    return sorted(TRUTH_DIR.glob("*.json"))


def _fixture_files() -> list[Path]:
    return sorted(p for p in FIXTURE_DIR.iterdir() if p.is_file() and p.suffix in FIXTURE_SUFFIXES)


def test_generator_roundtrip_is_byte_identical():
    """两层里的第二层：重跑生成器 → 与盘上产物逐字节比对。

    只断言盘上产物的守门在生成器被改坏时照常绿（实测过的假门形态）。
    """

    assert gen_fixtures.check(FIXTURE_DIR) == 0


def test_every_fixture_has_truth_and_vice_versa():
    on_disk = {p.name for p in _fixture_files()}
    for name in gen_fixtures.BUILDERS:
        assert name in on_disk, f"缺 fixture: {name}"
    orphans = sorted(p.name for p in _truth_files() if p.stem not in gen_fixtures.BUILDERS)
    assert orphans == [], f"孤儿真值: {orphans}"


def test_no_orphan_fixture_files():
    """反向：盘上不得有生成器不认领的产物（手放进去的样本不算数）。"""

    orphans = sorted(p.name for p in _fixture_files() if p.name not in gen_fixtures.BUILDERS)
    assert orphans == [], f"孤儿产物: {orphans}"


def test_truth_holds_input_and_expectation_only():
    """K01：真值库不得出现 `observed_*` 一类字段，且键集合受白名单约束。"""

    for path in _truth_files():
        data = json.loads(path.read_text(encoding="utf-8"))
        bad = sorted(k for k in data if k not in ALLOWED_TRUTH_KEYS)
        assert bad == [], f"{path.name} 含非白名单键: {bad}"


def test_expectation_keys_are_explicit():
    """'空' 与 '没写' 是两件事：期望键必须存在（哪怕是 `[]`）。"""

    for path in _truth_files():
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "expected_findings" in data, f"{path.name} 缺 expected_findings（空也要写）"
        for platform, expected in data.get("expected_collisions", {}).items():
            assert isinstance(expected, list), f"{path.name} {platform} 期望必须是列表"


def test_pending_fixtures_are_not_silently_shipped():
    """生成器登记的待落地样本不得出现在目录里（否则是'手放进去的'）。

    M1 收尾后 `PENDING == []`，本测试变成"反向空跑自证"：
    若有人把 PENDING 加回来却已把文件放进仓里，这里仍然会红。
    """

    on_disk = {p.name for p in _fixture_files()}
    leaked = sorted(name for name in gen_fixtures.PENDING if name in on_disk)
    assert leaked == [], f"待落地的样本提前入仓: {leaked}"


def test_clean_fixture_is_zero_finding_baseline():
    """零误报基线：`clean.zip` 的期望必须是空（M2 起由判定层实跑接管）。"""

    truth = json.loads((TRUTH_DIR / "clean.zip.json").read_text(encoding="utf-8"))
    assert truth["expected_findings"] == []


def test_dos_timestamp_is_frozen_constant():
    """K05：DOS 时间字段冻结，否则同命令两次生成字节会漂。"""

    data = gen_fixtures.fixture_clean()
    # LFH 的 time/date 位于签名 + 4(version) + 2(flags) + 2(method) 之后
    assert data[10:14].hex() == "00002100"