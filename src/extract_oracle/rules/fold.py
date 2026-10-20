"""MOD-3 跨平台落盘折叠（`plan/03` §MOD-3，`data/README.md` §4.3 / §4.9）。

**四条规则，判定顺序固定：FILEDIR → CASEFOLD → NFC → TRIM**（同一对名字可命中多条，全部输出；
输出顺序另由 `data/README.md` §4.8 的 `(min(cd_offset), code)` 决定——评估顺序 ≠ 输出顺序）。

| `ruleId` | 判定 | windows | macos | linux |
|---|---|---|---|---|
| `collision.FILEDIR` | 同一路径既要当文件又要当目录 | 报 | 报 | 报 |
| `collision.CASEFOLD` | 目标平台大小写规则下相撞 | **真实 `$UpCase` 表** | **不报**（无 macOS 折叠表，不近似） | 不报（不做折叠） |
| `collision.NFC` | 归一化后相撞 | 不报（不做归一化） | **报**（NFD 比较） | 不报 |
| `collision.TRIM` | 尾随空格/点裁剪后相撞 | 报 | 不报 | 不报 |

**Windows 折叠只能来自 `data/platforms/ntfs-upcase.bin`**（决策 ③）。本模块里**不出现**
`casefold` / `.lower()` / `.upper()`——`tests/test_rule_boundaries.py` 的 AST 守门会红，
而且近似法在 `ǅ/Ǆ` 上确实会给出假阳性（`data/README.md` §1.3.3）。

**macOS 为什么不报 CASEFOLD**：HFS+/APFS 的大小写敏感性是**卷格式选项**（可以建成大小写敏感卷），
而我们没有 macOS 的折叠表；用 Python 的 `lower()` 近似会违反决策 ③。所以这里**不猜**：
macOS 侧只报由 TN1150/UAX #15 支持、且实现观察一致的 NFC，`evidence_strength: medium`。
这条口径与 `case.zip` 的真值（macos 无 CASEFOLD）一致，并在 `data/README.md` §4.3 留痕。

**写序 → 存活者**：`writeOrder` = CD 顺序；`survivor` = 最后写入者（`FILEDIR` 例外：
先写者存活，因为后写者根本没落盘）；`verdict` ∈ {`overwritten`, `renamed`, `skipped`}。

纯函数：`(Archive, targets, PlatformTables) -> tuple[Collision, ...]`。不写盘、不联网、
不 import 其他判定模块、不 import `cli`（K10）。
"""

from __future__ import annotations

import unicodedata

from ..findings import VERDICTS, Collision, sort_collisions
from ..platforms import PlatformTables
from ..zip_reader import Archive, EntryView

#: 目标平台（与 `cli.TARGETS` 同序；`data/README.md` §4.3 的三个平台行）。
PLATFORMS: tuple[str, ...] = ("windows", "macos", "linux")

#: **判定顺序**（`data/README.md` §4.3：FILEDIR → CASEFOLD → NFC → TRIM）。
JUDGEMENT_ORDER: tuple[str, ...] = (
    "collision.FILEDIR",
    "collision.CASEFOLD",
    "collision.NFC",
    "collision.TRIM",
)

#: Windows 的尾随裁剪字符集（MS Learn 命名约定：尾随空格与尾随点被裁剪）。
WINDOWS_TRAILING_CHARS = " ."

#: 每条规则在每个平台上的证据强度（`data/README.md` §4.7 的四枚举值）。
#:
#: **按 (平台, 规则) 固定，不看本机是什么系统**——否则同一输入在 Windows 与 Linux 上会给出
#: 不同的 `evidence_strength`，直接违反"同输入 + 同平台表 → 同一输出"（`plan/02` §六）。
EVIDENCE: dict[str, dict[str, str]] = {
    "collision.FILEDIR": {"windows": "measured", "macos": "measured", "linux": "measured"},
    "collision.CASEFOLD": {"windows": "table_simulated"},
    "collision.NFC": {"macos": "medium"},
    "collision.TRIM": {"windows": "measured"},
}

#: 依据出处（逐个规则一条；`docs/rules.md` §七 是原句台账）。
SOURCES: dict[str, str] = {
    "collision.FILEDIR": "structural_self_evidence",
    "collision.CASEFOLD": "ntfs_upcase_table",
    "collision.NFC": "TN1150 + UAX #15 + libfsapfs",
    "collision.TRIM": "MS Learn naming conventions",
}


