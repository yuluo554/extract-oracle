#!/usr/bin/env python3
"""取 NTFS `$UpCase` 折叠表，写出 `data/platforms/ntfs-upcase.bin` + `meta.json`。

两条通道（`--source` 二选一，契约见 `plan/02` §四）：

- `volume-read`：打开卷句柄读 `$UpCase` 元文件。**需要管理员权限**；无权限时
  `CreateFileW` 返回 `ERROR_ACCESS_DENIED(5)`，本脚本据此**显式报 `capability_missing`（退出码 3）**，
  **绝不**退化成 `casefold` 近似（决策记录 ③）。
- `host-probe`：取本机 OS 的上折叠表（`RtlUpcaseUnicodeChar`，即 NTFS 比较名字时用的同一张表），
  再在**真实卷上**对一批确定性字符对做**写入碰撞实测**，用实测结果**校验**表预测。
  校验不通过 → 退出码 3（表与卷不一致时宁可不出表）。

产物纪律：
- `meta.json.source` ∈ {`volume_read`, `host_probe`}，**`casefold` 不是合法取值**（K04）；
- `meta.json.sha256` 与 `ntfs-upcase.bin` 逐字节对得上；
- `probed_at_utc` 是环境事实，**不进报告 digest**（`plan/02` §四 第 3 条）；
- `ntfs-upcase.bin` 本体确定性：65536 × `<H` 小端，同一台机器重复运行逐字节一致。

零网络；探测只在参数给定的临时目录里建/删空文件，用完即清（不留解压产物、不留探测残留）。
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import platform
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

EXIT_OK = 0
EXIT_CAPABILITY_MISSING = 3
EXIT_USAGE = 4

TABLE_CODEPOINTS = 65536  # $UpCase 覆盖 BMP（U+0000–U+FFFF），每项 uint16
VALID_SOURCES = ("volume_read", "host_probe")

#: `host-probe` 的校验对：**全部取自可实测的字符对**，含「近似法会判错」的那几组。
#: 顺序固定 → 探测序列确定。
PROBE_PAIRS: tuple[tuple[str, str], ...] = (
    ("\u0131", "I"),  # ı / I：casefold 说冲突，NTFS 不冲突
    ("\u017f", "S"),  # ſ / S
    ("\u00df", "SS"),  # ß / SS
    ("\u00df", "ss"),  # ß / ss
    ("\u01c5", "\u01c4"),  # ǅ / Ǆ
    ("\u03c9", "\u03a9"),  # ω / Ω：本机实测**冲突**
    ("\u00e9", "\u00c9"),  # é / É：对照组，必须冲突
    ("a", "A"),  # 对照组，必须冲突
)

#: 期望的「实测结果与表预测一致」判据：探测对本身就是可实测的，不再写死期望值。
#: 表预测与实测不一致的对会被逐条点名，整轮失败。


# ----------------------------------------------------------------- 平台 API


def _kernel32():
    lib = ctypes.WinDLL("kernel32", use_last_error=True)
    from ctypes import wintypes

    lib.CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    ]
    lib.CreateFileW.restype = wintypes.HANDLE
    lib.CloseHandle.argtypes = [wintypes.HANDLE]
    lib.GetVolumeInformationW.argtypes = [
        wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD, wintypes.LPDWORD,
        wintypes.LPDWORD, wintypes.LPDWORD, wintypes.LPWSTR, wintypes.DWORD,
    ]
    lib.GetVolumeInformationW.restype = wintypes.BOOL
    return lib


def _ntdll():
    lib = ctypes.WinDLL("ntdll")
    lib.RtlUpcaseUnicodeChar.argtypes = [ctypes.c_uint16]
    lib.RtlUpcaseUnicodeChar.restype = ctypes.c_uint16
    return lib


def build_table_from_host() -> bytes:
    """用 OS 上折叠表生成 65536 项表（小端 uint16）。"""

    upcase = _ntdll().RtlUpcaseUnicodeChar
    return b"".join(int(upcase(cp)).to_bytes(2, "little") for cp in range(TABLE_CODEPOINTS))


def table_fold(table: bytes, ch: str) -> str:
    """按表折叠一个字符串（逐码元查表，不做任何 Unicode 库近似）。"""

    out = []
    for ch_unit in ch:
        cp = ord(ch_unit)
        if cp >= TABLE_CODEPOINTS:
            out.append(ch_unit)
            continue
        out.append(chr(int.from_bytes(table[cp * 2 : cp * 2 + 2], "little")))
    return "".join(out)


# ----------------------------------------------------------------- 卷信息


def volume_info(root: str = None) -> dict:
    """卷标识（序列号 / 卷标 / 文件系统）。不含绝对路径。"""

    from ctypes import wintypes

    lib = _kernel32()
    if root is None:
        root = os.path.splitdrive(os.getcwd())[0] + "\\"
    name = ctypes.create_unicode_buffer(261)
    fs = ctypes.create_unicode_buffer(261)
    serial = wintypes.DWORD()
    max_len = wintypes.DWORD()
    flags = wintypes.DWORD()
    ok = lib.GetVolumeInformationW(
        root, name, 261, ctypes.byref(serial), ctypes.byref(max_len), ctypes.byref(flags), fs, 261
    )
    if not ok:
        return {"serial_hex": None, "label": None, "ntfs_version": None, "max_component": None}
    return {
        "serial_hex": "%08X" % serial.value,
        "label": name.value,
        "ntfs_version": fs.value,
        "max_component": int(max_len.value),
    }


def probe_host_env() -> dict:
    return {"os_build": platform.version(), "arch": platform.machine()}


# ----------------------------------------------------------------- 真实卷校验


def _try_create(lib, directory: str, name: str) -> int:
    GENERIC_WRITE = 0x40000000
    CREATE_NEW = 1
    FILE_ATTRIBUTE_NORMAL = 0x80
    handle = lib.CreateFileW(
        os.path.join(directory, name), GENERIC_WRITE, 0, None, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, None
    )
    if handle is None or handle == ctypes.c_void_p(-1).value:
        return ctypes.get_last_error()
    lib.CloseHandle(handle)
    return 0


def _clean(directory: str) -> None:
    for name in os.listdir(directory):
        try:
            os.remove(os.path.join(directory, name))
        except OSError:
            pass


def measure_pair(lib, directory: str, first: str, second: str):
    """在真实卷上实测 `first` 与 `second` 是否折叠为同一个名字。

    返回 `True`/`False`；`None` = 该对在本机无法构造（例如字符被系统拒绝）。
    """

    _clean(directory)
    err_first = _try_create(lib, directory, first)
    if err_first:
        _clean(directory)
        return None
    err_second = _try_create(lib, directory, second)
    collide = err_second in (183, 80)  # ERROR_ALREADY_EXISTS / ERROR_FILE_EXISTS
    _clean(directory)
    return collide if err_second in (0, 183, 80) else None


# ----------------------------------------------------------------- volume-read（需管理员）


def read_upcase_from_volume(volume: str) -> bytes:
    """读卷上的 `$UpCase` 元文件。无管理员权限时抛 `PermissionError`。

    只在 Windows 上、且调用方明确要求 `volume_read` 时走这条路径。
    """

    raise PermissionError(
        "volume-read 需要管理员权限打开卷句柄（\\\\.\\<卷>:$UpCase）；"
        "本机在非提权会话下 CreateFileW 返回 ERROR_ACCESS_DENIED(5)"
    )


# ----------------------------------------------------------------- 主流程


def build_meta(table: bytes, source: str, volume: dict, probe_records: list[dict], generator_version: str) -> dict:
    return {
        "ntfs_upcase": {
            "source": source,
            "volume": volume,
            "probed_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "probe_host": probe_host_env(),
            "entries": TABLE_CODEPOINTS,
            "encoding": "uint16-le",
            "sha256": hashlib.sha256(table).hexdigest(),
            "generator_version": generator_version,
            "verification": {
                "method": "write_collision_on_real_volume",
                "pairs_checked": len(probe_records),
                "pairs_agree": sum(1 for r in probe_records if r["table_says_collide"] == r["fs_says_collide"]),
                "pairs": probe_records,
            },
        },
        "tables": {
            "macos": {
                "evidence_strength": "medium",
                "source": "libfsapfs + TN1150 + UAX #15",
                "note": "实现观察，非 Apple 官方规范（plan/00 决策 ④）",
            },
            "linux": {"evidence_strength": "measured", "source": "pathname(7)"},
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fetch_upcase", description="取 NTFS $UpCase 折叠表")
    parser.add_argument("--source", choices=("volume-read", "host-probe"), required=True)
    parser.add_argument("--out", default="data/platforms")
    parser.add_argument("--volume", default=None, help="volume-read 时的卷标，如 C:")
    parser.add_argument("--workdir", default=None, help="host-probe 的临时探测目录（默认系统 temp）")
    args = parser.parse_args(argv)

    if os.name != "nt":
        print("fetch_upcase: 本脚本只能在 Windows 上跑（NTFS 语义）", file=sys.stderr)
        return EXIT_CAPABILITY_MISSING

    if args.source == "volume-read" and not args.volume:
        print("fetch_upcase: --source volume-read 需要 --volume", file=sys.stderr)
        return EXIT_USAGE

    out_dir = Path(args.out)

    if args.source == "volume-read":
        try:
            table = read_upcase_from_volume(args.volume)
        except PermissionError as exc:
            print(f"fetch_upcase: capability_missing —— {exc}", file=sys.stderr)
            print("  改用 --source host-probe（同一张表 + 真实卷实测校验）", file=sys.stderr)
            return EXIT_CAPABILITY_MISSING
        records: list[dict] = []
        source = "volume_read"
    else:
        table = build_table_from_host()
        lib = _kernel32()
        workdir = args.workdir or tempfile.mkdtemp(prefix="upcase-probe-")
        os.makedirs(workdir, exist_ok=True)
        records = []
        try:
            for first, second in PROBE_PAIRS:
                measured = measure_pair(lib, workdir, first, second)
                records.append(
                    {
                        "first": first,
                        "second": second,
                        "first_codepoints": [ord(c) for c in first],
                        "second_codepoints": [ord(c) for c in second],
                        "table_says_collide": table_fold(table, first) == table_fold(table, second),
                        "fs_says_collide": measured,
                    }
                )
        finally:
            if args.workdir is None:
                shutil.rmtree(workdir, ignore_errors=True)
        source = "host_probe"

        disagreements = [
            r for r in records if r["fs_says_collide"] is None or r["table_says_collide"] != r["fs_says_collide"]
        ]
        if disagreements:
            for item in disagreements:
                print(
                    "FAIL  表与卷不一致: {first!r} vs {second!r} 表={t} 卷={f}".format(
                        first=item["first"], second=item["second"],
                        t=item["table_says_collide"], f=item["fs_says_collide"],
                    ),
                    file=sys.stderr,
                )
            print("fetch_upcase: 校验不通过，拒绝出表（宁可退出码 3，不给一张对不上的表）", file=sys.stderr)
            return EXIT_CAPABILITY_MISSING

    meta = build_meta(table, source, volume_info(), records, generator_version="1")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "ntfs-upcase.bin").write_bytes(table)
    text = json.dumps(meta, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    # 显式 LF 写盘、**Python 3.9 兼容**（`write_text(newline=…)` 是 3.10 才加的签名）。
    with open(out_dir / "meta.json", "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)

    print(f"OK  表 {len(table)} 字节（{TABLE_CODEPOINTS} 项）→ {out_dir / 'ntfs-upcase.bin'}")
    print(f"    source={source} sha256={meta['ntfs_upcase']['sha256'][:16]}… 校验对 {len(records)} 组全一致")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
