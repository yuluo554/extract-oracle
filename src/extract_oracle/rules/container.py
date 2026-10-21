"""MOD-5 容器约定（`container.*` 五条，`plan/03` §MOD-5、`data/README.md` §4.5）。

**五条规则，零解压到磁盘**：`mimetype` 的内容按 `method` 在内存里取（`stored` 直接切片，
`deflate` 用 `zlib.decompressobj(-15)` 只取那一段流）；不落盘、不调用 `zipfile`。

| `ruleId` | 判定 | 依据（`docs/rules.md` #） |
|---|---|---|
| `container.MIMETYPE_NOT_FIRST` | `mimetype` 不是 CD 首条目 | 11,13 |
| `container.MIMETYPE_COMPRESSED` | `mimetype` 的 method ≠ 0，或有加密位 | 11,13 |
| `container.MIMETYPE_EXTRA` | `mimetype` 带 extra field | 11,13 |
| `container.MIMETYPE_PADDING` | `mimetype` 内容前后有空白/padding | 11（EPUB）/ 14（ODF，`inferred`） |
| `container.UTF8_REQUIRED` | 容器要求 UTF-8 但 bit 11 未置位 | 12 |

**容器识别**（`plan/03` §MOD-5）：`mimetype` 条目存在 **且**（`META-INF/container.xml` 存在
**或** `mimetype` 内容为 `application/epub+zip` / `application/vnd.oasis.opendocument.*`）。
识别不出 → **不做容器检查**，不猜。这条是零误报的关键：普通 ZIP 没有 `mimetype`，
所以五条一条都不会触发（`clean.zip` 基线）。

**`inferred` 标注**：`MIMETYPE_PADDING` 在 ODF 上下文里 `evidence.inferred = true`——ODF 原文
（ODF 1.2 part 3 §3.3）**没有**明文禁止尾随换行，该结论是从 media-type 相等约束推出来的
（`docs/rules.md` #14、`data/README.md` §4.7 的 `inferred`）。EPUB 上下文里这条是原文明文
（"MUST NOT contain any leading or trailing padding or whitespace"），所以 `inferred = false`。

纯函数：`(Archive) -> tuple[Finding, ...]`。不写盘、不联网、不 import 其他判定模块（K10）。
"""

from __future__ import annotations

import zlib

from ..findings import Finding, display_name, sort_findings
from ..zip_reader import Archive, EntryView

#: 五条 `container.*`（顺序即判定顺序，也是报告里的固定枚举）。
CONTAINER_CODES: tuple[str, ...] = (
    "container.MIMETYPE_NOT_FIRST",
    "container.MIMETYPE_COMPRESSED",
    "container.MIMETYPE_EXTRA",
    "container.MIMETYPE_PADDING",
    "container.UTF8_REQUIRED",
)

#: `precedent` 的合法取值（实现选择/规范原句枚举；`docs/rules.md` §二 逐规则）。
PRECEDENTS: tuple[str, ...] = (
    "epub_ocf_zip_requirements",
    "odf_package_requirements",
    "odf_padding_inferred",  # 唯一不引原句的一条：从 media-type 相等约束推出
    "epub_ocf_utf8_names",
)

#: 容器类型（报告里给 `container.kind` 用）。
KINDS: tuple[str, ...] = ("epub", "odf", "none")

MIMETYPE_NAME = "mimetype"
CONTAINER_XML_NAME = "META-INF/container.xml"

#: 已核对的 media type 前缀（`data/README.md` §3.2 的四个 mimetype fixture + ODF）。
EPUB_MEDIA_TYPE = "application/epub+zip"
ODF_MEDIA_TYPE_PREFIX = "application/vnd.oasis.opendocument."

#: method 0 = stored（唯一被 EPUB/ODF 接受的 `mimetype` 形态）。
METHOD_STORED = 0
METHOD_DEFLATE = 8

#: CD `general purpose flag` bit 0 = 加密。
FLAG_ENCRYPTED = 0x0001
#: bit 11 = 名字为 UTF-8。
FLAG_UTF8 = 0x0800

#: `mimetype` 的内容上限（防御性：标准内容约 20–60 字节；超过 4 KiB 视为"无法按容器约定判"）。
MAX_MIMETYPE_BYTES = 4096


def _decode(raw: bytes) -> str:
    """CD 名 → 判定用字符串（`surrogateescape` 逐字节可逆，仅内部用；展示形另走 `display_name`）。"""

    return raw.decode("utf-8", "surrogateescape")


