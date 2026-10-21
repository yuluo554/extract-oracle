"""CLI 入口（唯一交付态入口）。

子命令：
- `inspect <archive>`：报 EOCD / CD / LFH 三层结构事实 + 名字层事实（**不是判定**，不产 `ruleId`）；
- `capabilities`：列出五模块落地状态；
- `platforms --verify`：平台表完整性校验（真校验：`sha256` 对账 + `source` 枚举 + 表指纹）；
- `check <archive> --target {windows,macos,linux}`：**判定入口**。判定层未就绪时按
  `data/README.md` §4.1 返回退出码 3（`capability_missing`），**绝不产出空 findings**。

退出码语义见 `data/README.md` §4.1；本模块不得硬编码整数，统一走 `ExitCode`。
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from . import __version__
from .capabilities import MODULES, missing_core
from .errors import OracleError, ReasonCode
from .exit_codes import ExitCode
from .findings import Collision, Finding, display_name, sort_collisions, sort_findings
from .platforms import PlatformTables
from .platforms import load as load_platforms
from .platforms import verify as verify_platforms
from .report import SCHEMA_VERSION, dumps_json, render_text, write_atomic
from .rules import access as access_rules
from .rules import budget as budget_rules
from .rules import container as container_rules
from .rules import encoding as encoding_rules
from .rules import fold as fold_rules
from .rules import structure as structure_rules
from .zip_reader import Archive, read_archive

TARGETS = ("windows", "macos", "linux")


@dataclass(frozen=True)
class ModuleResult:
    """一个判定模块的产出（`_run_module` 的返回值）。

    五个字段对应五种形状，`None`/空元组 = 该模块不产这一种。这样加模块时不用再动一个
    四元组（`plan/HANDOFF-M5.md` §2 第 4 条点的就是这个：任一新形状都要同提交扩元组；
    这里一次扩成具名字段，后续加形状只加字段）。
    """

    findings: tuple[Finding, ...] = ()
    collisions: tuple[Collision, ...] = ()
    accessibility: dict[int, dict[str, dict]] | None = None
    #: MOD-2 的推断面（`data/README.md` §4.12）：按 `entry_index` 升序的数组。
    encoding: list[dict] | None = None
    #: MOD-5 的容器识别结果（`data/README.md` §4.13）：`{"kind": "epub"|"odf"|"none"}`。
    container: dict[str, str] | None = None


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
    platforms_cmd.add_argument(
        "--dir", type=Path, default=None, help="平台表目录（默认自动定位 data/platforms）"
    )
    platforms_cmd.add_argument("--format", choices=("json", "text"), default="text")
    platforms_cmd.add_argument("--out", type=Path, default=None)

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


def _run_module(
    name: str,
    archive: Archive,
    targets: list[str],
    tables: PlatformTables,
) -> "ModuleResult":
    """按模块名分派到判定层。未实现的模块在 `cmd_check` 里已被拒（走不到这里）。

    五种形状各归其主（`ModuleResult` 的字段就是这五种）：

    - `Finding`：MOD-1 / MOD-2 / MOD-5（`structure` / `encoding` / `container` / `budget`）；
    - `Collision`：MOD-3（`fold`，`plan/01` §2 模块③）；
    - `dict[entry_index, dict[platform, verdict]]`：MOD-4（`accessibility`，`data/README.md` §4.2）；
    - `encoding[]` 块：MOD-2 的推断面（`data/README.md` §4.12）；
    - `container` 块：MOD-5 的容器识别结果（§4.13）。

    形状契约都在包根 `findings.py` / 本模块——判定层之间互不 import（K10），
    所以 M4 需要的"会写出什么名字"由这里组装后作为参数传入，`rules/access.py` 不 import `fold.py`。
    """

    if name == "structure":
        return ModuleResult(findings=structure_rules.check(archive))
    if name == "encoding":
        findings, block = encoding_rules.check(archive)
        return ModuleResult(findings=findings, encoding=block)
    if name == "accessibility":
        # 判定层只吃"归档 + 目标平台 + 平台表"；条目名来自 CD（与 MOD-1/3 同一字节源）。
        assert tables is not None  # noqa: S101 - cmd_check 已保证（accessibility 必带表）
        return ModuleResult(accessibility=access_rules.check(archive, targets, tables))
    if name == "fold":
        # MOD-3 消费的是"名字集合 + 目标平台 + 平台表"，由调用方组装后传入
        # （`plan/02` §二：判定模块之间不 import，也不做模块级全局单例）。
        assert tables is not None  # noqa: S101 - cmd_check 已保证（fold 必带表）
        return ModuleResult(collisions=fold_rules.check(archive, targets, tables))
    if name == "container":
        # `container` 模块 = `container.*`（MOD-5 容器约定）+ `budget.*`（MOD-5 长度预算）。
        # 两个判定模块**不能互相 import**（K10），所以由这里各调一次再把 findings 合并。
        container_findings, kind = container_rules.check(archive)
        budget_findings = budget_rules.check(archive, targets, tables)
        return ModuleResult(
            findings=tuple(container_findings) + tuple(budget_findings),
            container=kind,
        )
    raise AssertionError(f"未分派的模块: {name}")  # pragma: no cover - 门在 cmd_check


def _entry_facts(
    archive: Archive,
    accessibility: dict[int, dict[str, dict]] | None = None,
) -> list[dict]:
    """三层结构事实的机读面（`plan/03` §0 的 `EntryView`）。

    `accessibility` 给了就并进每个条目（MOD-4 的判定字段，`data/README.md` §4.11）：
    `{"platform": {"level", "reasons", "evidence"}}`。`inspect` 恒不传——它是结构事实，
    不产判定（`plan/00` D13）。
    """

    facts: list[dict] = []
    for entry in archive.entries:
        fact = {
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
        if accessibility is not None:
            fact["accessibility"] = accessibility.get(entry.index, {})
        facts.append(fact)
    return facts


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

    findings: list[Finding] = []
    collisions: list[Collision] = []
    accessibility: dict[int, dict[str, dict]] = {}
    encoding_block: list[dict] | None = None
    container_block: dict[str, str] | None = None
    # 平台表按需加载：只有本次范围含需要平台语义的模块且目标里有平台依赖时才读表。
    # 表缺/校验失败 = `platform_table_missing`（退出码 3），**不静默跳过该平台的判定**。
    # M5 的 `budget` 通过 `rules/budget.py::declared_platforms()`（恒空）声明"不查表"，
    # 所以它不会把 `$UpCase` 表变成 `container` 模块的隐式依赖。
    needs_tables = {
        "fold": fold_rules.PLATFORMS,
        "accessibility": access_rules.PLATFORMS,
    }
    tables: PlatformTables | None = None
    for module_name, platforms in needs_tables.items():
        if module_name in scope and any(name in targets for name in platforms):
            tables = load_platforms()
            break

    for name in scope:
        result = _run_module(name, archive, targets, tables)
        findings.extend(result.findings)
        collisions.extend(result.collisions)
        if result.accessibility is not None:
            accessibility.update(result.accessibility)
        if result.encoding is not None:
            encoding_block = result.encoding
        if result.container is not None:
            container_block = result.container
    ordered_findings = sort_findings(findings)
    ordered_collisions = sort_collisions(collisions)
    verdicts = [
        verdict for per_platform in accessibility.values() for verdict in per_platform.values()
    ]
    access_counts = {
        level: sum(1 for verdict in verdicts if verdict["level"] == level)
        for level in access_rules.LEVELS
    }
    inaccessible = access_rules.count_issues(accessibility)

    entries = _entry_facts(
        archive, accessibility if "accessibility" in scope else None
    )
    payload = {
        "tool_version": __version__,
        "schema_version": SCHEMA_VERSION,
        "command": "check",
        "target": targets[0],
        "targets": targets,
        "modules": scope,
        "entries": entries,
        "findings": [item.to_dict() for item in ordered_findings],
        "collisions": [item.to_dict() for item in ordered_collisions],
        # MOD-2 的推断面（`data/README.md` §4.12）：只在 `encoding` 在范围内时出现，
        # 否则 `null`——"没查"与"查了没问题"是两件事（同 §4.11 的 `accessibility_levels`）。
        "encoding": encoding_block,
        # MOD-5 的容器识别（§4.13）：同上，不在范围内是 `null`。
        "container": container_block,
        "platforms": tables.to_report_dict() if tables is not None else None,
        "summary": {
            "entry_count": len(archive.entries),
            "finding_count": len(ordered_findings),
            "collision_count": len(ordered_collisions),
            # MOD-4（`data/README.md` §4.2）：非 `OK` 的 (条目, 平台) 对数与逐级计数。
            "accessibility_count": inaccessible,
            "accessibility_levels": access_counts if "accessibility" in scope else None,
            # MOD-2（§4.4）：`low` 置信度的条目数。**不参与退码**（§4.1 仍是三条来源）——
            # 编码猜不准是"不确定"，不是"发现问题"；把它并进退码会让普通 GBK 样本假报。
            "low_confidence_count": (
                encoding_rules.count_low_confidence(encoding_block)
                if encoding_block is not None
                else None
            ),
        },
    }
    text = dumps_json(payload) if args.format == "json" else render_text(payload)
    _emit(payload, text, args.out)
    # `data/README.md` §4.1：0 = 无 finding，1 = 有判定产出。空结果才允许退 0；
    # `collisions`（MOD-3）与不可访问的条目（MOD-4）同为判定产出，命中即 1。
    return int(
        ExitCode.FINDINGS
        if (ordered_findings or ordered_collisions or inaccessible)
        else ExitCode.OK
    )


def cmd_capabilities(_: argparse.Namespace) -> int:
    lines = [f"extract-oracle {__version__} capabilities"]
    for module in MODULES:
        state = "implemented" if module.implemented else "pending"
        lines.append(f"  {module.name:<16} {module.milestone:<6} {module.rule_prefix:<24} {state}")
    sys.stdout.write("\n".join(lines) + "\n")
    return int(ExitCode.OK)


def cmd_platforms(args: argparse.Namespace) -> int:
    """`platforms --verify`：**真校验**（`plan/02` §四 三条契约 + K04）。

    校验不过抛 `platform_table_missing`（退出码 3），**不静默使用**；过了就打表指纹 + 卷标识。
    输出面是诊断（人读 + `--format json`），**不进任何 `check` 报告**——所以这里可以带
    `probed_at_utc` 与卷标识（`plan/02` §四 第 3 条只约束判定输入）。
    """

    if not args.verify:
        raise OracleError(ReasonCode.USAGE_ERROR, "platforms 需要 --verify", {})

    tables = verify_platforms(args.dir)
    report = tables.verify_report()
    payload = {
        "tool_version": __version__,
        "schema_version": SCHEMA_VERSION,
        "command": "platforms",
        "subcommand": "verify",
        "verified": True,
        **report,
    }
    if args.format == "json":
        _emit(payload, dumps_json(payload), args.out)
        return int(ExitCode.OK)

    lines = [
        f"extract-oracle {__version__} (platforms --verify)",
        "OK   platform tables verified",
        f"  ntfs_upcase  entries={tables.ntfs.entries} source={tables.ntfs.source} "
        f"sha256={tables.ntfs.table_id}…",
        f"  volume       serial={tables.ntfs.volume.get('serial_hex', '-')} "
        f"label={tables.ntfs.volume.get('label', '-')} "
        f"fs={tables.ntfs.volume.get('ntfs_version', '-')}",
        f"  macos        evidence_strength={tables.macos.get('evidence_strength', '-')} "
        f"source={tables.macos.get('source', '-')}",
        f"  linux        evidence_strength={tables.linux.get('evidence_strength', '-')} "
        f"source={tables.linux.get('source', '-')}",
    ]
    _emit(payload, "\n".join(lines) + "\n", args.out)
    return int(ExitCode.OK)


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
