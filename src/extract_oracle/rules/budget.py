"""MOD-5 长度预算（`budget.*` 两条，`plan/03` §MOD-5、`data/README.md` §4.6）。

| `ruleId` | 判定 | 计量口径 |
|---|---|---|
| `budget.PATH_OVER_260` | Windows 目标下的整路径超预算 | **UTF-16 码元**（`win_max_path` = 260，含终止 NUL） |
| `budget.COMPONENT_OVER_255` | 单组件超限 | Windows：UTF-16 码元（`name_max_default` = 255）；Linux：**字节**（POSIX `{NAME_MAX}`） |

**`PATH_OVER_260` 是预算告警，不是"本机截断事实"**（`plan/05` §五 U12）：本机
`LongPathsEnabled=1` 时 314 字节的路径**可直接创建**。所以这条的 `evidence` 里显式带
`kind: "portability_budget"`，并且 `message` 不写"会被截断"——写"超出未开启长路径支持时的预算"。
`accessibility` 那一路（`rules/access.py`）对同一份样本仍判 `OK`，两者不打架：一个说
"目标平台能不能创建"，一个说"这份路径在默认设置下可不可移植"。

**按组件切的口径与 MOD-4 一致**（U19）：`/` 是分隔符，`a/b` 是两个组件。整路径长度按
**组件 + 分隔符**重新拼（不做任何规范化/裁剪——裁剪是 `accessibility`/`collision` 的事）。

**字节就按字节**（`plan/HANDOFF-M5.md` §2 第 14 条）：Linux 侧直接对原始名字节计数，
不中途 `encode()` 成 UTF-16；Windows 侧才按 UTF-16 码元（用 `surrogatepass`，理由同
`access.py::_utf16_units`）。

纯函数：`(Archive, targets, PlatformTables) -> tuple[Finding, ...]`。不写盘、不联网、
不 import 其他判定模块（K10）。
"""

from __future__ import annotations

from ..findings import Finding, display_name, sort_findings
from ..platforms import PlatformTables
from ..zip_reader import Archive, EntryView

#: 目标平台（与 `cli.TARGETS` 同序）。
PLATFORMS: tuple[str, ...] = ("windows", "macos", "linux")

#: 两条 `budget.*`（顺序即判定顺序）。
BUDGET_CODES: tuple[str, ...] = ("budget.PATH_OVER_260", "budget.COMPONENT_OVER_255")

#: `precedent` 的合法取值（`docs/rules.md` §二：`budget.PATH_OVER_260` = #1，
#: `budget.COMPONENT_OVER_255` = #1,#15）。
PRECEDENTS: tuple[str, ...] = (
    "ms_learn_max_path",  # MS Learn "the maximum length for a path is MAX_PATH … 260 characters"
    "posix_name_max_bytes",  # POSIX {NAME_MAX}：字节口径
)

#: `data/README.md` §4.6 的三个口径键（**本模块不另写数值**，常量只为引用方便）。
WIN_MAX_PATH = 260
LINUX_PATH_MAX = 4096
NAME_MAX_DEFAULT = 255

#: 长路径前缀下的上限（`data/README.md` §4.6：长路径前缀下 32767）。
WIN_MAX_PATH_EXTENDED = 32767

#: `evidence["kind"]` 的两种取值：预算告警 vs 本机实测的创建失败。
PATH_BUDGET_KIND = "portability_budget"

#: `/` 是分隔符（U19）。
SEPARATOR = "/"


def _utf16_units(text: str) -> int:
    """按 UTF-16 码元计长（Windows 口径；BMP 外算 2）。

    用 `surrogatepass`：判定用的名字可能来自 `surrogateescape`（非法字节 → 孤立代理项），
    默认编码会抛 `UnicodeEncodeError`。孤立代理项在 UTF-16 里恰占 1 个码元。
    """

    return len(text.encode("utf-16-le", "surrogatepass")) // 2


def _as_text(raw: bytes) -> str:
    """原始名字节 → 参与判定的字符串（`surrogateescape` 逐字节可逆，仅内部用）。"""

    return raw.decode("utf-8", "surrogateescape")


def components(name: str) -> list[str]:
    """按 `/` 切组件（与 `rules/access.py::_split_components` 同一口径，U19）。"""

    return name.split(SEPARATOR)


def byte_length(raw: bytes) -> int:
    """原始名字节的字节数（Linux `{NAME_MAX}` / `{PATH_MAX}` 的口径）。"""

    return len(raw)


def _base(entry: EntryView, rule_id: str, message: str, evidence: dict, precedent: str) -> Finding:
    return Finding(
        rule_id=rule_id,
        message=message,
        evidence=evidence,
        precedent=precedent,
        entry_index=entry.index,
        lfh_offset=entry.lfh_offset,
        cd_offset=entry.cd_offset,
        lfh_name=display_name(entry.lfh_name),
        cd_name=display_name(entry.cd_name),
    )


