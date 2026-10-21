"""M1 数据产物的常驻断言：平台表、四工具矩阵、生成器补全。

三条纪律各自的落地：
- **K04**：`meta.json.source` 只能是 `volume_read` / `host_probe`，表 sha256 必须与本体逐字节对上；
- **零解压到磁盘**：`probe_tools` 的临时目录必须用完即清（这里断言矩阵里不含本机绝对路径）；
- **确定性**：矩阵与平台表重跑一致；`probed_at_utc` 不进判定输入。
"""

from __future__ import annotations

import hashlib
import json
import struct
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

import fetch_upcase  # noqa: E402
import gen_fixtures  # noqa: E402
import probe_tools  # noqa: E402

PLATFORM_DIR = REPO / "data" / "platforms"
MATRIX_DIR = REPO / "data" / "tool-matrix"
FIXTURE_DIR = REPO / "data" / "fixtures"


# ------------------------------------------------------------------ 平台表（K04）


def test_upcase_table_and_meta_are_paired():
    assert (PLATFORM_DIR / "ntfs-upcase.bin").exists(), "缺 data/platforms/ntfs-upcase.bin"
    assert (PLATFORM_DIR / "meta.json").exists(), "缺 data/platforms/meta.json"


def test_upcase_meta_source_is_enum_only():
    """K04：`casefold` 不是合法取值（决策记录 ③）。"""

    meta = json.loads((PLATFORM_DIR / "meta.json").read_text(encoding="utf-8"))
    source = meta["ntfs_upcase"]["source"]
    assert source in fetch_upcase.VALID_SOURCES, f"非法 source: {source!r}"


def test_upcase_sha256_matches_table_bytes():
    """`plan/02` §四 第 2 条：对不上 = 表被换过，`platforms --verify` 必须报 3。"""

    table = (PLATFORM_DIR / "ntfs-upcase.bin").read_bytes()
    meta = json.loads((PLATFORM_DIR / "meta.json").read_text(encoding="utf-8"))
    assert hashlib.sha256(table).hexdigest() == meta["ntfs_upcase"]["sha256"]


def test_upcase_table_shape_is_fixed():
    """65536 项 × uint16 小端 = 131072 字节；长度不对 = 表结构变了。"""

    table = (PLATFORM_DIR / "ntfs-upcase.bin").read_bytes()
    assert len(table) == fetch_upcase.TABLE_CODEPOINTS * 2
    assert meta_entries() == fetch_upcase.TABLE_CODEPOINTS


def meta_entries() -> int:
    meta = json.loads((PLATFORM_DIR / "meta.json").read_text(encoding="utf-8"))
    return meta["ntfs_upcase"]["entries"]


def test_upcase_meta_records_volume_and_host():
    """HANDOFF-M1 §6：`meta.json` 必须带卷标识、探测环境、sha256。"""

    meta = json.loads((PLATFORM_DIR / "meta.json").read_text(encoding="utf-8"))
    block = meta["ntfs_upcase"]
    for key in ("source", "volume", "probed_at_utc", "probe_host", "entries", "sha256", "generator_version"):
        assert key in block, f"meta.json 缺 {key}"
    assert block["volume"].get("serial_hex"), "卷标识缺失"
    assert block["probe_host"].get("os_build"), "探测环境缺失"


def test_upcase_verification_pairs_agree_with_measured_fs():
    """表预测必须与真实卷实测一致——这是 `host_probe` 通道的存在意义。"""

    meta = json.loads((PLATFORM_DIR / "meta.json").read_text(encoding="utf-8"))
    verification = meta["ntfs_upcase"]["verification"]
    assert verification["method"] == "write_collision_on_real_volume"
    assert verification["pairs_checked"] == len(fetch_upcase.PROBE_PAIRS)
    assert verification["pairs_agree"] == verification["pairs_checked"]
    for record in verification["pairs"]:
        assert record["table_says_collide"] == record["fs_says_collide"], record


