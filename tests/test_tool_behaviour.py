"""三工具行为断言（`plan/03` §MOD-1 验收末条）：**只锁分歧方向，不锁 stderr 文案**。

R4（`plan/05` §七）：工具版本会漂，把 stderr 的具体措辞写进断言 = 让 CI 随上游改词变红。
所以这里只断言**"谁写了哪个名字 / 谁拒绝了"**——这正是本工具要预言的东西。

两条纪律：

1. **工具缺失即 skip，不是 pass**——但 CI 上 skip 等于假绿。所以 CI 设 `ORACLE_REQUIRE_TOOLS=1`，
   缺失时本文件**失败**并点名工具；本地开发不设该变量，缺失只跳过。
   **绝不**降级成"没分歧"（`data/README.md` §4.1 的"不静默退化"同一条精神）。
2. **临时目录里解压，用完即清**（`tmp_path`）：本项目的"零解压到磁盘"指**交付态运行时不落盘**，
   测试要验工具行为必须让它真的写——产物只在 `tmp_path`，由 pytest 清理。

三工具 = Python `zipfile` / Info-ZIP `unzip` / 7-Zip。libarchive 的结论由
`data/tool-matrix/` 的盘上记录覆盖（`tests/test_m2_ci_assertions.py` 锁矩阵结论）。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

import probe_tools  # noqa: E402

FIXTURES = REPO / "data" / "fixtures"

#: CI 里置 1：工具缺失 = 失败（skip 会变成假绿）。
REQUIRE_TOOLS = os.environ.get("ORACLE_REQUIRE_TOOLS") == "1"


def _require(tool: str, env_name: str) -> str:
    """定位工具。缺失时：CI 失败 / 本地跳过——**两种都不能静默变成"没分歧"**。"""

    located = probe_tools.locate(tool)
    if located:
        return located
    message = f"{tool} 不在本机（可用 {env_name} 指定路径；CI 上由 runner 的包管理器提供）"
    if REQUIRE_TOOLS:
        pytest.fail(message)
    pytest.skip(message)


def _unzip() -> str:
    return _require("info-zip-unzip", "PROBE_UNZIP")


def _seven_zip() -> str:
    return _require("7zip", "PROBE_7Z")


def _extract_with(argv: list[str], target: Path) -> tuple[int, str]:
    target.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        argv, capture_output=True, text=True, errors="replace", timeout=120, cwd=str(target)
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _written(target: Path) -> list[str]:
    return sorted(
        str(path.relative_to(target)).replace("\\", "/") for path in target.rglob("*") if path.is_file()
    )


# ---------------------------------------------------------------- mismatch_name.zip


def test_mismatch_name_python_reads_cd_name():
    """Python `zipfile` 取 **CD** 名（`evil.txt`）——但它在 `read()` 时才拒绝。

    M1 的对照矩阵记的是 `-m zipfile -e` 的拒绝；判定口径要的是"取哪个头"，
    所以这里分两步断言：`namelist()` 给 CD 名、`read()` 抛 `BadZipFile`。
    """

    with zipfile.ZipFile(FIXTURES / "mismatch_name.zip") as archive:
        assert archive.namelist() == ["evil.txt"]
        with pytest.raises(zipfile.BadZipFile):
            archive.read("evil.txt")


def test_mismatch_name_unzip_writes_cd_name(tmp_path):
    tool = _unzip()
    out = tmp_path / "unzip-out"
    _extract_with([tool, "-o", str(FIXTURES / "mismatch_name.zip"), "-d", str(out)], out)
    assert _written(out) == ["evil.txt"]


def test_mismatch_name_7zip_writes_lfh_name(tmp_path):
    tool = _seven_zip()
    out = tmp_path / "7z-out"
    _extract_with([tool, "x", "-y", f"-o{out}", str(FIXTURES / "mismatch_name.zip")], out)
    assert _written(out) == ["allowed.txt"]


# ---------------------------------------------------------------- overlap.zip


def test_overlap_python_refusal_depends_on_patch_version_and_unzip_never_degrades(tmp_path):
    """`overlap.zip`：**分歧方向**仍是这条断言的全部内容，但两处"随环境而变"必须写实。

    实测依据（M6 首推首跑与后续两轮的真日志）：

    * **Python 的重叠检测随"补丁版本"出现，不是某个 minor 版本的分界**：本机 **3.8.8 照读**
      （`read('a.txt')` 返回 45 字节），本机 3.12.10 与 CI 的 **3.9.25 都抛**
      `BadZipFile: Overlapped entries: 'a.txt' (possible zip bomb)` —— 即这条加固被**backport 到了
      3.9 的安全分支**。所以**不按 `sys.version_info` 分派**（首版就是这么写的，被 3.9.25 打红）：
      改为断言**与版本无关的那一半**——`ZipFile()` 与 `namelist()` **一律成功**（它不是"拒绝打开"），
      而 `read()` 的结局**允许两种**（照读 / 抛 `BadZipFile`）。
    * **`unzip` 的退出码随发行版补丁而变**：本机 Cygwin 6.00 → `rc=0` 且落出两个名字；
      Ubuntu 的 6.00（带重叠/炸弹检查补丁）→ `rc=12`。R4（`plan/05` §七）说得很清楚：
      **只锁分歧方向，不锁具体退出码**。所以这里锁"**要么照解、要么明确报错，绝不静默给出一份
      错的落盘**"，并把实测值带进断言消息。
    """

    with zipfile.ZipFile(FIXTURES / "overlap.zip") as archive:
        # 与版本无关的不变量：结构层两条都在（"分歧"不在"能不能打开"这一维）。
        assert archive.namelist() == ["a.txt", "b.txt"]
        try:
            payload = archive.read("a.txt")
        except zipfile.BadZipFile as exc:
            # 新补丁版本（3.9.25 / 3.12.x）走到这里；**只允许**是重叠检测那一类拒绝。
            assert "overlap" in str(exc).lower(), f"拒绝原因不是重叠检测: {exc}"
        else:
            # 旧版本（本机 3.8.8）走到这里：照读，且读到的是内嵌的 b.txt 头（重叠的物理证据）。
            assert payload[:4] == b"PK\x03\x04"

    tool = _unzip()
    out = tmp_path / "unzip-overlap"
    code, text = _extract_with([tool, "-o", str(FIXTURES / "overlap.zip"), "-d", str(out)], out)
    written = _written(out)
    assert written == ["a.txt", "b.txt"] or code != 0, (
        "unzip 对 overlap.zip 的处置无法归类（既没落出两个名字，也没报非零退出码）："
        f"rc={code} written={written} text={text[:300]!r}"
    )


# ---------------------------------------------------------------- crc_diverge.zip


def test_crc_diverge_python_refuses_but_7zip_writes(tmp_path):
    """CRC 双头不一致：Python 读时校验拒绝；7-Zip 写出文件（rc=2 但产物在）。"""

    with zipfile.ZipFile(FIXTURES / "crc_diverge.zip") as archive:
        with pytest.raises(zipfile.BadZipFile):
            archive.read("crc.txt")

    tool = _seven_zip()
    out = tmp_path / "7z-crc"
    _extract_with([tool, "x", "-y", f"-o{out}", str(FIXTURES / "crc_diverge.zip")], out)
    assert _written(out) == ["crc.txt"]


# ---------------------------------------------------------------- wrong_count.zip


def test_wrong_count_python_ignores_declared_count(tmp_path):
    """EOCD 声明 5 条、实际 2 条：Python 按 CD 实际条目走，照样解出两个。"""

    with zipfile.ZipFile(FIXTURES / "wrong_count.zip") as archive:
        assert archive.namelist() == ["alpha.txt", "beta.txt"]
        out = tmp_path / "py-wrong"
        archive.extractall(out)
    assert _written(out) == ["alpha.txt", "beta.txt"]


# ---------------------------------------------------------------- 不锁文案


def test_assertions_do_not_depend_on_stderr_wording(tmp_path):
    """R4 的自证：本文件里不得出现对具体 stderr 文案的 `in` 断言。

    判据落在**断言行**上（不含文档字符串——本函数的说明里就举了反例）。
    改本文件时若加了 `assert "mismatching local filename" in text`，这里会红。
    """

    source = Path(__file__).read_text(encoding="utf-8")
    banned = ("mismatching", "Errors:", "continuing with", "Inconsistent")
    assert_lines = [
        line.strip() for line in source.splitlines() if line.strip().startswith("assert ")
    ]
    assert assert_lines, "没抽到任何断言行——抽取面坏了（本判据会空跑）"
    for line in assert_lines:
        for phrase in banned:
            assert phrase not in line, f"断言锁了 stderr 文案（R4）: {line}"


def test_unzip_is_really_info_zip():
    """工具定位的假门对策：`unzip` 必须是 Info-ZIP，不是别的同名程序。"""

    tool = _unzip()
    code, text = _extract_with([tool, "-v"], Path(tool).parent)
    assert code in (0, 1)  # Info-ZIP 的 `-v` 无参数时 rc 随构建而变，内容才判据
    assert "Info-ZIP" in text
    assert shutil.which(tool) or Path(tool).exists()