def _as_text(raw: bytes) -> str:
    """原始名字节 → 参与判定的字符串。

    用 `surrogateescape`（**逐字节可逆**，仅在本模块内部用于比较）。展示形另走
    `findings.display_name`（`backslashreplace`）——两者用途不同，别混用（`plan/03` §0）。
    """

    return raw.decode("utf-8", "surrogateescape")


def _is_dir_prefix(file_name: bytes, other_name: bytes) -> bool:
    """`other_name` 是否是 `file_name + "/" + …`（字节比较，不解码）。"""

    prefix = file_name + b"/"
    return other_name.startswith(prefix) and len(other_name) > len(prefix)


def _split(name: str) -> list[str]:
    return name.split("/")


def trim_trailing(name: str) -> str:
    """Windows 裁剪：**逐组件**去掉尾随空格与点（不是整串）。

    `readme.` → `readme`；`a./b. ` → `a/b`。组件被裁成空串时保留原样（那是 MOD-4 的
    `BLOCKED` 语域，不是折叠问题）。
    """

    parts = []
    for part in _split(name):
        trimmed = part.rstrip(WINDOWS_TRAILING_CHARS)
        parts.append(trimmed if trimmed else part)
    return "/".join(parts)


def nfd(name: str) -> str:
    """macOS 侧的比较形：NFD（TN1150 "fully decomposed and in canonical order"）。"""

    return unicodedata.normalize("NFD", name)


def _entries(archive: Archive) -> tuple[EntryView, ...]:
    return archive.entries


def _pair_base(
    code: str,
    platform: str,
    left: EntryView,
    right: EntryView,
    *,
    on_disk: tuple[str, str],
    evidence: dict,
) -> Collision:
    """一条「两个条目相撞」的公共形状。`left` 在 CD 顺序里先于 `right`。"""

    return Collision(
        code=code,
        platform=platform,
        names=(_as_text(left.cd_name), _as_text(right.cd_name)),
        on_disk_names=on_disk,
        write_order=(left.index, right.index),
        cd_offsets=(left.cd_offset, right.cd_offset),
        survivor=_as_text(right.cd_name),
        survivor_entry_index=right.index,
        verdict="overwritten",
        evidence_strength=EVIDENCE[code][platform],
        evidence={**evidence, "source": SOURCES[code]},
    )


# ------------------------------------------------------------------ FILEDIR


def _is_dir_prefix(file_name: bytes, other_name: bytes) -> bool:
    """`other_name` 是否是 `file_name + "/" + …`（字节比较，不解码）。"""

    prefix = file_name + b"/"
    return other_name.startswith(prefix) and len(other_name) > len(prefix)


def _prefix_view(name: str, platform: str, tables: PlatformTables) -> str:
    """FILEDIR 的"路径视图"：该平台上"这是不是同一段路径"的等价判定形。

    - `windows`：先裁尾随空格/点，再按真实 `$UpCase` 表折叠（`a` 文件会挡住 `A/b` 的目录创建）；
    - `macos`：NFD（归一化不敏感）；
    - `linux`：原名（逐字节）。

    这是 FILEDIR 与 CASEFOLD 能**同时命中**的来源：`a`（文件）+ `A`（文件）+ `a/b` 在 Windows 上
    既有 `CASEFOLD(a, A)`，又有 `FILEDIR(A, a/b)`——"全部输出"，不在规则间短路。
    """

    if platform == "windows":
        return tables.windows.fold(trim_trailing(name))
    if platform == "macos":
        return nfd(name)
    return name