def test_upcase_table_fold_is_not_casefold():
    """核心断言：真表折叠 ≠ `str.casefold()`（否则整张表没有存在意义）。"""

    table = (PLATFORM_DIR / "ntfs-upcase.bin").read_bytes()

    def table_fold(text: str) -> str:
        return fetch_upcase.table_fold(table, text)

    # ǅ(U+01C5) 的 casefold 是 ǆ(U+01C6)，而真表折叠保持 ǅ → 两者至少在一处不同
    divergent = [
        ch for ch in "\u01c5\u0131\u017f\u00df\u0130"
        if table_fold(ch) != ch.casefold()
    ]
    assert divergent, "真表折叠与 casefold 完全一致，说明表取错了（可能是用近似法生成的）"


def test_upcase_table_does_case_fold_ascii():
    table = (PLATFORM_DIR / "ntfs-upcase.bin").read_bytes()
    assert fetch_upcase.table_fold(table, "abcXYZ") == "ABCXYZ"


# ------------------------------------------------------------------ 四工具矩阵


def test_matrix_covers_every_fixture():
    if not MATRIX_DIR.exists():
        pytest.skip("矩阵未生成（跑 py -3.12 tools/probe_tools.py）")
    fixtures = set(gen_fixtures.BUILDERS)
    recorded = {p.stem for p in MATRIX_DIR.glob("*.json") if not p.name.startswith("_")}
    assert fixtures - recorded == set(), f"矩阵缺样本: {sorted(fixtures - recorded)}"


def test_matrix_every_cell_has_command_and_excerpt():
    """`plan/05` §一 M1 DoD：「对照表每格有命令与输出」——没有命令的格不算实测。"""

    if not MATRIX_DIR.exists():
        pytest.skip("矩阵未生成")
    problems = []
    for path in sorted(MATRIX_DIR.glob("*.json")):
        if path.name.startswith("_"):
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        for tool, cell in record["cells"].items():
            if cell["status"] == "tool_unavailable":
                continue
            if not cell.get("command"):
                problems.append(f"{path.name}:{tool} 缺 command")
            if cell["status"] != "tool_unavailable" and not cell.get("written") and not cell.get("output_excerpt") and cell.get("error") is None:
                problems.append(f"{path.name}:{tool} 缺 written/output_excerpt/error")
    assert problems == [], problems


def test_matrix_has_no_absolute_paths():
    """`data/README.md` §4.8：不输出本机绝对路径（否则跨机不可比、且泄隐私）。"""

    if not MATRIX_DIR.exists():
        pytest.skip("矩阵未生成")
    offenders = []
    for path in sorted(MATRIX_DIR.glob("*.json")):
        text = path.read_text(encoding="utf-8")
        if "AppData" in text or "\\\\Users\\\\" in text or "/Users/" in text:
            offenders.append(path.name)
    assert offenders == [], f"矩阵里出现本机路径: {offenders}"


def test_matrix_clean_zip_is_agreement_baseline():
    """零误报基线：`clean.zip` 四工具必须落出同一组名字。"""

    path = MATRIX_DIR / "clean.zip.json"
    if not path.exists():
        pytest.skip("矩阵未生成")
    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["agreement"]["tools_agree"], record["agreement"]
    assert record["agreement"]["unavailable"] == []


def test_matrix_divergence_is_actually_detected():
    """反向断言：至少要有一份样本四工具落盘不同，否则矩阵测不出分歧（门形同虚设）。"""

    if not MATRIX_DIR.exists():
        pytest.skip("矩阵未生成")
    rows = []
    for path in sorted(MATRIX_DIR.glob("*.json")):
        if path.name.startswith("_"):
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        if not record["agreement"]["tools_agree"]:
            rows.append(path.stem)
    assert rows, "一份分歧样本都没有——四工具对照没有测到东西"


def test_matrix_mismatch_name_reproduces_documented_split():
    """`data/README.md` §1.3.1 的核心断言：Python 拒绝、unzip 写 CD 名、7-Zip 写 LFH 名。"""

    path = MATRIX_DIR / "mismatch_name.zip.json"
    if not path.exists():
        pytest.skip("矩阵未生成")
    record = json.loads(path.read_text(encoding="utf-8"))
    cells = record["cells"]
    assert cells["python-zipfile"]["status"] == "refused", "Python 应拒绝双头不一致"
    assert cells["info-zip-unzip"]["written"] == ["evil.txt"], "unzip 应取 CD 名"
    assert "allowed.txt" in cells["7zip"]["written"], "7-Zip 应取 LFH 名"


