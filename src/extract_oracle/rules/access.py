"""MOD-4 非法名与可访问性分级（`plan/03` §MOD-4，`data/README.md` §4.2）。

三级定义**只在 `data/README.md` §4.2 写一次**；本模块是它的执行体，不写第二份数值/口径表。
`OK` 是第四种取值但**不是级别**（它不参与分级评分，只是"无上述三情形"的标记）。

| 级别 | 判据（本项目落地形） |
|---|---|
| `BLOCKED` | 空名 / 空组件 / `.` / `..` / 含 NUL / Windows 非法字符 / Windows 单组件 > 255 个 UTF-16 码元 |
| `WRITTEN_UNREADABLE` | Windows 保留设备名出现在**最后一个点之前**（`CON.txt`、`COM1.log`、`CLOCK$`） |
| `WRITTEN_TRUNCATED` | Windows 尾随空格/点被裁剪；`:` 被按 ADS 语义截断为冒号前的部分 |
| `OK` | 其余 |

**为什么第三级是本题的差异点**：`CON.txt` 不违规、写入成功、名字没变，但应用层拿不到
（`data/README.md` §1.3.2 的三条实测）。竞品的判定停在"合不合规"，这里区分
"能不能写进去" / "写进去能不能被应用层拿到" / "拿到的还是不是原来那个名字"。

**判定顺序固定**：BLOCKED 类（空 / NUL / 非法字符 / 组件超长）→ 保留名 → 裁剪。
`reasons[]` 与 `evidence[]` **收集全部命中项**（不是先命中先返回），级别按上述顺序取第一个命中的档。

**按组件判定，`/` 是分隔符**：`a/b` 是"目录 a + 文件 b"，不是"一个含 `/` 的名字"。
真正让创建失败的是**空组件**（`a//b`、`/a`、`a/`）——`data/README.md` §4.2 的 2026-10-21 修订
把 Linux 的"名含 `/`"改写成这个可判定的形式（否则每一份带子目录的归档都会假报 `BLOCKED`）。

纯函数：`(Archive, targets, PlatformTables) -> dict`。不写盘、不联网、不 import 其他判定模块
（K10）。需要大小写无关比较时走 `tables.windows.fold()`——**本模块不出现**
`casefold` / `.lower()` / `.upper()`（`tests/test_rule_boundaries.py` 的 AST 守门）。
"""

from __future__ import annotations

from ..platforms import PlatformTables
from ..zip_reader import Archive

#: 目标平台（与 `cli.TARGETS` 同序）。
PLATFORMS: tuple[str, ...] = ("windows", "macos", "linux")

#: 四种取值（`data/README.md` §4.2）。`OK` 是"无三情形"的标记，**不是级别**。
LEVELS: tuple[str, ...] = ("BLOCKED", "WRITTEN_UNREADABLE", "WRITTEN_TRUNCATED", "OK")

#: 真正的三级（`OK` 不在其中——分级评分只看这三个）。
GRADES: tuple[str, ...] = ("BLOCKED", "WRITTEN_UNREADABLE", "WRITTEN_TRUNCATED")

#: Windows 非法字符（MS Learn 命名约定的保留字符集，**去掉 `:`**）。
#:
#: 为什么去掉 `:`：本机实测（2026-10-21）`CreateFileW('colon:name.txt')` **创建成功**，
#: NTFS 按 ADS 语义只存冒号前的 `colon`——名字变了但没失败，所以归 `WRITTEN_TRUNCATED`
#: 而不是 `BLOCKED`（`data/README.md` §4.2 的 2026-10-21 修订、`plan/05` §五 U11）。
WINDOWS_ILLEGAL: str = '<>\\|?*'

#: Windows 控制字符区间（0x01–0x1F；0x00 是 NUL，单独判）。
WINDOWS_CONTROL_RANGE = range(0x01, 0x20)

#: Windows 尾随裁剪字符集（与 `rules/fold.py::WINDOWS_TRAILING_CHARS` 同一依据）。
WINDOWS_TRAILING_CHARS: str = " ."

#: Windows 保留设备名（MS Learn 命名约定 + 本机实测的边界）。
#:
#: - `COM0` / `LPT0` **也**保留：本机实测 `COM0.txt` / `LPT0.txt` 同样 `Test-Path=False`
#:   （MS Learn 的枚举从 1 起，实测从 0 起都拿不到）；
#: - `COM10` 起不是保留名（实测 `Test-Path=True`）；
#: - `CLOCK$` 在 MS Learn 的正文里没列，但本机实测 `CLOCK$.txt` 不可读。
#:
#: **上标 ¹²³ 变体不在本表里**：MS Learn 说 `COM¹` 是设备名，但本机实测
#: `COM¹.txt` / `COM².txt` / `LPT³.log` 的 `CreateFileW` 创建成功、`Test-Path=True`、
#: `Get-Content` 读得到（`CreateFileW` 走的是文件命名空间，不是 CMD 的设备命名空间）。
#: 本工具预言的是**提取器走 Win32 文件 API 的落盘结果**，所以按实测判 `OK`；
#: 这条收窄记在 `data/README.md` §4.2 的 2026-10-21 修订里（不猜、按实测）。
RESERVED_DEVICE_NAMES: frozenset[str] = frozenset(
    {"CON", "PRN", "AUX", "NUL", "CLOCK$"}
    | {f"COM{index}" for index in range(10)}
    | {f"LPT{index}" for index in range(10)}
)

