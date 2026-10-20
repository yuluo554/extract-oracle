"""CLI 入口（唯一交付态入口）。

子命令（骨架期）：
- `inspect <archive>`：只报 EOCD 层结构事实（**不是判定**）；
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
from .report import SCHEMA_VERSION, dumps_json, render_text, write_atomic
from .zip_reader import probe

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


def cmd_inspect(args: argparse.Namespace) -> int:
    facts = probe(args.archive)
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
        "findings": [],
        "summary": {"entry_count": facts.declared_entries, "finding_count": 0},
    }
    if args.format == "json":
        _emit(payload, dumps_json(payload), args.out)
    else:
        text = (
            f"extract-oracle {__version__} (inspect, 结构事实非判定)\n"
            f"size={facts.archive_size} eocd@{facts.eocd_offset}\n"
            f"declared_entries={facts.declared_entries} "
            f"cd_offset={facts.declared_cd_offset} cd_size={facts.declared_cd_size}\n"
        )
        _emit(payload, text, args.out)
    return int(ExitCode.OK)


def cmd_check(args: argparse.Namespace) -> int:
    targets = _parse_targets(args.target)
    # 先读字节（输入不可解析优先于能力缺失：错的是输入，不是我们没实现）。
    facts = probe(args.archive)

    absent = missing_core()
    if absent:
        raise OracleError(
            ReasonCode.CAPABILITY_MISSING,
            "判定层尚未落地，拒绝产出空 findings",
            {
                "missing_modules": absent,
                "targets": targets,
                "declared_entries": facts.declared_entries,
                "hint": "五模块落地后本子命令才输出 findings；当前可用 `inspect` 看结构事实",
            },
        )

    # 五模块全部 implemented 之后才会走到这里（M5 收尾）。
    payload = {
        "tool_version": __version__,
        "schema_version": SCHEMA_VERSION,
        "command": "check",
        "target": targets[0],
        "targets": targets,
        "entries": [],
        "findings": [],
        "collisions": [],
        "summary": {"entry_count": facts.declared_entries, "finding_count": 0},
    }
    text = dumps_json(payload) if args.format == "json" else render_text(payload)
    _emit(payload, text, args.out)
    return int(ExitCode.OK)


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