def test_probe_tool_locate_does_not_accept_gnu_tar():
    """`libarchive` 格子必须是真 bsdtar；GNU tar 会被静默当成同一个工具。"""

    located = probe_tools.locate("libarchive")
    if located is None:
        pytest.skip("本机没有 libarchive/bsdtar")
    assert probe_tools._is_bsdtar(located), f"{located} 不是 bsdtar"


# ------------------------------------------------------------------ 生成器补全


def test_generator_pending_is_empty():
    """HANDOFF-M1 §6 第一项：`PENDING` 清零。"""

    assert gen_fixtures.PENDING == []


def test_generator_covers_all_22_documented_fixtures():
    """`data/README.md` §3.2 表逐行对应的 22 份样本必须全部由生成器产出。"""

    documented = {
        "mismatch_name.zip", "alias_lfh.zip", "overlap.zip", "wrong_count.zip",
        "crc_diverge.zip", "size_diverge.zip", "zh_gbk.zip", "upath.zip",
        "upath_badcrc.zip", "case.zip", "norm.zip", "trim.zip", "filedir.zip",
        "reserved.zip", "trailing.zip", "not_first.epub", "compressed.epub",
        "extra.epub", "padding.epub", "long_path.zip", "long_comp.zip", "clean.zip",
    }
    assert documented == set(gen_fixtures.BUILDERS)
    assert len(gen_fixtures.BUILDERS) == 22


def test_every_fixture_has_a_nonempty_truth():
    """每个判定项至少一个 fixture + 一份真值：真值文件不得是空对象。"""

    for name in gen_fixtures.BUILDERS:
        truth = json.loads((FIXTURE_DIR / "truth" / f"{name}.json").read_text(encoding="utf-8"))
        assert truth.get("expected_findings") is not None, f"{name} 缺 expected_findings"


def test_new_fixtures_are_appended_after_m0_ones():
    """K06：M0 的 6 份必须仍在前 6 位（既有确定性序列不被插队）。"""

    order = list(gen_fixtures.BUILDERS)
    assert order[:6] == [
        "clean.zip", "mismatch_name.zip", "case.zip", "norm.zip", "reserved.zip", "trailing.zip",
    ]


@pytest.mark.parametrize(
    "name,needle",
    [
        ("alias_lfh.zip", ("FLAG_DIVERGES",)),
        ("overlap.zip", ("LFH_OVERLAP",)),
        ("wrong_count.zip", ("CD_COUNT_MISMATCH",)),
        ("crc_diverge.zip", ("CRC_DIVERGES",)),
        ("size_diverge.zip", ("SIZE_DIVERGES",)),
        ("upath_badcrc.zip", ("UPATH_CRC_MISMATCH",)),
        ("not_first.epub", ("MIMETYPE_NOT_FIRST",)),
        ("compressed.epub", ("MIMETYPE_COMPRESSED",)),
        ("extra.epub", ("MIMETYPE_EXTRA",)),
        ("padding.epub", ("MIMETYPE_PADDING",)),
        ("long_path.zip", ("PATH_OVER_260",)),
        ("long_comp.zip", ("COMPONENT_OVER_255",)),
    ],
)
def test_fixture_covers_its_documented_rule(name: str, needle: tuple[str, ...]):
    """`plan/00` §七 对照表逐行核：每个 ruleId 至少一个 fixture 认领。"""

    truth = json.loads((FIXTURE_DIR / "truth" / f"{name}.json").read_text(encoding="utf-8"))
    haystack = " ".join(truth["expected_findings"])
    assert any(token in haystack for token in needle), f"{name} 没认领 {needle}"


def test_long_path_length_is_measured_not_guessed():
    """`long_path.zip` 的整路径必须真的 > 260；`long_comp.zip` 的组件必须真的 > 255。"""

    long_path = [n for n in _names_of("long_path.zip")]
    assert len(long_path[0]) > 260
    long_comp = [n for n in _names_of("long_comp.zip")]
    assert len(long_comp[0].split("/")[0]) == 256