def check_path_windows(entry: EntryView) -> Finding | None:
    """`budget.PATH_OVER_260`（Windows）：整路径 UTF-16 码元数 + 终止 NUL > 260。

    计数 = 各组件码元数 + 分隔符数 + 1（终止 NUL）。**只是预算**：长路径前缀（`\\\\?\\`）下
    上限是 32767，而且本机 `LongPathsEnabled=1` 时可直接创建（U12）。所以 `evidence.kind`
    显式标 `portability_budget`，`message` 不说"会被截断"。
    """

    name = _as_text(entry.cd_name)
    parts = components(name)
    units = sum(_utf16_units(part) for part in parts) + max(len(parts) - 1, 0) + 1
    if units <= WIN_MAX_PATH:
        return None
    return _base(
        entry,
        "budget.PATH_OVER_260",
        "整路径超出默认 MAX_PATH 预算：未开启长路径支持的目标上不可移植"
        "（这是**预算告警**，不是本机能不能创建的结论——见 evidence.kind）",
        {
            "kind": PATH_BUDGET_KIND,
            "units": units,
            "limit": WIN_MAX_PATH,
            "extendedLimit": WIN_MAX_PATH_EXTENDED,
            "componentCount": len(parts),
            "longestComponentUnits": max((_utf16_units(part) for part in parts), default=0),
            "platform": "windows",
        },
        "ms_learn_max_path",
    )


def check_component_windows(entry: EntryView) -> Finding | None:
    """`budget.COMPONENT_OVER_255`（Windows）：任一组件 > 255 个 UTF-16 码元。"""

    name = _as_text(entry.cd_name)
    parts = components(name)
    over = [(index, len(part), _utf16_units(part)) for index, part in enumerate(parts)]
    over = [item for item in over if item[2] > NAME_MAX_DEFAULT]
    if not over:
        return None
    index, chars, units = over[0]
    return _base(
        entry,
        "budget.COMPONENT_OVER_255",
        "单个路径组件超出 255 个 UTF-16 码元：目标平台在创建时即失败",
        {
            "kind": "platform_limit",
            "limit": NAME_MAX_DEFAULT,
            "units": units,
            "characters": chars,
            "componentIndex": index,
            "violations": [
                {"componentIndex": item[0], "characters": item[1], "units": item[2]} for item in over
            ],
            "platform": "windows",
        },
        "ms_learn_max_path",
    )


def check_component_linux(entry: EntryView) -> Finding | None:
    """`budget.COMPONENT_OVER_255`（Linux）：任一组件 > 255 **字节**（POSIX `{NAME_MAX}`）。

    按原始名字节的字节切片算（**字节就按字节**，不 encode 成 UTF-16）：`/` 的字节是
    `0x2F`，按它切出来的片段长度就是该组件的字节数。
    """

    raw = entry.cd_name
    parts = raw.split(SEPARATOR.encode("ascii"))
    violations = [
        {"componentIndex": index, "bytes": byte_length(part)}
        for index, part in enumerate(parts)
        if byte_length(part) > NAME_MAX_DEFAULT
    ]
    if not violations:
        return None
    first = violations[0]
    return _base(
        entry,
        "budget.COMPONENT_OVER_255",
        "单个路径组件超出 255 字节：POSIX `{NAME_MAX}` 的上限，目标平台创建时即失败",
        {
            "kind": "platform_limit",
            "limit": NAME_MAX_DEFAULT,
            "bytes": first["bytes"],
            "componentIndex": first["componentIndex"],
            "violations": violations,
            "platform": "linux",
        },
        "posix_name_max_bytes",
    )


def check_path_linux(entry: EntryView) -> Finding | None:
    """`budget.PATH_OVER_260` 的 Linux 侧：整路径 > 4096 字节（`{PATH_MAX}`，不含终止 NUL）。

    同一份报告里两个平台的整路径上限不同，所以 `evidence.platform` 必带——否则读者会以为
    260 与 4096 是同一个口径。
    """

    raw = entry.cd_name
    size = byte_length(raw)
    if size <= LINUX_PATH_MAX:
        return None
    return _base(
        entry,
        "budget.PATH_OVER_260",
        "整路径超出 POSIX `{PATH_MAX}` 字节预算：目标平台创建时即失败",
        {
            "kind": "platform_limit",
            "bytes": size,
            "limit": LINUX_PATH_MAX,
            "platform": "linux",
        },
        "posix_name_max_bytes",
    )


def check(
    archive: Archive,
    targets: tuple[str, ...] | list[str],
    tables: PlatformTables,
) -> tuple[Finding, ...]:
    """MOD-5 的预算判定（`tables` 只为接口一致：预算不需要折叠表，`declared_platforms()` 说明这点）。"""

    unknown = [name for name in targets if name not in PLATFORMS]
    if unknown:
        raise AssertionError(f"未知目标平台: {unknown}")  # pragma: no cover - cli 已校验
    del tables  # 预算判定不查表（见 declared_platforms）

    found: list[Finding] = []
    for entry in archive.entries:
        if "windows" in targets:
            for finding in (check_path_windows(entry), check_component_windows(entry)):
                if finding is not None:
                    found.append(finding)
        if "linux" in targets:
            for finding in (check_path_linux(entry), check_component_linux(entry)):
                if finding is not None:
                    found.append(finding)
    return sort_findings(found)


def declared_platforms() -> tuple[str, ...]:
    """本模块**需要平台语义**的那几个目标——空元组 = 不读平台表。

    `cli.cmd_check` 的 `needs_tables` 靠这个值与 `rules/access.py::PLATFORMS` 合并判断，
    避免"为了跑预算去加载 `$UpCase` 表"这种无谓依赖（平台表缺失时预算仍然可判）。
    """

    return ()


__all__ = [
    "BUDGET_CODES",
    "LINUX_PATH_MAX",
    "NAME_MAX_DEFAULT",
    "PATH_BUDGET_KIND",
    "PLATFORMS",
    "PRECEDENTS",
    "SEPARATOR",
    "WIN_MAX_PATH",
    "WIN_MAX_PATH_EXTENDED",
    "byte_length",
    "check",
    "check_component_linux",
    "check_component_windows",
    "check_path_linux",
    "check_path_windows",
    "components",
    "declared_platforms",
]
