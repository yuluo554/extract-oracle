#!/usr/bin/env python3
"""fixture 生成器：全部样本由 `struct.pack` 直接拼字节，零网络、零第三方库。

纪律（`data/README.md` §3.1）：
- 不调用任何压缩库写归档；payload 一律固定 ASCII 短语；
- DOS 时间字段固定为 `1980-01-01 00:00`，同一命令重复运行产物逐字节一致；
- `--check` 把产物重新生成到临时目录并与入仓文件逐字节比对（**两层**：盘上产物形态 + 重生成一致）。

骨架期（M0）只实现四个 fixture；M1 按 `data/README.md` §3.2 补齐其余样本与真值。
未实现的样本在 `PENDING` 里显式登记，`--check` 会打印"待 M1 落地"而不是假装通过。
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

FIXED_DOS_TIME = 0x0000  # 1980-01-01 00:00:00（DOS date/time = 0 即该时刻）
FIXED_DOS_DATE = 0x0021  # 1980-01-01

LFH_SIG = 0x04034B50
CD_SIG = 0x02014B50
EOCD_SIG = 0x06054B50


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
    import zlib

    return zlib.crc32(data) & 0xFFFFFFFF


def build_zip(
    entries: list[Entry],
    *,
    declared_entries: int | None = None,
    cd_override: list[tuple[int, int]] | None = None,
) -> bytes:
    """按 APPNOTE 布局拼出归档字节（仅 stored，无压缩，无 data descriptor）。

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


#: 骨架期已实现的 fixture → 构造函数。
BUILDERS = {
    "clean.zip": fixture_clean,
    "mismatch_name.zip": fixture_mismatch_name,
    "case.zip": fixture_case,
    "norm.zip": fixture_norm,
    "reserved.zip": fixture_reserved,
    "trailing.zip": fixture_trailing,
}

#: M1 待落地的 fixture（显式登记，`--check` 会打印，不假装通过）。
PENDING = [
    "alias_lfh.zip",
    "overlap.zip",
    "wrong_count.zip",
    "crc_diverge.zip",
    "size_diverge.zip",
    "zh_gbk.zip",
    "upath.zip",
    "upath_badcrc.zip",
    "trim.zip",
    "filedir.zip",
    "not_first.epub",
    "compressed.epub",
    "extra.epub",
    "padding.epub",
    "long_path.zip",
    "long_comp.zip",
]

#: 真值（输入 + 期望，不含任何 observed_* 字段；`data/README.md` §3.1）。
TRUTH = {
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
            "windows": {"CON.txt": "WRITTEN_UNREADABLE", "NUL.txt": "WRITTEN_UNREADABLE", "aux.tar.gz": "WRITTEN_UNREADABLE"},
            "linux": {},
            "macos": {},
        },
    },
    "trailing.zip": {
        "expected_findings": [],
        "expected_accessibility": {
            "windows": {
                "trailing. ": "WRITTEN_TRUNCATED",
                "trailingdot.": "WRITTEN_TRUNCATED",
                "colon:name.txt": "BLOCKED",
            },
            "linux": {},
            "macos": {},
        },
    },
}


def generate() -> dict[str, bytes]:
    """生成全部 fixture 字节（返回内存结果，写盘由调用方决定）。"""

    return {name: builder() for name, builder in BUILDERS.items()}


def write_all(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    truth_dir = out_dir / "truth"
    truth_dir.mkdir(parents=True, exist_ok=True)
    for name, data in generate().items():
        (out_dir / name).write_bytes(data)
        truth = {"fixture": name, **TRUTH[name]}
        (truth_dir / f"{name}.json").write_text(
            json.dumps(truth, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )


def check(out_dir: Path) -> int:
    """两层断言：① 盘上产物与内存重生成逐字节一致；② 真值文件成对存在。"""

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
    extra = sorted(p.name for p in out_dir.glob("*.zip") if p.name not in generated)
    for name in extra:
        problems.append(f"孤儿产物（无生成器认领）: {name}")

    print(f"生成器自检：已实现 {len(generated)} 份，待 M1 落地 {len(PENDING)} 份")
    if problems:
        for item in problems:
            print(f"FAIL  {item}")
        return 1
    print("OK  重生成结果与盘上产物逐字节一致；真值成对")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gen_fixtures", description="程序化合成 fixture（零网络）")
    parser.add_argument("--out", type=Path, default=Path("data/fixtures"))
    parser.add_argument("--check", action="store_true", help="只校验，不写盘")
    args = parser.parse_args(argv)

    if args.check:
        return check(args.out)
    write_all(args.out)
    print(f"已生成 {len(BUILDERS)} 份 fixture → {args.out}（待 M1 落地 {len(PENDING)} 份）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
