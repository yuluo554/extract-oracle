"""M3 验收：MOD-3 跨平台落盘折叠 + 平台表接入（K08 的靶子）。

覆盖 `plan/HANDOFF-M3.md` §3 / §6 的六条待办：

1. 平台表接入：`sha256` 对账、`source` 枚举、`probed_at_utc` 不进 digest；
2. `platforms --verify` 给出真指纹（不再是无条件退 3 的占位）；
3. MOD-3 四条规则、判定顺序 FILEDIR → CASEFOLD → NFC → TRIM；
4. `windows` 折叠走真实 `$UpCase` 表（AST 守门另在 `test_rule_boundaries.py`）；
5. `case.zip` / `norm.zip` / `trim.zip` / `filedir.zip` 的分平台结论 + 写序→存活者；
6. 8 组字符对回归：**真表结果 = 卷实测** 且 **casefold 近似结果 ≠ 真表结果**。

口径一律引用 `data/README.md` §4.3 / §4.7 / §4.9，本文不写第二份数值表述。
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import os

import pytest

from extract_oracle import platforms as platform_tables
from extract_oracle.capabilities import MODULES
from extract_oracle.cli import main
from extract_oracle.errors import ReasonCode
from extract_oracle.exit_codes import ExitCode
from extract_oracle.findings import COLLISION_CODES, VERDICTS, sort_collisions
from extract_oracle.rules import fold
from extract_oracle.zip_reader import read_archive

REPO = Path(__file__).resolve().parent.parent


def _write_lf(path: Path, text: str) -> None:
    """显式 LF 写盘，**Python 3.9 兼容**。

    为什么不用 `Path.write_text` 的 `newline=` 参数（这里刻意不写出完整调用式）：
    那个参数是 **3.10** 才加的，而本项目
    `requires-python >= 3.9` —— CI 首推首跑实测：3.9 通道上 14 条测试报
    `TypeError: write_text() got an unexpected keyword argument 'newline'`。
    判别 = **"我用的是不是 3.9 就有的写法？"**（`plan/05` §五 U10 从"未实跑"变成"实跑结论"的那一格）。
    """

    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)

FIXTURES = REPO / "data" / "fixtures"
TRUTH = FIXTURES / "truth"
PLATFORM_DIR = REPO / "data" / "platforms"

sys.path.insert(0, str(REPO / "tools"))

import gen_fixtures  # noqa: E402


def _synthetic(tmp_path: Path, name: str, pairs: list[tuple[str, bytes]]) -> Path:
    """用生成器的 `build_zip` 现造一份两/多条目的样本（不落 fixture 目录，不碰真值）。"""

    entries = [gen_fixtures.Entry(item.encode("utf-8"), payload) for item, payload in pairs]
    path = tmp_path / name
    path.write_bytes(gen_fixtures.build_zip(entries))
    return path


@pytest.fixture(scope="module")
def tables():
    return platform_tables.load(PLATFORM_DIR)


def _archive(name: str):
    return read_archive(FIXTURES / name)


def _collisions(name: str, target: str, tables) -> tuple:
    return fold.check(_archive(name), [target], tables)


def _codes(name: str, target: str, tables) -> list[str]:
    return [item.code for item in _collisions(name, target, tables)]


# ------------------------------------------------------------------ 能力门（K08）


def test_fold_module_is_implemented():
    """`capabilities.fold` 已翻 True——本文件就是它的验收靶子（同提交，K08）。"""

    module = next(item for item in MODULES if item.name == "fold")
    assert module.implemented is True
    assert module.rule_prefix == "collision.*"


def test_fold_module_is_dispatchable_from_cli(capsys):
    """翻 True 之后 `--module fold` 必须真能跑（不是"翻了个没分派的门"）。"""

    assert main(["check", str(FIXTURES / "clean.zip"), "--target", "windows", "--module", "fold"]) == int(
        ExitCode.OK
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["modules"] == ["fold"]
    assert payload["collisions"] == []


# ------------------------------------------------------------------ 平台表接入


def test_platform_table_sha256_is_verified_byte_by_byte(tables):
    """`plan/02` §四 第 2 条：表本体与 `meta.json` 的 sha256 必须逐字节对上。"""

    body = (PLATFORM_DIR / "ntfs-upcase.bin").read_bytes()
    assert tables.ntfs.sha256 == hashlib.sha256(body).hexdigest()
    assert tables.ntfs.entries * 2 == len(body) == 131072


def test_platform_table_source_is_enum_only(tables):
    """K04：`source` ∈ {`volume_read`,`host_probe`}；`casefold` 不是合法值。"""

    assert tables.ntfs.source in platform_tables.VALID_SOURCES
    assert "casefold" not in platform_tables.VALID_SOURCES


def test_replaced_table_is_refused_not_silently_used(tmp_path):
    """表被换过 → `platform_table_missing`（退出码 3），**不静默使用**。"""

    (tmp_path / "meta.json").write_bytes((PLATFORM_DIR / "meta.json").read_bytes())
    tampered = bytearray((PLATFORM_DIR / "ntfs-upcase.bin").read_bytes())
    tampered[0x41 * 2] ^= 0xFF  # 改一个字节
    (tmp_path / "ntfs-upcase.bin").write_bytes(bytes(tampered))

    with pytest.raises(Exception) as excinfo:
        platform_tables.load(tmp_path)
    assert getattr(excinfo.value, "code", None) is ReasonCode.PLATFORM_TABLE_MISSING


def test_illegal_source_value_is_refused(tmp_path):
    """`source: "casefold"` 必须被拒（决策 ③ 的机读形态）。"""

    meta = json.loads((PLATFORM_DIR / "meta.json").read_text(encoding="utf-8"))
    meta["ntfs_upcase"]["source"] = "casefold"
    _write_lf(tmp_path / "meta.json", json.dumps(meta))
    (tmp_path / "ntfs-upcase.bin").write_bytes((PLATFORM_DIR / "ntfs-upcase.bin").read_bytes())

    with pytest.raises(Exception) as excinfo:
        platform_tables.load(tmp_path)
    error = excinfo.value
    assert getattr(error, "code", None) is ReasonCode.PLATFORM_TABLE_MISSING
    assert error.detail["value"] == "casefold"


def test_missing_table_dir_is_refused(tmp_path):
    with pytest.raises(Exception) as excinfo:
        platform_tables.load(tmp_path)
    assert getattr(excinfo.value, "code", None) is ReasonCode.PLATFORM_TABLE_MISSING


def test_probed_at_utc_is_not_a_judgement_input(tables):
    """`probed_at_utc` 是环境事实，不进判定报告面（否则跨机复跑必红）。"""

    digest = json.dumps(tables.to_report_dict(), sort_keys=True, ensure_ascii=False)
    assert "probed_at_utc" not in digest
    assert "2026-10" not in digest  # 也不得间接触发时间戳正则

    # 反向：`--verify` 的诊断面**可以**带它（那是它的用途），但那是另一条通路。
    assert "probed_at_utc" in json.dumps(tables.verify_report(), sort_keys=True)


def test_check_report_carries_table_identity_but_no_timestamp(capsys):
    """`check` 报告带表 sha256（跨机可比），不带探测时点。"""

    main(["check", str(FIXTURES / "case.zip"), "--target", "windows", "--module", "fold"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["platforms"]["ntfs_upcase"]["sha256"] == platform_tables.load(PLATFORM_DIR).ntfs.sha256
    assert "probed_at_utc" not in json.dumps(payload, sort_keys=True)


def test_platforms_verify_reports_real_fingerprint(capsys):
    """`platforms --verify` 从占位变成真校验：打印表指纹 + 卷标识，退出码 0。"""

    assert main(["platforms", "--verify"]) == int(ExitCode.OK)
    out = capsys.readouterr().out
    assert "entries=65536" in out
    assert "sha256=41c26bc7a12bdaeb" in out  # 表指纹前缀（完整值见 meta.json）
    assert "serial=445ED634" in out


def test_platforms_verify_json_carries_full_fingerprint(capsys):
    assert main(["platforms", "--verify", "--format", "json"]) == int(ExitCode.OK)
    payload = json.loads(capsys.readouterr().out)
    assert payload["verified"] is True
    assert len(payload["ntfs_upcase"]["sha256"]) == 64
    assert payload["ntfs_upcase"]["source"] == "host_probe"


def test_platforms_verify_refuses_tampered_dir(tmp_path, capsys):
    """对账不过 → 退出码 3 + 机读错误行，stdout 不产出半份报告。"""

    (tmp_path / "meta.json").write_bytes((PLATFORM_DIR / "meta.json").read_bytes())
    (tmp_path / "ntfs-upcase.bin").write_bytes(b"\x00" * 131072)
    code = main(["platforms", "--verify", "--dir", str(tmp_path)])
    assert code == int(ExitCode.CAPABILITY_MISSING)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err.strip())["error"] == ReasonCode.PLATFORM_TABLE_MISSING.value


def test_check_refuses_when_platform_table_missing(tmp_path, capsys, monkeypatch):
    """`--module fold` 但表缺 → 3，不是"零冲突"的假绿。"""

    monkeypatch.setenv(platform_tables.ENV_DIR, str(tmp_path))
    monkeypatch.chdir(tmp_path)  # 让 cwd 候选也落到空目录
    code = main(["check", str(FIXTURES / "case.zip"), "--target", "windows", "--module", "fold"])
    assert code == int(ExitCode.CAPABILITY_MISSING)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err.strip())["error"] == ReasonCode.PLATFORM_TABLE_MISSING.value


# ------------------------------------------------------------------ 四条规则 · 分平台


def test_case_zip_windows_reports_exactly_one_casefold(tables):
    """`case.zip --target windows` → 恰 1 条 `CASEFOLD`，`survivor=README.TXT`。"""

    items = _collisions("case.zip", "windows", tables)
    assert [item.code for item in items] == ["collision.CASEFOLD"]
    item = items[0]
    assert item.names == ("Readme.txt", "README.TXT")
    assert item.write_order == (0, 1)  # CD 顺序
    assert item.survivor == "README.TXT"  # 后写者；与 §1.3.1 实测"内容为 LOWER"一致
    assert item.verdict == "overwritten"
    assert item.evidence_strength == "table_simulated"


def test_case_zip_macos_and_linux_do_not_report_casefold(tables):
    """macOS 无折叠表（不近似）、Linux 不做折叠——两边都不得报 `CASEFOLD`。"""

    for target in ("macos", "linux"):
        assert "collision.CASEFOLD" not in _codes("case.zip", target, tables), target
        assert _collisions("case.zip", target, tables) == (), target


def test_norm_zip_windows_does_not_report_nfc(tables):
    """NTFS 把名字当不透明 WCHAR 序列 → NFC/NFD 是两个不同的文件。"""

    assert "collision.NFC" not in _codes("norm.zip", "windows", tables)
    assert _collisions("norm.zip", "windows", tables) == ()


def test_norm_zip_macos_reports_nfc(tables):
    """macOS 必须报 NFC，并带 `evidence_strength: medium`（决策 ④）。"""

    items = _collisions("norm.zip", "macos", tables)
    assert [item.code for item in items] == ["collision.NFC"]
    assert items[0].evidence_strength == "medium"
    assert "非 Apple 官方规范" in items[0].evidence["note"]


def test_norm_zip_linux_does_not_report_nfc(tables):
    assert _codes("norm.zip", "linux", tables) == []


def test_trim_zip_reports_trim_and_survivor(tables):
    """`trim.zip` → `collision.TRIM` + `survivor=readme`（`readme.` 被裁剪后覆盖）。"""

    items = _collisions("trim.zip", "windows", tables)
    assert [item.code for item in items] == ["collision.TRIM"]
    assert items[0].survivor == "readme"
    assert items[0].on_disk_names == ("readme", "readme")


def test_trim_is_windows_only(tables):
    for target in ("macos", "linux"):
        assert _codes("trim.zip", target, tables) == [], target


def test_filedir_is_reported_on_all_three_platforms(tables):
    """`filedir.zip` → 三平台都报（M1 实测；不是"大小写不敏感卷"的推论）。"""

    for target in fold.PLATFORMS:
        items = _collisions("filedir.zip", target, tables)
        assert [item.code for item in items] == ["collision.FILEDIR"], target
        assert items[0].survivor == "a", target  # 先写者存活：后写者根本没落盘
        assert items[0].verdict == "skipped", target


def test_clean_zip_has_no_collisions_on_any_platform(tables):
    """零误报基线。"""

    for target in fold.PLATFORMS:
        assert _collisions("clean.zip", target, tables) == (), target


def test_no_collisions_across_all_other_fixtures(tables):
    """其余 18 份样本在三平台上都不得报折叠冲突（除真值里写明的四份）。"""

    with_truth = {"case.zip", "norm.zip", "trim.zip", "filedir.zip"}
    offenders = []
    for path in sorted(FIXTURES.iterdir()):
        if path.suffix not in {".zip", ".epub"} or path.name in with_truth:
            continue
        archive = read_archive(path)
        for target in fold.PLATFORMS:
            found = fold.check(archive, [target], tables)
            if found:
                offenders.append((path.name, target, [item.code for item in found]))
    assert offenders == []


# ------------------------------------------------------------------ 判定顺序与形状


def test_judgement_order_is_fixed():
    """`data/README.md` §4.3：FILEDIR → CASEFOLD → NFC → TRIM。"""

    assert fold.JUDGEMENT_ORDER == (
        "collision.FILEDIR",
        "collision.CASEFOLD",
        "collision.NFC",
        "collision.TRIM",
    )
    assert tuple(COLLISION_CODES) == fold.JUDGEMENT_ORDER


def test_order_is_joint_evaluated_not_short_circuited(tmp_path, tables):
    """同一对可命中多条，**全部输出**（不是"先命中先返回"）。

    构造 `a.txt` + `A.TXT.`：
    - `CASEFOLD`：`fold(trim('a.txt'))` 与 `fold(trim('A.TXT.'))` 都是 `A.TXT`，且裁剪后逐字节不同；
    - `TRIM`：`A.TXT.` 裁成 `A.TXT`，但两条裁剪后不同 → TRIM 不成立。

    因而这一对只命中 CASEFOLD。要证明"全部输出"，用跨规则组合更直接：
    `a`（文件）+ `A`（文件）+ `a/b` 在 Windows 上同时给出 `CASEFOLD(a,A)` 与
    **两条** `FILEDIR`（`a`↔`a/b`、`A`↔`a/b`，因为 `A` 在 NTFS 上就是 `a`）。
    跨规则**不短路**、同规则**逐对穷举**——两者都在这一条里被钉住。
    """

    path = _synthetic(tmp_path, "both.zip", [("a", b"1"), ("A", b"2"), ("a/b", b"3")])
    found = fold.check(read_archive(path), ["windows"], tables)
    codes = sorted(item.code for item in found)
    assert codes == ["collision.CASEFOLD", "collision.FILEDIR", "collision.FILEDIR"], codes


def test_trim_and_casefold_are_a_partition_not_a_double_count(tmp_path, tables):
    """`trim(a)==trim(b)` 的对子只归 `TRIM`（不重复报 `CASEFOLD`），反之亦然。"""

    trim_only = _synthetic(tmp_path, "trim_only.zip", [("readme.", b"1"), ("readme", b"2")])
    assert [item.code for item in fold.check(read_archive(trim_only), ["windows"], tables)] == [
        "collision.TRIM"
    ]

    case_only = _synthetic(tmp_path, "case_only.zip", [("a.txt", b"1"), ("A.TXT.", b"2")])
    assert [item.code for item in fold.check(read_archive(case_only), ["windows"], tables)] == [
        "collision.CASEFOLD"
    ]


def test_collisions_are_sorted_by_min_cd_offset_then_code(tables):
    """`data/README.md` §4.8：`(min(cd_offset), code)` 升序。"""

    items = fold.check(_archive("filedir.zip"), ["windows", "macos", "linux"], tables)
    keys = [(min(item.cd_offsets), item.code) for item in items]
    assert keys == sorted(keys)
    assert sort_collisions(items) == items


def test_verdict_vocabulary_is_closed(tables):
    """`verdict` ∈ {`overwritten`, `renamed`, `skipped`}（`data/README.md` §4.9）。"""

    seen = set()
    for name in ("case.zip", "norm.zip", "trim.zip", "filedir.zip"):
        for target in fold.PLATFORMS:
            for item in _collisions(name, target, tables):
                assert item.verdict in VERDICTS
                seen.add(item.verdict)
    assert seen == {"overwritten", "skipped"}


def test_collision_shape_has_no_absent_fields(tables):
    item = _collisions("case.zip", "windows", tables)[0].to_dict()
    for key in (
        "code",
        "platform",
        "names",
        "onDiskNames",
        "writeOrder",
        "cdOffsets",
        "survivor",
        "survivorEntryIndex",
        "verdict",
        "evidenceStrength",
        "evidence",
    ):
        assert key in item, key
    assert len(item["names"]) == len(item["onDiskNames"]) == len(item["writeOrder"]) == len(
        item["cdOffsets"]
    )


# ------------------------------------------------------------------ 真值对账


def _expected(name: str) -> dict | None:
    return json.loads((TRUTH / f"{name}.json").read_text(encoding="utf-8")).get("expected_collisions")


@pytest.mark.parametrize(
    "fixture", ["case.zip", "norm.zip", "trim.zip", "filedir.zip"]
)
def test_collisions_match_truth_per_platform(fixture: str, tables):
    """读真值 → 跑 MOD-3 → 逐平台逐条比较（`code` + `survivor`），不只看数量。"""

    expected = _expected(fixture)
    assert expected is not None, f"{fixture} 真值缺 expected_collisions"
    assert set(expected) == set(fold.PLATFORMS)
    for target in fold.PLATFORMS:
        want = expected[target]
        got = _collisions(fixture, target, tables)
        assert len(got) == len(want), (fixture, target, [i.code for i in got])
        for item, record in zip(got, want):
            assert item.code == record["code"], (fixture, target)
            if "survivor" in record:
                assert item.survivor == record["survivor"], (fixture, target)


# ------------------------------------------------------------------ 8 组字符对回归


def test_eight_pairs_table_matches_real_volume_measurement(tables):
    """① **真表结果 = 卷实测**：8 组逐一比对（实测值登记在 `meta.json`）。"""

    meta = json.loads((PLATFORM_DIR / "meta.json").read_text(encoding="utf-8"))
    verification = meta["ntfs_upcase"]["verification"]
    assert verification["pairs_checked"] == 8
    assert verification["pairs_agree"] == 8

    for record in verification["pairs"]:
        first, second = record["first"], record["second"]
        table_says = tables.windows.fold(first) == tables.windows.fold(second)
        assert table_says == record["table_says_collide"], (first, second)
        assert table_says == record["fs_says_collide"], (first, second)


def test_eight_pairs_casefold_approximation_is_wrong(tables):
    """② **`casefold` 近似结果 ≠ 真表结果**——这条就是"近似法为什么不能用"的机器证明。

    8 组里至少 4 组不一致（`ſ/S`、`ß/SS`、`ß/ss`、`ǅ/Ǆ`）。**断言这些差异真实存在**，
    而不是只断言"有差异"（否则只要有一组不同就能蒙混过关）。
    """

    meta = json.loads((PLATFORM_DIR / "meta.json").read_text(encoding="utf-8"))
    pairs = [(r["first"], r["second"]) for r in meta["ntfs_upcase"]["verification"]["pairs"]]

    diverged = []
    for first, second in pairs:
        table_says = tables.windows.fold(first) == tables.windows.fold(second)
        approx_says = first.casefold() == second.casefold()
        if table_says != approx_says:
            diverged.append((first, second, table_says, approx_says))

    measured = {(r["first"], r["second"]): r["fs_says_collide"] for r in meta["ntfs_upcase"]["verification"]["pairs"]}
    # 差异处必须"真表 = 实测"而"近似 ≠ 实测"
    for first, second, table_says, approx_says in diverged:
        assert table_says == measured[(first, second)], (first, second)
        assert approx_says != measured[(first, second)], (first, second)

    assert len(diverged) >= 4, [f"{a}/{b}" for a, b, *_ in diverged]
    # 具体点名的四组（`docs/rules.md` §四 的复核表）
    assert {(a, b) for a, b, *_ in diverged} >= {
        ("ſ", "S"),
        ("ß", "SS"),
        ("ß", "ss"),
        ("ǅ", "Ǆ"),
    }


def test_eight_pairs_via_fold_rule_not_just_the_table(tables, tmp_path):
    """同样四组结论要能从**判定入口**（`rules/fold.py` 的 CASEFOLD）得到，不只是查表原语。"""

    cases = {
        "tau_sigma": ("ſ.txt", "S.txt", True),  # 真表：不冲突；casefold 会判冲突
        "sharp_s_ss": ("ß.txt", "ss.txt", True),  # 真表：不冲突
        "dz": ("ǅ.txt", "Ǆ.txt", True),  # 真表：不冲突
        "omega": ("ω.txt", "Ω.txt", False),  # 真表：冲突
        "eacute": ("é.txt", "É.txt", False),  # 对照组：冲突
    }
    for label, (first, second, expect_no_collision) in cases.items():
        path = _synthetic(tmp_path, f"{label}.zip", [(first, b"a"), (second, b"b")])
        found = fold.check(read_archive(path), ["windows"], tables)
        codes = [item.code for item in found]
        if expect_no_collision:
            assert codes == [], (label, codes)
        else:
            assert codes == ["collision.CASEFOLD"], (label, codes)
            assert found[0].survivor == second


#: `docs/rules.md` §四 复核表的 8 组（`HANDOFF-M3` §3 第 5 条点名的就是这张表，**不是** `meta.json`）。
#:
#: 为什么两处不一样：`tools/fetch_upcase.PROBE_PAIRS` 是**每轮重取表时真跑**的探测对
#: （含 `a/A` 对照组），而本表是**人读复核表**（含 `İ/i` —— M0 记错、M1 改正的两格之一）。
#: `meta.json` 的 `verification.pairs` 里没有 `İ/i`，所以只用 `meta.json` 驱动回归会漏掉这一格。
#: 真表对 `İ/i` 的答案是"不冲突"（`İ`→`İ`、`i`→`I`），与 §四 一致。
DOC_PAIRS: tuple[tuple[str, str, bool], ...] = (
    ("ı", "I", False),
    ("ſ", "S", False),
    ("ß", "SS", False),
    ("ß", "ss", False),
    ("İ", "i", False),
    ("ǅ", "Ǆ", False),
    ("ω", "Ω", True),
    ("é", "É", True),
)


def test_eight_pairs_of_docs_rules_table_are_reproduced(tables):
    """`docs/rules.md` §四 的 8 组逐组复现（含 `İ/i`——`meta.json` 的探测对里没有它）。

    这是 DoD 那句"8 组字符对回归全通过"的直接落点：判据取自**人读复核表**，
    而不是探测对列表（后者面向"重取表时的自动核对"，两者不是同一张表）。
    """

    assert len(DOC_PAIRS) == 8
    mismatched = [
        (first, second, tables.windows.fold(first) == tables.windows.fold(second), expected)
        for first, second, expected in DOC_PAIRS
        if (tables.windows.fold(first) == tables.windows.fold(second)) != expected
    ]
    assert mismatched == [], f"真表与 docs/rules.md §四 不符: {mismatched}"


@pytest.mark.parametrize("first,second,expected", DOC_PAIRS, ids=lambda v: str(v))
def test_docs_pairs_disagree_with_approximation_where_documented(
    tables, first: str, second: str, expected: bool
):
    """`docs/rules.md` §四 的每一组：真表必须与复核值一致；近似法若与真表不同，
    必须是"真表 = 实测"而"近似 ≠ 实测"（否则近似法反而是对的，决策 ③ 就没有依据）。

    **`İ/i` 这一格为什么必须在表里**：它是 M1 复核改正的两格之一（M0 记"冲突"，实测"不冲突"），
    而 `tools/fetch_upcase.PROBE_PAIRS` 里没有它（那里用 `a/A` 当对照组）。只靠探测对驱动回归，
    就会漏掉这格——`docs/rules.md` §四 的 8 组才是 DoD 点名的那张表。
    """

    table_says = tables.windows.fold(first) == tables.windows.fold(second)
    assert table_says == expected, (first, second)

    approximations = {
        "casefold": first.casefold() == second.casefold(),
        "upper": first.upper() == second.upper(),
        "lower": first.lower() == second.lower(),
    }
    for label, approx in approximations.items():
        if approx == table_says:
            continue
        # 近似与真表不同 → 近似必然与"真表 = 实测"的结论相反
        assert approx != table_says, (first, second, label)


def test_docs_rules_section_4_m0_corrections_are_reflected(tables):
    """M1 改写的那两格（`İ/i` 与 `é/É`）必须与真表一致——防"表对了但文档没改"的漂移。

    M0 原表：`İ/i` 记"冲突"（实测不冲突）、`é/É` 记"不冲突"（实测冲突）。两格都已按实测改正；
    本断言把"改正后的值"钉在真表上，任何人把文档改回去都会红。
    """

    m0_values = {  # `data/README.md` §1.3.3 的 M0 列（已知错的两格在这里）
        ("İ", "i"): True,
        ("é", "É"): False,
    }
    for (first, second), m0 in m0_values.items():
        real = tables.windows.fold(first) == tables.windows.fold(second)
        assert real != m0, f"{first}/{second}: M0 值与真表相同，说明复核改正被回退了"


# ------------------------------------------------------------------ 确定性


def test_check_fold_output_is_byte_identical_across_runs():
    """K09：同输入双跑逐字节一致（含平台表身份块）。"""

    import io
    from contextlib import redirect_stdout

    def run() -> tuple[int, str]:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(
                ["check", str(FIXTURES / "filedir.zip"), "--target", "windows", "--module", "fold"]
            )
        return code, buffer.getvalue()

    assert run() == run()


def test_check_fold_output_has_no_host_path_or_timestamp():
    import io
    import re
    from contextlib import redirect_stdout

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        main(["check", str(FIXTURES / "case.zip"), "--target", "windows", "--module", "fold"])
    text = buffer.getvalue()
    assert not re.search(r"\b[A-Za-z]:[\\/]", text)
    assert "/home/" not in text and "/Users/" not in text
    assert not re.search(r"\b20\d{2}-\d{2}-\d{2}T\d{2}:", text)


def test_fold_targets_are_independently_assertable(capsys):
    """三个 `--target` 各自的结论要能分开断言（`--target` 一次给多个时按平台分别输出）。"""

    assert main(
        ["check", str(FIXTURES / "norm.zip"), "--target", "windows,macos", "--module", "fold"]
    ) == int(ExitCode.FINDINGS)
    payload = json.loads(capsys.readouterr().out)
    assert payload["targets"] == ["windows", "macos"]
    assert [(item["code"], item["platform"]) for item in payload["collisions"]] == [
        ("collision.NFC", "macos")
    ]


def test_fold_entry_point_runs_in_subprocess(tmp_path):
    """`python -m extract_oracle` 通路（交付态入口的独立冒烟）。"""

    env = {"PYTHONPATH": str(REPO / "src"), "PYTHONUTF8": "1"}
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "extract_oracle",
            "check",
            str(FIXTURES / "case.zip"),
            "--target",
            "windows",
            "--module",
            "fold",
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
        env={**os.environ, **env},
        cwd=str(tmp_path),
    )
    assert proc.returncode == 1, proc.stderr  # 有冲突 → 1（不是 0）
    payload = json.loads(proc.stdout)
    assert payload["collisions"][0]["survivor"] == "README.TXT"