def _names_of(fixture: str) -> list[str]:
    data = (FIXTURE_DIR / fixture).read_bytes()
    # EOCD 在尾部；用生成器的布局反推 CD 起始
    eocd = data.rindex(b"PK\x05\x06")
    _, _, _, total, _, cd_size, cd_offset, _ = struct.unpack_from("<IHHHHIIH", data, eocd)
    names = []
    pos = cd_offset
    for _ in range(total):
        name_len, extra_len, comment_len = struct.unpack_from("<HHH", data, pos + 28)
        names.append(data[pos + 46 : pos + 46 + name_len].decode("utf-8", "replace"))
        pos += 46 + name_len + extra_len + comment_len
    return names


def test_compressed_epub_crc_is_over_uncompressed_content():
    """deflate 条目的 CRC32 必须是**解压后**内容的校验（否则解压器全报 bad CRC）。"""

    import zipfile

    with zipfile.ZipFile(FIXTURE_DIR / "compressed.epub") as archive:
        info = archive.getinfo("mimetype")
        assert info.compress_type == zipfile.ZIP_DEFLATED
        assert archive.read("mimetype") == b"application/epub+zip"  # 读不出来会抛 BadZipFile


# ── docs/divergence.md 的"22×4 = 88 格"是承诺，必须有机器判据 ─────────────────────


def test_divergence_doc_covers_every_fixture_with_four_tool_cells():
    """`docs/divergence.md` 声称"88 格逐格命令 + 输出节选"——**这句话本身要被机器核。**

    为什么必须核：`plan/01` §3 第 4 条把"分歧对照每格附实测命令与输出节选"写成提交材料，
    而 `plan/06` §二 把 `docs/divergence.md` 列为招牌动词的兑现物。只靠人读，**漏一份 fixture
    或漏一格工具都不会变红**——那正是"文档承诺"与"机器判据"脱节的经典形态。
    判据只数**表格行**（形如 "竖线 + 反引号工具名 + 竖线 + 反引号命令"），不读散文。
    """

    import re

    doc = REPO / "docs" / "divergence.md"
    assert doc.is_file(), "缺 docs/divergence.md"
    text = doc.read_text(encoding="utf-8")
    tools = ("python-zipfile", "info-zip-unzip", "7zip", "libarchive")
    cell_re = re.compile(r"^\| `(%s)` \| `" % "|".join(tools))

    blocks: dict[str, int] = {}
    order: list[str] = []
    current: str | None = None
    for line in text.splitlines():
        heading = re.match(r"^#{3,4} (?:\d+\.\d+ )?`([^`]+\.(?:zip|epub))`", line)
        if heading:
            current = heading.group(1)
            blocks[current] = 0
            order.append(current)
            continue
        if line.startswith("## "):
            current = None
        if current and cell_re.match(line):
            blocks[current] += 1

    fixtures = sorted(p.name for p in FIXTURE_DIR.iterdir() if p.suffix in {".zip", ".epub"})
    assert len(order) == len(set(order)), f"同一 fixture 出现多个小节: {order}"
    assert sorted(order) == fixtures, (
        "divergence.md 的小节与 data/fixtures 不一一对应："
        f"缺 {sorted(set(fixtures) - set(order))} / 多 {sorted(set(order) - set(fixtures))}"
    )
    incomplete = {name: count for name, count in blocks.items() if count != len(tools)}
    assert incomplete == {}, f"这些 fixture 的逐格表不是 4 行: {incomplete}"
    assert sum(blocks.values()) == len(fixtures) * len(tools) == 88, sum(blocks.values())


def test_divergence_doc_records_the_two_measured_narrowings():
    """M5 的两处实测收窄必须在定稿里**写明**（旧表述"7z 多编码猜测"不得照抄）。"""

    text = (REPO / "docs" / "divergence.md").read_text(encoding="utf-8")
    assert "不做字符集探测" in text, "缺'7z/libarchive 不做字符集探测'这条收窄"
    assert "与 bit 11 无关" in text, "缺'unzip 落盘名与 bit 11 无关'这条收窄"
    # 反向：旧说法"7z → 多编码猜测"**只允许**作为"初版表述"出现在对照表的左列
    # （改正表要引用旧措辞才读得懂），不得作为结论出现。
    for line in text.splitlines():
        if "多编码猜测" in line:
            assert "初版表述" in line or "| \"`7z` → 多编码猜测\" |" in line, (
                f"旧表述'多编码猜测'出现在非对照位置: {line[:120]}"
            )
