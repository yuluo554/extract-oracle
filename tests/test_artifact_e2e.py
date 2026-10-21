"""交付态端到端：对 `dist/extract-oracle.exe` 跑，不只对库函数跑。

**为什么这条必须常驻**：源码态全绿 ≠ 产物态绿。M0 首次打包实测过一次（`__main__.py` 当入口 →
`ImportError`，见 `tests/test_freeze_entry.py`）；M6 定版时又实测到第二格：**产物不带平台语义表**，
在仓库根跑会"假装"通过（`platforms.py::candidate_dirs` 里那条 `Path.cwd()/data/platforms` 兜住了），
换到中立目录立刻退 3。所以本文件把四条交付态命令 + **平台表随包分发**钉成常驻断言。

**产物不在时怎么办**：默认 `skip`，但 skip 是**响的**（打印复现命令，不静默）；
设 `ORACLE_REQUIRE_ARTIFACT=1` 则缺失即**失败**——与 `tests/test_tool_behaviour.py` 的
`ORACLE_REQUIRE_TOOLS=1` 同一条纪律（**不许 skip 成假绿**）。CI 的 `artifact` job 构建产物后
就用 `ORACLE_REQUIRE_ARTIFACT=1` 跑本文件。

**每条命令都在 `tmp_path` 里跑**（中立工作目录）：产物必须自己找得到表与模块，
不能靠"恰好从仓库根启动"。
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from extract_oracle import __version__

REPO = Path(__file__).resolve().parent.parent
FIXTURES = REPO / "data" / "fixtures"

#: 产物按平台两种文件名（`scripts/build.py` 的命名口径）。
ARTIFACT = next(
    (path for path in (REPO / "dist" / "extract-oracle.exe", REPO / "dist" / "extract-oracle") if path.is_file()),
    None,
)

REQUIRE = os.environ.get("ORACLE_REQUIRE_ARTIFACT") == "1"

SKIP_HINT = (
    "交付态产物不存在（先跑 `py -3.12 scripts/build.py`）；"
    "想让它变成失败而不是跳过，设 ORACLE_REQUIRE_ARTIFACT=1"
)


@pytest.fixture(autouse=True)
def _artifact_present() -> None:
    if ARTIFACT is None:
        if REQUIRE:
            pytest.fail(SKIP_HINT)
        pytest.skip(SKIP_HINT)


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[bytes]:
    """在**中立工作目录**里跑产物；`PYTHONUTF8=1` 与仓库其余脚本同口径（CI 也设）。"""

    env = {**os.environ, "PYTHONUTF8": "1"}
    # 显式清掉权威覆盖：产物必须靠**随包分发**的表自证，不能靠外部注入（平台表随包分发那条判据）。
    env.pop("ORACLE_PLATFORM_DIR", None)
    assert ARTIFACT is not None
    return subprocess.run(
        [str(ARTIFACT), *args],
        capture_output=True,
        cwd=str(cwd),
        env=env,
        timeout=120,
    )


def _text(proc: subprocess.CompletedProcess[bytes]) -> str:
    return proc.stdout.decode("utf-8", errors="replace") + proc.stderr.decode("utf-8", errors="replace")


def test_artifact_version_is_the_single_source_of_truth(tmp_path: Path) -> None:
    """版本号第三条断言（前两条见 `tests/test_publish_ready.py` 与 `pyproject`）：产物自报 == 根模块。"""

    proc = _run(["--version"], tmp_path)
    assert proc.returncode == 0, _text(proc)
    assert proc.stdout.decode("utf-8", errors="replace").strip() == f"extract-oracle {__version__}"


def test_artifact_capabilities_reports_five_implemented_modules(tmp_path: Path) -> None:
    proc = _run(["capabilities"], tmp_path)
    assert proc.returncode == 0, _text(proc)
    text = _text(proc)
    for module in ("structure", "encoding", "fold", "accessibility", "container"):
        assert module in text, f"产物自述缺模块 {module}"
    assert text.count("implemented") == 5, f"五个模块应全部 implemented：\n{text}"


def test_artifact_inspect_reports_structure_facts(tmp_path: Path) -> None:
    proc = _run(["inspect", str(FIXTURES / "clean.zip"), "--format", "json"], tmp_path)
    assert proc.returncode == 0, _text(proc)
    payload = json.loads(proc.stdout.decode("utf-8"))
    assert payload["command"] == "inspect"
    assert payload["cd"]["actual_entries"] == 2
    assert len(payload["entries"]) == 2
    # `inspect` 是结构事实面，不产判定（`plan/00` 决策 ⑬）。
    assert payload["findings"] == []


def test_artifact_check_clean_zip_exits_zero_with_empty_judgement_arrays(tmp_path: Path) -> None:
    """五模块齐备时的零误报基线（`data/README.md` §4.1）：退 0 且三数组皆空。"""

    proc = _run(["check", str(FIXTURES / "clean.zip"), "--target", "windows"], tmp_path)
    assert proc.returncode == 0, _text(proc)
    payload = json.loads(proc.stdout.decode("utf-8"))
    assert payload["tool_version"] == __version__
    assert payload["findings"] == []
    assert payload["collisions"] == []
    assert payload["summary"]["accessibility_count"] == 0


def test_artifact_check_case_zip_reports_casefold_survivor(tmp_path: Path) -> None:
    """产物也要给出"最后剩谁"（`plan/01` §2 模块 ③ 的核心区别），不只给"会冲突"。"""

    proc = _run(["check", str(FIXTURES / "case.zip"), "--target", "windows"], tmp_path)
    assert proc.returncode == 1, _text(proc)
    payload = json.loads(proc.stdout.decode("utf-8"))
    codes = [item["code"] for item in payload["collisions"]]
    assert codes == ["collision.CASEFOLD"]
    assert payload["collisions"][0]["survivor"] == "README.TXT"
    # Windows 侧一律 `table_simulated`（`plan/05` §五 U16）：判据是"表 + 目标平台"，不是"本机恰好是 Windows"。
    assert payload["collisions"][0]["evidenceStrength"] == "table_simulated"


def test_artifact_check_reserved_zip_carries_the_three_measured_evidence(tmp_path: Path) -> None:
    """`WRITTEN_UNREADABLE` 的三条实测证据必须从产物里出得来（`data/README.md` §1.3.2 / §4.11）。"""

    proc = _run(["check", str(FIXTURES / "reserved.zip"), "--target", "windows"], tmp_path)
    assert proc.returncode == 1, _text(proc)
    payload = json.loads(proc.stdout.decode("utf-8"))
    levels = {entry["cdName"]: entry["accessibility"]["windows"] for entry in payload["entries"]}
    assert levels["CON.txt"]["level"] == "WRITTEN_UNREADABLE"
    assert levels["CON.txt"]["evidence"] == ["test_path_false", "get_content_error", "open_readable"]
    # `aux.tar.gz` 是 M1 实测的可读对照组（"含扩展名即保留名"不成立）。
    assert levels["aux.tar.gz"]["level"] == "OK"


def test_artifact_carries_the_platform_table(tmp_path: Path) -> None:
    """平台表必须**随包分发**：在中立工作目录里 `platforms --verify` 仍退 0。

    这条是 M6 实测补上的回归靶子——`--add-data` 之前，产物在仓库根跑会因为
    `Path.cwd()/data/platforms` 兜底而**假装**通过，换目录即退 3。
    """

    proc = _run(["platforms", "--verify"], tmp_path)
    assert proc.returncode == 0, (
        "产物在仓库外找不到平台语义表（产物未自带表？）\n" + _text(proc)
    )


def test_artifact_platforms_verify_does_not_leak_host_identity(tmp_path: Path) -> None:
    """表指纹进报告、**卷标识不进**（K15：探测时点与卷标是环境事实，不是判定输入）。"""

    proc = _run(["platforms", "--verify"], tmp_path)
    assert proc.returncode == 0, _text(proc)
    text = _text(proc)
    for banned in ("probed_at_utc", "volume_serial"):
        assert banned not in text or '"' + banned + '": null' in text, f"诊断输出里出现了 {banned}"


def test_artifact_json_is_byte_stable_across_two_runs(tmp_path: Path) -> None:
    """同输入双跑逐字节一致（K03/K09）——产物态的确定性，不只是库函数的。"""

    args = ["check", str(FIXTURES / "case.zip"), "--target", "windows"]
    first = _run(args, tmp_path)
    second = _run(args, tmp_path)
    assert first.returncode == second.returncode == 1
    assert first.stdout == second.stdout, "同输入双跑的产物 stdout 不一致（含时间戳/随机 ID/路径？）"
    assert b"\r\n" not in first.stdout, "JSON 导出必须用 LF（`data/README.md` §4.8）"
    assert first.stdout.endswith(b"\n")


def test_artifact_output_has_no_host_absolute_path(tmp_path: Path) -> None:
    """报告里不得出现本机绝对路径（隐私红线 + 跨机可比，`data/README.md` §4.8）。"""

    proc = _run(["check", str(FIXTURES / "reserved.zip"), "--target", "windows"], tmp_path)
    text = _text(proc)
    assert "/home/" not in text and "/Users/" not in text
    assert str(FIXTURES) not in text, "报告里出现了 fixture 的本机绝对路径"
    assert str(REPO) not in text, "报告里出现了仓库的本机绝对路径"