#: `evidence[]` 的封闭词表（机读依据；`data/README.md` §4.2）。
#:
#: 前三条是 `CON.txt` 的**实测三证据**（`data/README.md` §1.3.2）：
#: PowerShell `Test-Path -LiteralPath` = False、`Get-Content` 报 path does not exist、
#: Python `open()` 读到内容。它们证明"文件在盘上，但应用层拿不到"。
EVIDENCE_TOKENS: tuple[str, ...] = (
    "test_path_false",
    "get_content_error",
    "open_readable",
    "illegal_char",
    "nul_byte",
    "empty_component",
    "dot_component",
    "component_too_long",
    "reserved_device_name",
    "trailing_space_or_dot",
    "ads_colon_truncation",
)

#: 保留名 verdict 的三证据（顺序固定，逐条都是实测来源）。
RESERVED_EVIDENCE: tuple[str, ...] = ("test_path_false", "get_content_error", "open_readable")

#: 每条 reason 的固定枚举值（`reason` 是机读键，`REASON_TOKENS` 钉住封闭性）。
REASON_TOKENS: tuple[str, ...] = (
    "empty_name",
    "nul_byte",
    "empty_component",
    "dot_component",
    "illegal_char",
    "component_too_long",
    "reserved_device_name",
    "trailing_space_or_dot",
    "ads_colon_truncation",
)

#: Windows 单组件的上限（`data/README.md` §4.6 的 `win_max_path` 邻近口径：
#: 组件按 **UTF-16 码元**计；256 码元 `CreateFileW` 直接失败 → `BLOCKED`）。
WINDOWS_MAX_COMPONENT = 255


def _split_components(name: str) -> list[str]:
    """按 `/` 切组件。`/` 是路径分隔符，不是名字的一部分（`data/README.md` §4.2）。"""

    return name.split("/")


def _stem_before_last_dot(component: str) -> str:
    """保留名匹配的键：**最后一个点之前**的整体。

    `CON.txt` → `CON`；`AUX.tar.gz` → `AUX.tar`（不是保留名）；`CLOCK$` → `CLOCK$`。
    """

    index = component.rfind(".")
    return component if index < 0 else component[:index]


def _utf16_units(text: str) -> int:
    """按 UTF-16 码元计长（Windows 的组件口径；BMP 外算 2）。

    用 `surrogatepass`：判定用的名字来自 `surrogateescape`（非法 UTF-8 字节 → 孤立代理项），
    默认编码会抛 `UnicodeEncodeError`。孤立代理项在 UTF-16 里恰占 1 个码元，与"一个无法解码的
    字节算一个字符"的口径一致（展示形另走 `backslashreplace`，不在这里）。
    """

    return len(text.encode("utf-16-le", "surrogatepass")) // 2


def _judge_windows(
    name: str,
    components: list[str],
    tables: PlatformTables,
) -> tuple[str, list[str], list[str]]:
    """Windows 侧：BLOCKED 类 → 保留名 → 裁剪（顺序固定，`reasons` 全收）。"""

    reasons: list[str] = []
    evidence: list[str] = []

    if name == "":
        reasons.append("empty_name")
        evidence.append("empty_component")

    if "\x00" in name:
        reasons.append("nul_byte")
        evidence.append("nul_byte")

    for component in components:
        if component == "":
            if "empty_component" not in reasons:
                reasons.append("empty_component")
                evidence.append("empty_component")
            continue
        if component in (".", ".."):
            if "dot_component" not in reasons:
                reasons.append("dot_component")
                evidence.append("dot_component")
            continue
        if any(ch in WINDOWS_ILLEGAL for ch in component) or any(
            ord(ch) in WINDOWS_CONTROL_RANGE for ch in component
        ):
            if "illegal_char" not in reasons:
                reasons.append("illegal_char")
                evidence.append("illegal_char")
        if _utf16_units(component) > WINDOWS_MAX_COMPONENT:
            if "component_too_long" not in reasons:
                reasons.append("component_too_long")
                evidence.append("component_too_long")

    if reasons:
        return "BLOCKED", reasons, evidence

    # 保留名按**裁剪后**的组件匹配：Windows 先裁尾随空格/点、再判设备名。
    # 本机实测（2026-10-21）：`con.txt.` 落盘为 `con.txt`，而 `con.txt` 的 `Get-Content` 报错
    # ——所以裁剪+保留名同时成立时，级别是 `WRITTEN_UNREADABLE`（更严重的那一档）。
    trimmed_components = [component.rstrip(WINDOWS_TRAILING_CHARS) or component for component in components]
    reserved_hit = False
    for component in trimmed_components:
        stem = _stem_before_last_dot(component)
        if tables.windows.fold(stem) in RESERVED_DEVICE_NAMES:
            reserved_hit = True
            break

    if reserved_hit:
        reasons.append("reserved_device_name")
        evidence.extend(RESERVED_EVIDENCE)

    # 裁剪：尾随空格/点（逐组件）、`:` 的 ADS 截断（两者都可与保留名同时成立）。
    for component in components:
        if component != component.rstrip(WINDOWS_TRAILING_CHARS):
            if "trailing_space_or_dot" not in reasons:
                reasons.append("trailing_space_or_dot")
                evidence.append("trailing_space_or_dot")
        if ":" in component:
            if "ads_colon_truncation" not in reasons:
                reasons.append("ads_colon_truncation")
                evidence.append("ads_colon_truncation")

    if reserved_hit:
        return "WRITTEN_UNREADABLE", reasons, evidence
    if reasons:
        return "WRITTEN_TRUNCATED", reasons, evidence

    return "OK", [], []