def filedir_pairs(archive: Archive, platform: str, tables: PlatformTables) -> list[Collision]:
    """`collision.FILEDIR`：同一路径既要当文件又要当目录（`a` 与 `a/b` 并存）。

    三平台都报：本机四工具实测（`data/README.md` §3.2 的 `filedir.zip` 行）三个平台都表现为失败
    ——Python 抛 `FileNotFoundError`、unzip rc=2 `a exists but is not directory`、7-Zip rc=2；
    只有 bsdtar 会把 `a` 转成目录再写 `a/b`。所以这条**不是**「大小写不敏感卷」的推论。

    路径比较走 `_prefix_view`（平台等价形），因此 `a` + `A/b` 在 Windows 上也算 FILEDIR
    ——并且能与 `CASEFOLD` **同时命中**（"全部输出"）。
    """

    found: list[Collision] = []
    entries = _entries(archive)
    for left in entries:
        for right in entries:
            if left.index >= right.index:
                continue
            for file_entry, dir_entry in ((left, right), (right, left)):
                file_view = _prefix_view(_as_text(file_entry.cd_name), platform, tables)
                dir_view = _prefix_view(_as_text(dir_entry.cd_name), platform, tables)
                if not (dir_view.startswith(file_view + "/") and len(dir_view) > len(file_view) + 1):
                    continue
                first, second = sorted((file_entry, dir_entry), key=lambda item: item.index)
                found.append(
                    Collision(
                        code="collision.FILEDIR",
                        platform=platform,
                        names=(_as_text(first.cd_name), _as_text(second.cd_name)),
                        on_disk_names=(
                            _prefix_view(_as_text(first.cd_name), platform, tables),
                            _prefix_view(_as_text(second.cd_name), platform, tables),
                        ),
                        write_order=(first.index, second.index),
                        cd_offsets=(first.cd_offset, second.cd_offset),
                        # 先写者存活：后写者要么建不出文件（同名目录已在），要么建不出目录。
                        survivor=_as_text(first.cd_name),
                        survivor_entry_index=first.index,
                        verdict="skipped",
                        evidence_strength=EVIDENCE["collision.FILEDIR"][platform],
                        evidence={
                            "fileEntryIndex": file_entry.index,
                            "directoryEntryIndex": dir_entry.index,
                            "reason": "同一路径既是文件又要求作目录",
                            "readers": {
                                "python-zipfile": "error",
                                "info-zip-unzip": "error",
                                "7zip": "error",
                                "libarchive": "coerced_to_directory",
                            },
                            "source": SOURCES["collision.FILEDIR"],
                        },
                    )
                )
                break  # 一对条目最多产生一条 FILEDIR
    return found


# ------------------------------------------------------------------ CASEFOLD


def casefold_pairs(archive: Archive, platform: str, tables: PlatformTables) -> list[Collision]:
    """`collision.CASEFOLD`：目标平台大小写规则下相撞。

    只有 `windows` 参与判定，且折叠**逐码元查真实 `$UpCase` 表**（决策 ③）。

    NTFS 的"是不是同一个文件"= **先裁尾随空格/点、再做大小写无关比较**，所以比较键取
    `fold(trim(name))`。为了不与 `collision.TRIM` 重复计数，**裁剪后逐字节相同的对子归 TRIM**，
    这里跳过（两条规则由此构成一个划分：`trim(a)==trim(b)` → TRIM；否则 `fold(trim)` 相等 → CASEFOLD）。
    `/`（U+002F）在表里是恒等映射，所以整串折叠不会串组件。
    """

    if platform != "windows":
        return []  # macos：无折叠表不近似；linux：不做折叠

    table = tables.windows
    found: list[Collision] = []
    entries = _entries(archive)
    for position, left in enumerate(entries):
        for right in entries[position + 1 :]:
            left_text = _as_text(left.cd_name)
            right_text = _as_text(right.cd_name)
            trimmed_left = trim_trailing(left_text)
            trimmed_right = trim_trailing(right_text)
            if trimmed_left == trimmed_right:
                continue  # 纯裁剪差异 → 归 collision.TRIM，不在这里重复报
            folded_left = table.fold(trimmed_left)
            folded_right = table.fold(trimmed_right)
            if folded_left != folded_right:
                continue
            found.append(
                _pair_base(
                    "collision.CASEFOLD",
                    platform,
                    left,
                    right,
                    # NTFS 保留**写入时**的大小写（`case.zip` 实测：落盘只有 `README.TXT`，
                    # 内容是后写者的 `LOWER`），但尾随空格/点已被裁掉。
                    on_disk=(trimmed_left, trimmed_right),
                    evidence={
                        "algorithm": "ntfs_upcase_table",
                        "tableSha256": table.table_id,
                        "compared": [trimmed_left, trimmed_right],
                        "folded": [folded_left, folded_right],
                    },
                )
            )
    return found


