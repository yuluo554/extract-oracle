"""CLI 入口（唯一交付态入口）。

子命令：
- `inspect <archive>`：报 EOCD / CD / LFH 三层结构事实 + 名字层事实（**不是判定**，不产 `ruleId`）；
- `capabilities`：列出五模块落地状态；
- `platforms --verify`：平台表完整性占位（M3 实现真表后才有内容）；
- `check <archive> --target {windows,macos,linux}`：**判定入口**。判定层未就绪时按
  `data/README.md` §4.1 返回退出码 3（`capability_missing`），**绝不产出空 findings**。

退出码语义见 `data/README.md` §4.1；本模块不得硬编码整数，统一走 `ExitCode`。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from . import __version__
from .capabilities import MODULES, missing_core
from .errors import OracleError, ReasonCode
from .exit_codes import ExitCode
from .findings import display_name, sort_findings
from .report import SCHEMA_VERSION, dumps_json, render_text, write_atomic
from .rules import encoding as encoding_rules
from .rules import structure as structure_rules
from .zip_reader import Archive, read_archive

TARGETS = ("windows", "macos", "linux")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="extract-oracle",
        description="归档提取预言机：只读归档字节，预言各提取器/目标平台会写出什么名字。",
    )
    parser.add_argument("--version", action="version", version=f"extract-oracle {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    inspect_cmd = sub.add_parser("inspect", help="只报 EOCD 层结构事实（不是判定）")
    inspect_cmd.add_argument("archive", type=Path)
    inspect_cmd.add_argument("--format", choices=("json", "text"), default="text")
    inspect_cmd.add_argument("--out", type=Path, default=None, help="写盘路径（默认 stdout）")

    check_cmd = sub.add_parser("check", help="判定入口（五模块输出 findings）")
    check_cmd.add_argument("archive", type=Path)
    check_cmd.add_argument(
        "--target",
        action="append",
        default=None,
        metavar="{windows,macos,linux}",
        help="目标平台，可重复或逗号分隔（如 --target windows,macos）",
    )
    check_cmd.add_argument(
        "--module",
        action="append",
        default=None,
        metavar="{structure,encoding,fold,accessibility,container}",
        help=(
            "只跑这些判定模块（可重复或逗号分隔）。不给 = 要求五模块齐备，缺一个即退 3；"
            "给了 = 只对**明确点名的模块**负责，报告里的 modules 字段写明本次范围"
        ),
    )
    check_cmd.add_argument("--format", choices=("json", "text"), default="json")
    check_cmd.add_argument("--out", type=Path, default=None)

    sub.add_parser("capabilities", help="列出五模块落地状态")

    platforms_cmd = sub.add_parser("platforms", help="平台表操作")
    platforms_cmd.add_argument("--verify", action="store_true", help="校验平台表完整性并打印表指纹")

    return parser


def _parse_targets(values: Sequence[str] | None) -> list[str]:
    """支持 `--target windows`、`--target windows --target macos`、`--target windows,macos`。"""

    if not values:
        raise OracleError(ReasonCode.USAGE_ERROR, "check 至少需要一个 --target", {})
    picked: list[str] = []
    for raw in values:
        for part in raw.split(","):
            name = part.strip()
            if not name:
                raise OracleError(ReasonCode.USAGE_ERROR, "--target 含空值", {"value": raw})
            if name not in TARGETS:
                raise OracleError(
                    ReasonCode.USAGE_ERROR,
                    "--target 取值非法",
                    {"value": name, "allowed": list(TARGETS)},
                )
            if name not in picked:
                picked.append(name)
    return picked


def _emit(payload: dict, text: str, out: Path | None) -> None:
    if out is None:
        sys.stdout.write(text)
        return
    write_atomic(out, text)


def _parse_modules(values: Sequence[str] | None) -> list[str] | None:
    """`--module` 三种形态（单值 / 重复 / 逗号）；不给 = `None`（要求五模块齐备）。"""

    if not values:
        return None
    allowed = [module.name for module in MODULES]
    picked: list[str] = []
    for raw in values:
        for part in raw.split(","):
            name = part.strip()
            if not name:
                raise OracleError(ReasonCode.USAGE_ERROR, "--module 含空值", {"value": raw})
            if name not in allowed:
                raise OracleError(
                    ReasonCode.USAGE_ERROR,
                    "--module 取值非法",
                    {"value": name, "allowed": allowed},
                )
            if name not in picked:
                picked.append(name)
    return picked


def _run_module(name: str, archive: Archive) -> tuple:
    """按模块名分派到判定层。未实现的模块在 `cmd_check` 里已被拒（走不到这里）。"""

    if name == "structure":
        return structure_rules.check(archive)
    raise AssertionError(f"未分派的模块: {name}")  # pragma: no cover - 门在 cmd_check


def _entry_facts(archive: Archive) -> list[dict]:
    """三层结构事实的机读面（`plan/03` §0 的 `EntryView`，不含任何判定）。"""

    return [
        {
            "index": entry.index,
            "lfhOffset": entry.lfh_offset,
            "lfhEnd": entry.lfh_end,
            "cdOffset": entry.cd_offset,
            "lfhName": display_name(entry.lfh_name),
            "cdName": display_name(entry.cd_name),
            "lfhNameHex": entry.lfh_name.hex(),
            "cdNameHex": entry.cd_name.hex(),
            "lfhFlags": entry.lfh_flags,
            "cdFlags": entry.cd_flags,
            "lfhCrc": entry.lfh_crc,
            "cdCrc": entry.cd_crc,
            "lfhCompSize": entry.lfh_csize,
            "cdCompSize": entry.cd_csize,
            "lfhUncompSize": entry.lfh_usize,
            "cdUncompSize": entry.cd_usize,
            "method": entry.method,
            "lfhExtraIds": [item.field_id for item in entry.lfh_extra],
            "cdExtraIds": [item.field_id for item in entry.cd_extra],
        }
        for entry in archive.entries
    ]


def cmd_inspect(args: argparse.Namespace) -> int:
    archive = read_archive(args.archive)
    facts = archive.probe
    entries = _entry_facts(archive)
    names = [item.to_dict() for item in encoding_rules.describe_all(archive)]
    payload = {
        "tool_version": __version__,
        "schema_version": SCHEMA_VERSION,
        "command": "inspect",
        "archive": {"size": facts.archive_size, "eocd_offset": facts.eocd_offset},
        "eocd": {
            "declared_entries": facts.declared_entries,
            "declared_cd_size": facts.declared_cd_size,
            "declared_cd_offset": facts.declared_cd_offset,
            "comment_length": facts.comment_length,
        },
        "cd": {
            "actual_entries": archive.cd_actual_entries,
            "span_start": archive.cd_span[0],
            "span_end": archive.cd_span[1],
            "zip64": archive.zip64,
        },
        "entries": entries,
        "names": names,
        "findings": [],
        "summary": {"entry_count": len(entries), "finding_count": 0},
    }
    if args.format == "json":
        _emit(payload, dumps_json(payload), args.out)
    else:
        lines = [
            f"extract-oracle {__version__} (inspect, 结构事实非判定)",
            f"size={facts.archive_size} eocd@{facts.eocd_offset}",
            f"declared_entries={facts.declared_entries} actual_entries={archive.cd_actual_entries} "
            f"cd@{archive.cd_span[0]}..{archive.cd_span[1]}",
        ]
        for entry in archive.entries:
            lines.append(
                "  [{index}] lfh@{lfh_offset}..{lfh_end} cd@{cd_offset} "
                "name={name} bit11={bit11}".format(
                    index=entry.index,
                    lfh_offset=entry.lfh_offset,
                    lfh_end=entry.lfh_end,
                    cd_offset=entry.cd_offset,
                    name=display_name(entry.cd_name),
                    bit11=int(bool(entry.cd_flags & encoding_rules.FLAG_UTF8)),
                )
            )
        _emit(payload, "\n".join(lines) + "\n", args.out)
    return int(ExitCode.OK)


def cmd_check(args: argparse.Namespace) -> int:
    targets = _parse_targets(args.target)
    requested = _parse_modules(args.module)
    # 先读字节（输入不可解析优先于能力缺失：错的是输入，不是我们没实现）。
    archive = read_archive(args.archive)

    implemented = {module.name for module in MODULES if module.implemented}
    if requested is None:
        absent = missing_core()
        if absent:
            raise OracleError(
                ReasonCode.CAPABILITY_MISSING,
                "判定层尚未落地，拒绝产出空 findings",
                {
                    "missing_modules": absent,
                    "targets": targets,
                    "declared_entries": archive.probe.declared_entries,
                    "hint": "五模块落地后本子命令才输出 findings；当前可用 `inspect` 看结构事实，"
                    "或用 `--module structure` 只跑已落地的模块（报告里写明范围）",
                },
            )
        scope = [module.name for module in MODULES]
    else:
        # 点名的模块里只要有一个没落地 → 拒。**不得**把"没点名"当成"没问题"。
        absent = [name for name in requested if name not in implemented]
        if absent:
            raise OracleError(
                ReasonCode.CAPABILITY_MISSING,
                "--module 点名的判定模块尚未落地，拒绝产出空 findings",
                {
                    "missing_modules": absent,
                    "implemented_modules": sorted(implemented),
                    "targets": targets,
                },
            )
        scope = requested

    findings = []
    for name in scope:
        findings.extend(_run_module(name, archive))
    findings = [item.to_dict() for item in sort_findings(findings)]

    payload = {
        "tool_version": __version__,
        "schema_version": SCHEMA_VERSION,
        "command": "check",
        "target": targets[0],
        "targets": targets,
        "modules": scope,
        "entries": _entry_facts(archive),
        "findings": findings,
        "collisions": [],
        "summary": {"entry_count": len(archive.entries), "finding_count": len(findings)},
    }
    text = dumps_json(payload) if args.format == "json" else render_text(payload)
    _emit(payload, text, args.out)
    # `data/README.md` §4.1：0 = 无 finding，1 = 有 finding。空 findings 才允许退 0。
    return int(ExitCode.FINDINGS if findings else ExitCode.OK)


def cmd_capabilities(_: argparse.Namespace) -> int:
    lines = [f"extract-oracle {__version__} capabilities"]
    for module in MODULES:
        state = "implemented" if module.implemented else "pending"
        lines.append(f"  {module.name:<16} {module.milestone:<6} {module.rule_prefix:<24} {state}")
    sys.stdout.write("\n".join(lines) + "\n")
    return int(ExitCode.OK)


def cmd_platforms(args: argparse.Namespace) -> int:
    if not args.verify:
        raise OracleError(ReasonCode.USAGE_ERROR, "platforms 需要 --verify", {})
    raise OracleError(
        ReasonCode.PLATFORM_TABLE_MISSING,
        "平台表尚未落地（M1 取表 / M3 接入）",
        {"expected": "data/platforms/ntfs-upcase.bin + data/platforms/meta.json"},
    )


COMMANDS = {
    "inspect": cmd_inspect,
    "check": cmd_check,
    "capabilities": cmd_capabilities,
    "platforms": cmd_platforms,
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # argparse 用法错误统一成 4（口径 §4.1）
        code = exc.code
        return int(ExitCode.USAGE_ERROR if code not in (0, None) else ExitCode.OK)

    try:
        return COMMANDS[args.command](args)
    except OracleError as exc:
        # 机读面：stderr 一行 JSON，便于 CI 断言；stdout 不产出半份报告。
        sys.stderr.write(
            json.dumps(
                {
                    "error": exc.code.value,
                    "message": exc.message,
                    "exit_code": int(exc.exit_code),
                    "detail": exc.detail,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n"
        )
        return int(exc.exit_code)


__all__ = ["build_parser", "main"]