def _judge_posix_like(name: str, components: list[str]) -> tuple[str, list[str], list[str]]:
    """macOS / Linux 侧：只判平台无关的三类（空/NUL/坏组件）。

    为什么不多判：`data/README.md` §4.2 只给了 Windows 的保留名与裁剪规则；macOS 的
    保留名（`:`）与 APFS 的折叠语义都缺少可用的平台表，用近似会违反决策 ③/④。
    所以这里**不猜**：只报跨平台都成立的"创建时即失败"，其余留 `OK`，并把
    `plan/05` §五 U2（macOS/Linux 未实测）作为已知边界带在报告外。
    """

    reasons: list[str] = []
    evidence: list[str] = []

    if name == "":
        reasons.append("empty_name")
        evidence.append("empty_component")

    if "\x00" in name:
        reasons.append("nul_byte")
        evidence.append("nul_byte")

    for component in components:
        if component == "":
            if "empty_component" not in reasons:
                reasons.append("empty_component")
                evidence.append("empty_component")
            continue
        if component in (".", ".."):
            if "dot_component" not in reasons:
                reasons.append("dot_component")
                evidence.append("dot_component")

    if reasons:
        return "BLOCKED", reasons, evidence
    return "OK", [], []


def judge_name(
    name: str,
    platform: str,
    tables: PlatformTables,
) -> dict:
    """单条目在单平台上的可访问性判定（`{"level", "reasons", "evidence"}`）。"""

    if platform not in PLATFORMS:
        raise AssertionError(f"未知目标平台: {platform}")  # pragma: no cover - cli 已校验

    components = _split_components(name)
    if platform == "windows":
        level, reasons, evidence = _judge_windows(name, components, tables)
    else:
        level, reasons, evidence = _judge_posix_like(name, components)

    assert level in LEVELS, level
    assert all(item in REASON_TOKENS for item in reasons), reasons
    assert all(item in EVIDENCE_TOKENS for item in evidence), evidence
    return {"level": level, "reasons": reasons, "evidence": evidence}


def _as_text(raw: bytes) -> str:
    """原始名字节 → 参与判定的字符串（`surrogateescape` 逐字节可逆，仅内部用）。"""

    return raw.decode("utf-8", "surrogateescape")


def check(
    archive: Archive,
    targets: tuple[str, ...] | list[str],
    tables: PlatformTables,
) -> dict[int, dict[str, dict]]:
    """MOD-4 的全部判定。

    返回 `{entry_index: {platform: {"level", "reasons", "evidence"}}}`——只对**本次 targets**
    里的平台出键，因此三个 `--target` 的结论能各自独立断言（`plan/HANDOFF-M4.md` §3 第 5 条）。
    """

    unknown = [name for name in targets if name not in PLATFORMS]
    if unknown:
        raise AssertionError(f"未知目标平台: {unknown}")  # pragma: no cover - cli 已校验

    verdicts: dict[int, dict[str, dict]] = {}
    for entry in archive.entries:
        name = _as_text(entry.cd_name)
        per_platform: dict[str, dict] = {}
        for platform in PLATFORMS:
            if platform not in targets:
                continue
            per_platform[platform] = judge_name(name, platform, tables)
        verdicts[entry.index] = per_platform
    return verdicts


def count_issues(verdicts: dict[int, dict[str, dict]]) -> int:
    """非 `OK` 的 (条目, 平台) 对数——`check` 退码 `1` 的判据之一（`data/README.md` §4.1）。"""

    return sum(
        1
        for per_platform in verdicts.values()
        for verdict in per_platform.values()
        if verdict["level"] != "OK"
    )


__all__ = [
    "EVIDENCE_TOKENS",
    "GRADES",
    "LEVELS",
    "PLATFORMS",
    "REASON_TOKENS",
    "RESERVED_DEVICE_NAMES",
    "RESERVED_EVIDENCE",
    "WINDOWS_ILLEGAL",
    "WINDOWS_MAX_COMPONENT",
    "WINDOWS_TRAILING_CHARS",
    "check",
    "count_issues",
    "judge_name",
]