# ------------------------------------------------------------------ NFC


def nfc_pairs(archive: Archive, platform: str) -> list[Collision]:
    """`collision.NFC`：NFD 后相撞（macOS 做、Windows/Linux 不做）。

    Windows 把名字当**不透明 WCHAR 序列**（`data/README.md` §1.4 第一条原句），所以 NTFS 上
    NFC 与 NFD 是两个不同的文件——`norm.zip` 在 `--target windows` 下**不得**报这条。
    """

    if platform != "macos":
        return []

    found: list[Collision] = []
    entries = _entries(archive)
    for position, left in enumerate(entries):
        for right in entries[position + 1 :]:
            left_text = _as_text(left.cd_name)
            right_text = _as_text(right.cd_name)
            if left_text == right_text:
                continue  # 逐字节相同：那是 CASEFOLD/覆盖语义，不是归一化差异
            normalized_left = nfd(left_text)
            normalized_right = nfd(right_text)
            if normalized_left != normalized_right:
                continue
            found.append(
                _pair_base(
                    "collision.NFC",
                    platform,
                    left,
                    right,
                    on_disk=(normalized_left, normalized_right),
                    evidence={
                        "form": "NFD",
                        "normalized": [normalized_left, normalized_right],
                        "note": "实现观察，非 Apple 官方规范（plan/00 决策 ④）",
                    },
                )
            )
    return found


# ------------------------------------------------------------------ TRIM


def trim_pairs(archive: Archive, platform: str) -> list[Collision]:
    """`collision.TRIM`：尾随空格/点裁剪后相撞（仅 Windows）。"""

    if platform != "windows":
        return []

    found: list[Collision] = []
    entries = _entries(archive)
    for position, left in enumerate(entries):
        for right in entries[position + 1 :]:
            left_text = _as_text(left.cd_name)
            right_text = _as_text(right.cd_name)
            trimmed_left = trim_trailing(left_text)
            trimmed_right = trim_trailing(right_text)
            if trimmed_left != trimmed_right:
                continue
            if (left_text, right_text) == (trimmed_left, trimmed_right):
                continue  # 两条都没有被裁剪过 → 不相撞（那是别的规则的事）
            found.append(
                _pair_base(
                    "collision.TRIM",
                    platform,
                    left,
                    right,
                    on_disk=(trimmed_left, trimmed_right),
                    evidence={
                        "trimmed": [trimmed_left, trimmed_right],
                        "chars": WINDOWS_TRAILING_CHARS,
                    },
                )
            )
    return found


# ------------------------------------------------------------------ 入口


def check(
    archive: Archive,
    targets: tuple[str, ...] | list[str],
    tables: PlatformTables,
) -> tuple[Collision, ...]:
    """MOD-3 的全部判定。**评估顺序固定** FILEDIR → CASEFOLD → NFC → TRIM。

    输出顺序另由 `findings.sort_collisions`（`(min(cd_offset), code)`）决定。
    """

    unknown = [name for name in targets if name not in PLATFORMS]
    if unknown:
        raise AssertionError(f"未知目标平台: {unknown}")  # pragma: no cover - cli 已校验

    found: list[Collision] = []
    for platform in PLATFORMS:
        if platform not in targets:
            continue
        for code in JUDGEMENT_ORDER:
            if code == "collision.FILEDIR":
                found.extend(filedir_pairs(archive, platform, tables))
            elif code == "collision.CASEFOLD":
                found.extend(casefold_pairs(archive, platform, tables))
            elif code == "collision.NFC":
                found.extend(nfc_pairs(archive, platform))
            elif code == "collision.TRIM":
                found.extend(trim_pairs(archive, platform))
    for item in found:
        assert item.verdict in VERDICTS
    return sort_collisions(found)


__all__ = [
    "EVIDENCE",
    "JUDGEMENT_ORDER",
    "PLATFORMS",
    "SOURCES",
    "WINDOWS_TRAILING_CHARS",
    "casefold_pairs",
    "check",
    "filedir_pairs",
    "nfc_pairs",
    "nfd",
    "trim_pairs",
    "trim_trailing",
]