def _entry_name(entry: EntryView) -> str:
    return _decode(entry.cd_name)


def find_mimetype(archive: Archive) -> EntryView | None:
    """`mimetype` 条目（**按 CD 名逐字节比较**，CD 顺序取第一条）。"""

    return next((entry for entry in archive.entries if entry.cd_name == MIMETYPE_NAME.encode("ascii")), None)


def read_mimetype_bytes(archive: Archive, entry: EntryView) -> bytes | None:
    """在内存里取 `mimetype` 的**未压缩**内容。取不到返回 `None`（不猜、不落盘）。

    - `stored`：直接切片；
    - `deflate`：只解这一条流（`-15` = 裸 deflate，无 zlib 头尾）；
    - 其他 method / 加密 / 长度超预算：`None`（`MIMETYPE_COMPRESSED` 已经报了这一条）。
    """

    if archive.data == b"":
        return None
    if entry.method != METHOD_STORED or (entry.cd_flags & FLAG_ENCRYPTED):
        if entry.method != METHOD_DEFLATE or (entry.cd_flags & FLAG_ENCRYPTED):
            return None
        blob = archive.data[entry.data_offset : entry.data_offset + entry.cd_csize]
        try:
            text = zlib.decompressobj(-15).decompress(blob, MAX_MIMETYPE_BYTES + 1)
        except zlib.error:
            return None
        return text
    blob = archive.data[entry.data_offset : entry.data_offset + entry.cd_csize]
    return blob[: MAX_MIMETYPE_BYTES + 1]


def detect_kind(archive: Archive, mimetype: EntryView | None) -> str:
    """容器识别（`plan/03` §MOD-5）：`epub` / `odf` / `none`。识别不出 → 不做容器检查。"""

    if mimetype is None:
        return "none"
    has_container_xml = any(entry.cd_name == CONTAINER_XML_NAME.encode("ascii") for entry in archive.entries)
    content = read_mimetype_bytes(archive, mimetype)
    text = content.decode("utf-8", "surrogateescape") if content is not None else ""
    stripped = text.strip()
    if stripped == EPUB_MEDIA_TYPE:
        return "epub"
    if stripped.startswith(ODF_MEDIA_TYPE_PREFIX):
        return "odf"
    # 媒体类型读不出来时，`META-INF/container.xml` 是 EPUB 的结构标志（ODF 没有这个文件）。
    if has_container_xml:
        return "epub"
    return "none"


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


def check_not_first(archive: Archive, mimetype: EntryView) -> Finding | None:
    """`MIMETYPE_NOT_FIRST`：`mimetype` 的 `entry_index` 不是 0（CD 顺序里不是首条目）。"""

    if mimetype.index == 0:
        return None
    return _base(
        mimetype,
        "container.MIMETYPE_NOT_FIRST",
        "mimetype 不是归档的首个条目：OCF/ODF 要求它排第一，否则读取器要扫全表才能认容器",
        {
            "expectedIndex": 0,
            "actualIndex": mimetype.index,
            "firstEntryName": _entry_name(archive.entries[0]) if archive.entries else None,
        },
        "epub_ocf_zip_requirements",
    )


def check_compressed(mimetype: EntryView) -> Finding | None:
    """`MIMETYPE_COMPRESSED`：`mimetype` 的 method ≠ 0，或有加密位。"""

    encrypted = bool(mimetype.cd_flags & FLAG_ENCRYPTED)
    if mimetype.method == METHOD_STORED and not encrypted:
        return None
    return _base(
        mimetype,
        "container.MIMETYPE_COMPRESSED",
        "mimetype 被压缩或加密：容器约定要求它以 stored（method=0）且未加密的形态存在",
        {
            "method": mimetype.method,
            "expectedMethod": METHOD_STORED,
            "encrypted": encrypted,
            "cdFlags": mimetype.cd_flags,
        },
        "epub_ocf_zip_requirements",
    )


def check_extra(mimetype: EntryView) -> Finding | None:
    """`MIMETYPE_EXTRA`：`mimetype` 带任何 extra field（EPUB/ODF 都禁止）。"""

    ids = [item.field_id for item in mimetype.cd_extra]
    if not ids:
        return None
    return _base(
        mimetype,
        "container.MIMETYPE_EXTRA",
        "mimetype 带了 extra field：容器约定要求这个条目不带附加字段",
        {
            "extraIds": ids,
            "lfhExtraIds": [item.field_id for item in mimetype.lfh_extra],
        },
        "epub_ocf_zip_requirements",
    )


