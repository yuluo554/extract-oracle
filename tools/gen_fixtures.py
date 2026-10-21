#!/usr/bin/env python3
"""fixture 生成器：全部样本由 `struct.pack` 直接拼字节，零网络、零第三方库。

纪律（`data/README.md` §3.1）：
- 不调用任何压缩库写归档；payload 一律固定 ASCII 短语；需要 deflate 时只用
  `zlib.compressobj(level=..., wbits=-15)` 取裸压缩流字节（不调 `zipfile` 写）；
- DOS 时间字段固定为 `1980-01-01 00:00`，同一命令重复运行产物逐字节一致；
- `--check` 把产物重新生成到临时目录并与入仓文件逐字节比对（**两层**：盘上产物形态 + 重生成一致）。

K06：**新样本一律追加在 `BUILDERS` 末尾**，既有样本的字节与顺序不动
（既有顺序参与确定性序列，中途插入会污染 diff）。
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
import zlib
from dataclasses import dataclass
from pathlib import Path

FIXED_DOS_TIME = 0x0000  # 1980-01-01 00:00:00（DOS date/time = 0 即该时刻）
FIXED_DOS_DATE = 0x0021  # 1980-01-01

LFH_SIG = 0x04034B50
CD_SIG = 0x02014B50
EOCD_SIG = 0x06054B50

#: general purpose flag bit 11：名字为 UTF-8（APPNOTE 6.3.10 D.1）
FLAG_UTF8 = 0x0800

#: Info-ZIP Unicode Path extra field（APPNOTE 6.3.10 D.6）
UPATH_ID = 0x7075


@dataclass
class Entry:
    """一个条目。`lfh_name` / `cd_name` 分开给，才能构造双头不一致。"""

    name: bytes
    payload: bytes
    lfh_name: bytes | None = None
    cd_name: bytes | None = None
    flags: int = 0
    lfh_flags: int | None = None
    cd_flags: int | None = None
    cd_extra: bytes = b""
    lfh_extra: bytes = b""
    method: int = 0
    crc: int = 0
    comp_size: int | None = None
    uncomp_size: int | None = None
    lfh_offset: int | None = None


def _crc32(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF


def _deflate_raw(data: bytes, level: int = 6) -> bytes:
    """裸 deflate 流（无 zlib 头尾）。只用 `zlib` 取压缩字节，不写归档。"""

    obj = zlib.compressobj(level, zlib.DEFLATED, -15)
    return obj.compress(data) + obj.flush()


def _upath_extra(raw_name: bytes, unicode_name: bytes, *, crc_override: int | None = None) -> bytes:
    """拼 0x7075 Unicode Path extra：`id(2) size(2) version(1) name_crc32(4) utf8_name`。"""

    body = struct.pack("<B", 1) + struct.pack("<I", crc_override if crc_override is not None else _crc32(raw_name))
    body += unicode_name
    return struct.pack("<HH", UPATH_ID, len(body)) + body


def build_zip(
    entries: list[Entry],
    *,
    declared_entries: int | None = None,
    cd_override: list[tuple[int, int]] | None = None,
) -> bytes:
    """按 APPNOTE 布局拼出归档字节（stored 或 deflate，无 data descriptor）。

    `cd_override` 可在写 CD 时逐条替换 `(crc, uncompressed_size)`，用于构造 CRC/SIZE 反差。
    """

    out = bytearray()
    for entry in entries:
        lfh_name = entry.lfh_name if entry.lfh_name is not None else entry.name
        lfh_flags = entry.lfh_flags if entry.lfh_flags is not None else entry.flags
        payload = entry.payload
        crc = entry.crc or _crc32(payload)
        comp_size = entry.comp_size if entry.comp_size is not None else len(payload)
        uncomp_size = entry.uncomp_size if entry.uncomp_size is not None else len(payload)
        entry.lfh_offset = len(out)
        out += struct.pack(
            "<IHHHHHIIIHH",
            LFH_SIG,
            20,
            lfh_flags,
            entry.method,
            FIXED_DOS_TIME,
            FIXED_DOS_DATE,
            crc,
            comp_size,
            uncomp_size,
            len(lfh_name),
            len(entry.lfh_extra),
        )
        out += lfh_name
        out += entry.lfh_extra
        out += payload

    cd_start = len(out)
    cd_count = 0
    for index, entry in enumerate(entries):
        cd_name = entry.cd_name if entry.cd_name is not None else entry.name
        cd_flags = entry.cd_flags if entry.cd_flags is not None else entry.flags
        payload = entry.payload
        crc = entry.crc or _crc32(payload)
        comp_size = entry.comp_size if entry.comp_size is not None else len(payload)
        uncomp_size = entry.uncomp_size if entry.uncomp_size is not None else len(payload)
        if cd_override and index < len(cd_override):
            crc, uncomp_size = cd_override[index]
        offset = entry.lfh_offset if entry.lfh_offset is not None else 0
        out += struct.pack(
            "<IHHHHHHIIIHHHHHII",
            CD_SIG,
            20,
            20,
            cd_flags,
            entry.method,
            FIXED_DOS_TIME,
            FIXED_DOS_DATE,
            crc,
            comp_size,
            uncomp_size,
            len(cd_name),
            len(entry.cd_extra),
            0,
            0,
            0,
            0,
            offset,
        )
        out += cd_name
        out += entry.cd_extra
        cd_count += 1

    cd_size = len(out) - cd_start
    total = declared_entries if declared_entries is not None else cd_count
    out += struct.pack("<IHHHHIIH", EOCD_SIG, 0, 0, total, total, cd_size, cd_start, 0)
    return bytes(out)


# ---------------------------------------------------------------- 既有 6 份（M0）


def _nfkc_cafe_nfc() -> bytes:
    return "caf\u00e9.txt".encode("utf-8")


def _cafe_nfd() -> bytes:
    return "cafe\u0301.txt".encode("utf-8")


def fixture_clean() -> bytes:
    """零误报基线：两个正常条目。"""

    return build_zip(
        [
            Entry("alpha.txt".encode("ascii"), b"PAYLOAD-A\n"),
            Entry("beta.txt".encode("ascii"), b"PAYLOAD-B\n"),
        ]
    )


def fixture_mismatch_name() -> bytes:
    """LFH 名 `allowed.txt` / CD 名 `evil.txt`（等长，便于字节级定位）。"""

    return build_zip(
        [
            Entry(
                b"allowed.txt",
                b"PAYLOAD-A\n",
                lfh_name=b"allowed.txt",
                cd_name=b"evil.txt",
            )
        ]
    )


def fixture_case() -> bytes:
    """仅大小写不同：`Readme.txt`(UPPER) + `README.TXT`(LOWER)。"""

    return build_zip(
        [
            Entry(b"Readme.txt", b"UPPER\n"),
            Entry(b"README.TXT", b"LOWER\n"),
        ]
    )


def fixture_norm() -> bytes:
    """NFC `café.txt` + NFD `café.txt`（不同归一形、不同字节）。"""

    return build_zip([Entry(_nfkc_cafe_nfc(), b"PAYLOAD-NFC\n"), Entry(_cafe_nfd(), b"PAYLOAD-NFD\n")])


def fixture_reserved() -> bytes:
    """Windows 保留设备名（含带扩展名形式）。"""

    return build_zip(
        [
            Entry(b"CON.txt", b"PAYLOAD-CON\n"),
            Entry(b"NUL.txt", b"PAYLOAD-NUL\n"),
            Entry(b"aux.tar.gz", b"PAYLOAD-AUX\n"),
        ]
    )


def fixture_trailing() -> bytes:
    """尾随点/空格与冒号。"""

    return build_zip(
        [
            Entry(b"trailing. ", b"PAYLOAD-T1\n"),
            Entry(b"trailingdot.", b"PAYLOAD-T2\n"),
            Entry(b"colon:name.txt", b"PAYLOAD-T3\n"),
        ]
    )


# ---------------------------------------------------------------- M1 新增 16 份


def _lfh_record(name: bytes, payload: bytes, *, flags: int = 0) -> bytes:
    """只拼 LFH 头 + 名字（不含 payload），供需要精确摆放偏移的构造使用。"""

    return struct.pack(
        "<IHHHHHIIIHH",
        LFH_SIG,
        20,
        flags,
        0,
        FIXED_DOS_TIME,
        FIXED_DOS_DATE,
        _crc32(payload),
        len(payload),
        len(payload),
        len(name),
        0,
    ) + name


def fixture_alias_lfh() -> bytes:
    """名字一致，LFH 与 CD 的 general purpose flag 不同（LFH 无 bit11，CD 有）。

    `structure.FLAG_DIVERGES` 判的是 16 位全量比较，所以差异位就是 bit 11 本身。
    """

    return build_zip(
        [
            Entry(
                "same.txt".encode("ascii"),
                b"PAYLOAD-A\n",
                lfh_flags=0x0000,
                cd_flags=FLAG_UTF8,
            )
        ]
    )


def fixture_overlap() -> bytes:
    """两个条目的 LFH 记录区间物理相交（`a.txt` 的数据区里嵌着 `b.txt` 的整条 LFH）。

    构造手法：`a.txt` 的 payload 恰好等于 `b.txt` 的 `LFH + name + payload`，
    于是 CD 里 `b.txt` 的 `relative_offset` 落在 `a.txt` 的数据区内。
    **两侧字节各自自洽**（CRC、size 都对），因此只应命中 `LFH_OVERLAP`，不夹带 CRC/SIZE 反差。
    本机实测：Python `zipfile` 现在接受它（3.12 的 overlapped 检查要求真正的时间/大小异常）；
    `unzip` / `7-Zip` / `bsdtar` 均正常解出两个文件。
    """

    a_name = b"a.txt"
    b_name = b"b.txt"
    b_payload = b"PAYLOAD-B\n"
    b_record = _lfh_record(b_name, b_payload) + b_payload
    a_payload = b_record
    a_record = _lfh_record(a_name, a_payload) + a_payload
    a_offset = 0
    b_offset = len(_lfh_record(a_name, a_payload))
    out = bytearray(a_record)

    cd_start = len(out)
    for offset, name, payload in ((a_offset, a_name, a_payload), (b_offset, b_name, b_payload)):
        out += struct.pack(
            "<IHHHHHHIIIHHHHHII",
            CD_SIG,
            20,
            20,
            0,
            0,
            FIXED_DOS_TIME,
            FIXED_DOS_DATE,
            _crc32(payload),
            len(payload),
            len(payload),
            len(name),
            0,
            0,
            0,
            0,
            0,
            offset,
        )
        out += name
    out += struct.pack("<IHHHHIIH", EOCD_SIG, 0, 0, 2, 2, len(out) - cd_start, cd_start, 0)
    return bytes(out)


def fixture_wrong_count() -> bytes:
    """EOCD 声明 5 个条目，实际 CD 只有 2 个。"""

    return build_zip(
        [
            Entry(b"alpha.txt", b"PAYLOAD-A\n"),
            Entry(b"beta.txt", b"PAYLOAD-B\n"),
        ],
        declared_entries=5,
    )


def fixture_crc_diverge() -> bytes:
    """LFH 与 CD 的 CRC32 不同（CD 的 CRC 被改写一个位）。"""

    payload = b"PAYLOAD-A\n"
    return build_zip([Entry(b"crc.txt", payload)], cd_override=[(_crc32(payload) ^ 0x00000001, len(payload))])


def fixture_size_diverge() -> bytes:
    """LFH 与 CD 的 uncompressed size 不同（CD 多 7 字节）。"""

    payload = b"PAYLOAD-A\n"
    return build_zip([Entry(b"size.txt", payload)], cd_override=[(_crc32(payload), len(payload) + 7)])


def fixture_zh_gbk() -> bytes:
    """无 bit11，名字是 GBK 编码的 `中文名.txt`（CP437 下会解成乱码）。"""

    return build_zip([Entry("中文名.txt".encode("gbk"), b"PAYLOAD-ZH\n", flags=0x0000)])


def fixture_upath() -> bytes:
    """无 bit11，原名字节是 **GBK** 的 `中文名.txt`，另带 0x7075 指向 `café.txt`。

    0x7075 的 CRC 按**原名字节**算（APPNOTE 6.3.10 D.6），因此覆盖有效。
    本机四工具实测一致：全部写出 `café.txt`（0x7075 压过 CP437/GBK 猜测）。
    """

    raw = "中文名.txt".encode("gbk")
    extra = _upath_extra(raw, "caf\u00e9.txt".encode("utf-8"))
    return build_zip([Entry(raw, b"PAYLOAD-UP\n", lfh_extra=extra, cd_extra=extra)])


def fixture_upath_badcrc() -> bytes:
    """同上，但 0x7075 的 CRC 字段被取反 → 覆盖失效、降级 `low`。

    本机四工具实测**四方分歧**：Python `zipfile` 出 `╓╨╬─├√.txt`（CP437）、
    Info-ZIP 出 `Íð+-+¹.txt`（CP437 + 非法字符替换）、7-Zip 与 libarchive 出 `中文名.txt`（GBK）。
    """

    raw = "中文名.txt".encode("gbk")
    extra = _upath_extra(raw, "caf\u00e9.txt".encode("utf-8"), crc_override=_crc32(raw) ^ 0xFFFFFFFF)
    return build_zip([Entry(raw, b"PAYLOAD-UPB\n", lfh_extra=extra, cd_extra=extra)])


def fixture_trim() -> bytes:
    """`readme.` + `readme`：尾随点裁剪后相撞。"""

    return build_zip([Entry(b"readme.", b"PAYLOAD-DOT\n"), Entry(b"readme", b"PAYLOAD-PLAIN\n")])


def fixture_filedir() -> bytes:
    """同一路径既是文件又要求当目录：`a` 与 `a/b`。"""

    return build_zip([Entry(b"a", b"PAYLOAD-FILE\n"), Entry(b"a/b", b"PAYLOAD-NEST\n")])


def _epub_entries(mimetype: Entry) -> list[Entry]:
    """`META-INF/container.xml` 保证容器可识别；`mimetype` 的位置/形态由调用方决定。"""

    container = Entry(
        b"META-INF/container.xml",
        b'<?xml version="1.0"?><container version="1.0"/>\n',
        flags=FLAG_UTF8,
    )
    content = Entry(b"OEBPS/content.xhtml", b"<html><body>PAYLOAD</body></html>\n", flags=FLAG_UTF8)
    return [mimetype, container, content]


def _mimetype_entry(*, method: int = 0, extra: bytes = b"", content: bytes = b"application/epub+zip") -> Entry:
    """`mimetype` 条目。**CRC 恒按未压缩内容算**（APPNOTE：CRC32 是解压后字节的校验）。"""

    payload = _deflate_raw(content) if method == 8 else content
    return Entry(
        b"mimetype",
        payload,
        flags=FLAG_UTF8,
        method=method,
        crc=_crc32(content),
        comp_size=len(payload),
        uncomp_size=len(content),
        lfh_extra=extra,
        cd_extra=extra,
    )


def fixture_not_first_epub() -> bytes:
    """`mimetype` 不是首个条目（container.xml 在前）。"""

    container = Entry(
        b"META-INF/container.xml",
        b'<?xml version="1.0"?><container version="1.0"/>\n',
        flags=FLAG_UTF8,
    )
    return build_zip([container, _mimetype_entry()])


def fixture_compressed_epub() -> bytes:
    """`mimetype` 被 deflate（method=8）。"""

    return build_zip(_epub_entries(_mimetype_entry(method=8)))


def fixture_extra_epub() -> bytes:
    """`mimetype` 带一个结构合法的 extra field。"""

    extra = struct.pack("<HH", 0xCAFE, 4) + b"ABCD"
    return build_zip(_epub_entries(_mimetype_entry(extra=extra)))


def fixture_padding_epub() -> bytes:
    """`mimetype` 内容带尾随换行（EPUB 3.3 §4.3.3 明文禁止）。"""

    return build_zip(_epub_entries(_mimetype_entry(content=b"application/epub+zip\n")))


def fixture_long_path() -> bytes:
    """解出的完整路径 > 260（7 段 × 44 字节 + 6 个分隔符 = 314）。"""

    part = b"d" * 44
    name = b"/".join([part] * 7)
    assert len(name) == 314
    return build_zip([Entry(name, b"PAYLOAD-LONG\n")])


def fixture_long_comp() -> bytes:
    """单个路径组件 > 255 字节（256 个 `x`）。"""

    name = b"x" * 256
    return build_zip([Entry(name, b"PAYLOAD-COMP\n")])


#: fixture → 构造函数。**顺序即确定性序列**；新样本只许追加（K06）。
BUILDERS = {
    # M0（6 份，字节与顺序冻结）
    "clean.zip": fixture_clean,
    "mismatch_name.zip": fixture_mismatch_name,
    "case.zip": fixture_case,
    "norm.zip": fixture_norm,
    "reserved.zip": fixture_reserved,
    "trailing.zip": fixture_trailing,
    # M1（16 份，追加在末尾）
    "alias_lfh.zip": fixture_alias_lfh,
    "overlap.zip": fixture_overlap,
    "wrong_count.zip": fixture_wrong_count,
    "crc_diverge.zip": fixture_crc_diverge,
    "size_diverge.zip": fixture_size_diverge,
    "zh_gbk.zip": fixture_zh_gbk,
    "upath.zip": fixture_upath,
    "upath_badcrc.zip": fixture_upath_badcrc,
    "trim.zip": fixture_trim,
    "filedir.zip": fixture_filedir,
    "not_first.epub": fixture_not_first_epub,
    "compressed.epub": fixture_compressed_epub,
    "extra.epub": fixture_extra_epub,
    "padding.epub": fixture_padding_epub,
    "long_path.zip": fixture_long_path,
    "long_comp.zip": fixture_long_comp,
}

#: M1 待落地的 fixture。M1 收尾时必须为空（`--check` 与本清单一致性断言）。
PENDING: list[str] = []

#: 真值（输入 + 期望，不含任何 `observed_*` 字段；`data/README.md` §3.1、K01）。
#:
#: 键集合受 `tests/test_fixtures.py::ALLOWED_TRUTH_KEYS` 白名单约束：
#: - `expected_findings`：期望的 ruleId 集合（空列表 = 必须一条都不报）；
#: - `expected_collisions`：按平台给出期望的折叠冲突；
#: - `expected_accessibility`：按平台给出期望的三级可访问性；
#: - `expected_names`：按提取器给出期望落盘名（`null` = 不可预测，须附 `reason`）；
#: - `expected_encoding`：编码候选与 0x7075 的期望；
#: - `note`：口径说明（只解释期望，不承载观测值）。
TRUTH: dict[str, dict] = {
    "clean.zip": {"expected_findings": []},
    "mismatch_name.zip": {"expected_findings": ["structure.NAME_DIVERGES"]},
    "case.zip": {
        "expected_findings": [],
        "expected_collisions": {
            "windows": [{"code": "collision.CASEFOLD", "survivor": "README.TXT"}],
            "macos": [],
            "linux": [],
        },
    },
    "norm.zip": {
        "expected_findings": [],
        "expected_collisions": {
            "windows": [],
            "macos": [{"code": "collision.NFC"}],
            "linux": [],
        },
    },
    "reserved.zip": {
        "expected_findings": [],
        "expected_accessibility": {
            "windows": {
                "CON.txt": "WRITTEN_UNREADABLE",
                "NUL.txt": "WRITTEN_UNREADABLE",
                "aux.tar.gz": "OK",
            },
            "linux": {},
            "macos": {},
        },
        "note": "保留名按「最后一个点之前」整体匹配：`CON.txt`/`NUL.txt` 不可读，"
        "而 `aux.tar.gz` 的最后一段是 `gz`、`aux.tar` 不是保留名 → **真可读**（本机 PowerShell `Test-Path`=True）。"
        "初版 §4.2 的「含扩展名即保留」被本条实测否掉（`plan/05` §五 U11）",
    },
    "trailing.zip": {
        "expected_findings": [],
        "expected_accessibility": {
            "windows": {
                "trailing. ": "WRITTEN_TRUNCATED",
                "trailingdot.": "WRITTEN_TRUNCATED",
                "colon:name.txt": "WRITTEN_TRUNCATED",
            },
            "linux": {},
            "macos": {},
        },
        "note": "`trailing. `/`trailingdot.` 被裁掉尾随点+空格存成 `trailing`/`trailingdot`；"
        "`colon:name.txt` **创建并不失败**——NTFS 按 ADS 语义只写冒号前的 `colon`（名字变了=TRUNCATED）。"
        "§4.2 初版把 `:` 归入 BLOCKED 是错的（`plan/05` §五 U11）",
    },
    "alias_lfh.zip": {
        "expected_findings": ["structure.FLAG_DIVERGES"],
        "note": "LFH flag=0x0000 / CD flag=0x0800，差异位为 bit 11",
    },
    "overlap.zip": {
        "expected_findings": ["structure.LFH_OVERLAP"],
        "note": "a.txt 的 payload 恰为 b.txt 的整条 LFH+name+payload，"
        "CD 里 b.txt 的 relative_offset=35 落在 a.txt 的数据区内（a 的记录区间 [0,86)）。"
        "两侧 CRC/size 各自自洽 → 不夹带 CRC/SIZE 反差。"
        "本机实测：Python `zipfile` 抛 `BadZipFile: Overlapped entries`；"
        "unzip/7-Zip/bsdtar 均 rc=0 正常解出两个文件 → 分歧方向是「一个拒绝、三个照解」",
    },
    "wrong_count.zip": {
        "expected_findings": ["structure.CD_COUNT_MISMATCH"],
        "note": "EOCD 声明 5 条，实际 CD 2 条",
    },
    "crc_diverge.zip": {
        "expected_findings": ["structure.CRC_DIVERGES"],
        "note": "CD 的 CRC 为 LFH 的 CRC 翻转最低位",
    },
    "size_diverge.zip": {
        "expected_findings": ["structure.SIZE_DIVERGES"],
        "note": "CD 的 uncompressed size 比 LFH 多 7",
    },
    "zh_gbk.zip": {
        "expected_findings": [],
        "expected_encoding": {
            "bit11": False,
            "preferred": "GBK",
            "decoded_expected": "中文名.txt",
            "candidates_include": ["CP437", "GBK"],
        },
        "note": "GBK 字节 d6d0 cec4 c3fb；CP437 下解为乱码，GBK 下得原名",
    },
    "upath.zip": {
        "expected_findings": [],
        "expected_encoding": {
            "bit11": False,
            "upath": {"present": True, "crc_valid": True, "utf8_name": "café.txt"},
            "confidence": "high",
        },
        "expected_names": {
            "python-zipfile": "café.txt",
            "info-zip-unzip": "café.txt",
            "7zip": "café.txt",
            "libarchive": "café.txt",
        },
        "note": "原名字节为 GBK 的 中文名.txt；0x7075 的 CRC 按原名字节校验通过 → 四工具一致写出 café.txt",
    },
    "upath_badcrc.zip": {
        "expected_findings": ["encoding.UPATH_CRC_MISMATCH"],
        "expected_encoding": {
            "bit11": False,
            "upath": {"present": True, "crc_valid": False},
            "confidence": "low",
        },
        "expected_names": {
            "python-zipfile": "╓╨╬─├√.txt",
            "info-zip-unzip": "Íð+-+¹.txt",
            "7zip": "中文名.txt",
            "libarchive": "中文名.txt",
        },
        "note": "0x7075 的 CRC 取反 → 覆盖失效并降级 low；四方分歧：CP437 两种 + GBK 两种",
    },
    "trim.zip": {
        "expected_findings": [],
        "expected_collisions": {
            "windows": [{"code": "collision.TRIM", "survivor": "readme"}],
            "macos": [],
            "linux": [],
        },
        "expected_accessibility": {
            "windows": {"readme.": "WRITTEN_TRUNCATED", "readme": "OK"},
            "linux": {},
            "macos": {},
        },
        "note": "`readme.` 裁剪为 `readme` 后与 `readme` 相撞；两条目 `survivor` 都是 `readme`。"
        "注意：`unzip` 用 POSIX 语义真写出了 `readme.`（一个带点的独立文件），"
        "所以本条的 TRIM 是**Windows 目标**的折叠结论，不是 unzip 的落盘事实",
    },
    "filedir.zip": {
        "expected_findings": [],
        "expected_collisions": {
            "windows": [{"code": "collision.FILEDIR"}],
            "macos": [{"code": "collision.FILEDIR"}],
            "linux": [{"code": "collision.FILEDIR"}],
        },
        "note": "`a` 是文件而 `a/b` 要求 `a` 作目录。本机四工具实测**三个平台都表现为失败**"
        "（Python 抛 FileNotFoundError、unzip rc=2 'a exists but is not directory'、7-Zip rc=2、"
        "只有 bsdtar 把 `a` 转成目录再写 `a/b`）——所以 `collision.FILEDIR` 三平台都报，"
        "`plan` 初版只写 windows/macos 是按「大小写不敏感卷」推的，实测不成立",
    },
    "not_first.epub": {
        "expected_findings": ["container.MIMETYPE_NOT_FIRST"],
        "note": "META-INF/container.xml 排在 mimetype 之前",
    },
    "compressed.epub": {
        "expected_findings": ["container.MIMETYPE_COMPRESSED"],
        "note": "mimetype 用 method=8（deflate）",
    },
    "extra.epub": {
        "expected_findings": ["container.MIMETYPE_EXTRA"],
        "note": "mimetype 带 0xCAFE extra field",
    },
    "padding.epub": {
        "expected_findings": ["container.MIMETYPE_PADDING"],
        "note": "mimetype 内容为 `application/epub+zip\\n`（EPUB 3.3 §4.3.3 明文禁止）",
    },
    "long_path.zip": {
        "expected_findings": ["budget.PATH_OVER_260"],
        "expected_accessibility": {"windows": {}, "linux": {}, "macos": {}},
        "note": "整路径 314 字节（>260 含终止 NUL）；组件各 44 字节未超 255。"
        "本机 LongPathsEnabled=1 实测可直接创建（`plan/05` §五 U12），"
        "因此 `budget.PATH_OVER_260` 是**可移植性预算告警**，不是本机截断事实",
    },
    "long_comp.zip": {
        "expected_findings": ["budget.COMPONENT_OVER_255"],
        "expected_accessibility": {"windows": {"<long>": "BLOCKED"}, "linux": {}, "macos": {}},
        "note": "单组件 256 字节。本机实测 `CreateFileW` 直接失败（ERROR_INVALID_NAME 123），"
        "**加 `\\\\?\\` 前缀也一样**——所以按 §4.2「创建时即失败」判 `BLOCKED`，不是 `WRITTEN_TRUNCATED`。"
        "`plan/03` MOD-4 第 6 步把「组件超长」写成截断，M4 必须按本条实测裁决",
    },
}


def generate() -> dict[str, bytes]:
    """生成全部 fixture 字节（返回内存结果，写盘由调用方决定）。"""

    return {name: builder() for name, builder in BUILDERS.items()}


def _truth_payload(name: str) -> dict:
    return {"fixture": name, **TRUTH[name]}


def write_all(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    truth_dir = out_dir / "truth"
    truth_dir.mkdir(parents=True, exist_ok=True)
    for name, data in generate().items():
        (out_dir / name).write_bytes(data)
        truth_text = json.dumps(_truth_payload(name), ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        # 显式 LF 写盘、**Python 3.9 兼容**：`write_text(newline=…)` 是 3.10 才加的签名
        # （`tests/test_py39_compat.py` 守着这一类；K05 的逐字节一致依赖这里的 LF）。
        with open(truth_dir / f"{name}.json", "w", encoding="utf-8", newline="\n") as handle:
            handle.write(truth_text)


def check(out_dir: Path) -> int:
    """两层断言：① 盘上产物与内存重生成逐字节一致；② 真值文件成对且内容与生成器一致。"""

    problems: list[str] = []
    generated = generate()
    for name, data in generated.items():
        path = out_dir / name
        if not path.exists():
            problems.append(f"缺产物: {name}")
            continue
        if path.read_bytes() != data:
            problems.append(f"字节不一致（重生成 ≠ 盘上）: {name}")
        truth_path = out_dir / "truth" / f"{name}.json"
        if not truth_path.exists():
            problems.append(f"缺真值: truth/{name}.json")
            continue
        expected = json.loads(truth_path.read_text(encoding="utf-8"))
        if expected != _truth_payload(name):
            problems.append(f"真值与生成器不一致: truth/{name}.json（改了 fixture 必须同提交改真值）")

    extra = sorted(p.name for p in out_dir.glob("*.zip") if p.name not in generated)
    extra += sorted(p.name for p in out_dir.glob("*.epub") if p.name not in generated)
    for name in extra:
        problems.append(f"孤儿产物（无生成器认领）: {name}")

    orphan_truth = sorted(p.name for p in (out_dir / "truth").glob("*.json") if p.stem not in generated)
    for name in orphan_truth:
        problems.append(f"孤儿真值: truth/{name}")

    if PENDING:
        for name in PENDING:
            problems.append(f"待落地样本仍未实现: {name}")

    print(f"生成器自检：已实现 {len(generated)} 份，待落地 {len(PENDING)} 份")
    if problems:
        for item in problems:
            print(f"FAIL  {item}")
        return 1
    print("OK  重生成结果与盘上产物逐字节一致；真值成对且与生成器一致")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gen_fixtures", description="程序化合成 fixture（零网络）")
    parser.add_argument("--out", type=Path, default=Path("data/fixtures"))
    parser.add_argument("--check", action="store_true", help="只校验，不写盘")
    args = parser.parse_args(argv)

    if args.check:
        return check(args.out)
    write_all(args.out)
    print(f"已生成 {len(BUILDERS)} 份 fixture → {args.out}（待落地 {len(PENDING)} 份）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