def check_padding(archive: Archive, mimetype: EntryView, kind: str) -> Finding | None:
    """`MIMETYPE_PADDING`：`mimetype` 内容前后有空白/padding。

    ODF 上下文里 `evidence.inferred = true`（原文未明文禁止，从 media-type 相等约束推出）。
    内容取不到时不报（**不猜**）：那种情形已经由 `MIMETYPE_COMPRESSED` 认领。
    """

    content = read_mimetype_bytes(archive, mimetype)
    if content is None:
        return None
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if text == text.strip():
        return None
    inferred = kind == "odf"
    return _base(
        mimetype,
        "container.MIMETYPE_PADDING",
        "mimetype 内容前后有空白/padding：容器约定要求内容恰为 media type 本身",
        {
            "leadingBytes": len(text) - len(text.lstrip()),
            "trailingBytes": len(text) - len(text.rstrip()),
            "contentLength": len(content),
            "inferred": inferred,
            "evidence_strength": "inferred" if inferred else "measured",
        },
        "odf_padding_inferred" if inferred else "epub_ocf_zip_requirements",
    )


def check_utf8(archive: Archive, mimetype: EntryView, kind: str) -> Finding | None:
    """`UTF8_REQUIRED`：容器要求文件名用 UTF-8，但 bit 11 未置位。

    判在**条目原名字节**上（结构事实），不问"内容能不能解"：EPUB 3.3 §4.3.2 的约束是
    编码声明（bit 11 = "MUST support UTF-8"），不是"恰好解得出 UTF-8"。

    两个"不报"的排除项都写在判据里（不是靠调用顺序碰巧）：

    - 只对**非纯 ASCII** 的名字报——纯 ASCII 在 UTF-8 与 CP437 下同形，报它等于假阳性；
    - 逐条目找**真正违规的那条**，不是"取第一条 bit 11 未置位的"（那条可能是纯 ASCII 的
      `mimetype`，于是整份归档漏报）。
    """

    if kind != "epub":
        return None
    offender = next(
        (
            entry
            for entry in archive.entries
            if not (entry.cd_flags & FLAG_UTF8)
            and any(byte >= 0x80 for byte in entry.cd_name)
        ),
        None,
    )
    if offender is None:
        return None
    raw = offender.cd_name
    return _base(
        offender,
        "container.UTF8_REQUIRED",
        "OCF 要求归档内文件名用 UTF-8，但该条目的 bit 11 未置位：读取器会按历史 CP437 解释它",
        {
            "bit11": bool(offender.cd_flags & FLAG_UTF8),
            "expectedBit11": True,
            "rawNameHex": raw.hex(),
            "container": kind,
        },
        "epub_ocf_utf8_names",
    )


def check(archive: Archive) -> tuple[tuple[Finding, ...], dict[str, str]]:
    """MOD-5 的容器判定：`(findings, {"kind": ...})`。

    `container.index` = 容器识别的结果（`epub` / `odf` / `none`），进 `summary` 的邻近块
    （`data/README.md` §4.13）。
    """

    mimetype = find_mimetype(archive)
    kind = detect_kind(archive, mimetype)
    if kind == "none":
        return (), {"kind": kind}

    found: list[Finding] = []
    for finding in (
        check_not_first(archive, mimetype),
        check_compressed(mimetype),
        check_extra(mimetype),
        check_padding(archive, mimetype, kind),
        check_utf8(archive, mimetype, kind),
    ):
        if finding is not None:
            found.append(finding)
    return sort_findings(found), {"kind": kind}


__all__ = [
    "CONTAINER_CODES",
    "CONTAINER_XML_NAME",
    "EPUB_MEDIA_TYPE",
    "FLAG_ENCRYPTED",
    "FLAG_UTF8",
    "KINDS",
    "MAX_MIMETYPE_BYTES",
    "MIMETYPE_NAME",
    "ODF_MEDIA_TYPE_PREFIX",
    "PRECEDENTS",
    "check",
    "check_compressed",
    "check_extra",
    "check_not_first",
    "check_padding",
    "check_utf8",
    "detect_kind",
    "find_mimetype",
    "read_mimetype_bytes",
]
