#!/usr/bin/env python3
"""四工具行为对照实测：Python `zipfile` / Info-ZIP `unzip` / 7-Zip / libarchive。

每格落"命令 + 退出码 + 实际写出的名字 + 输出节选"，M6 定稿成 `docs/divergence.md`。
**必须是可重跑脚本，不是手抄表**——手抄表不能回归，工具行为漂移时也没人发现。

纪律（`plan/01` §2 MOD-1 依据纪律、`data/README.md` §4.8）：
- 只记录**实际观察到的行为**，不推断；
- 工具缺失 → 该格记 `tool_unavailable`，整体退出码 **3**（不静默跳过，否则矩阵看起来"全绿"）；
- 落盘确定性：**无时间戳、无随机 ID、无本机绝对路径**（临时目录一律回写为 `<workdir>`）；
  全部写盘经 `extract_oracle.report.write_atomic`；
- 解压只发生在**测试临时目录**，用完即删（`data/README.md` §3.1 的"不解压到磁盘"红线指
  **产物形态**；本脚本是测量工具，其临时产物在 `finally` 里清空，不入库、不进产物）。

用法：

    py -3.12 tools/probe_tools.py                      # 全部 fixture
    py -3.12 tools/probe_tools.py --check              # 只比对，不写盘
    py -3.12 tools/probe_tools.py --fixtures clean.zip # 指定样本

退出码：0 全部格实测完成且与盘上记录一致 / 1 有格与盘上记录不符 / 3 工具或 fixture 缺失 / 4 用法错误。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from extract_oracle.report import write_atomic  # noqa: E402

EXIT_OK = 0
EXIT_MISMATCH = 1
EXIT_CAPABILITY_MISSING = 3
EXIT_USAGE = 4

SCHEMA_VERSION = "1"

#: 四工具。`libarchive` 用 Windows 自带的 bsdtar（`C:\Windows\System32\tar.exe` 即 bsdtar）。
TOOLS = ("python-zipfile", "info-zip-unzip", "7zip", "libarchive")

#: 工具定位：先看环境变量，再看 PATH，最后看本机实测过的固定位置。
TOOL_CANDIDATES = {
    "info-zip-unzip": ("PROBE_UNZIP", ("unzip",), ()),
    "7zip": ("PROBE_7Z", ("7z", "7za"), (r"C:\Program Files\7-Zip\7z.exe",)),
    "libarchive": ("PROBE_BSDTAR", ("bsdtar",), (r"C:\Windows\System32\tar.exe",)),
}

#: 输出节选的最大行数与宽度（节选过长会让矩阵变成日志转储）。
EXCERPT_LINES = 6
EXCERPT_WIDTH = 200


def locate(tool: str) -> str | None:
    env_name, names, fixed = TOOL_CANDIDATES[tool]
    from_env = os.environ.get(env_name)
    if from_env and Path(from_env).exists():
        return from_env
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    for candidate in fixed:
        if Path(candidate).exists():
            # 只接受真正的目标工具：System32\tar.exe 必须是 bsdtar
            if tool == "libarchive" and not _is_bsdtar(candidate):
                continue
            return candidate
    return None


def _is_bsdtar(path: str) -> bool:
    try:
        out = subprocess.run([path, "--version"], capture_output=True, text=True, errors="replace", timeout=20)
    except (OSError, subprocess.SubprocessError):
        return False
    return "bsdtar" in (out.stdout or "").lower()


def tool_versions(paths: dict[str, str | None]) -> dict[str, str | None]:
    """各工具的自报版本首行（工具缺失记 None）。"""

    versions: dict[str, str | None] = {"python-zipfile": "Python %s (stdlib zipfile)" % _py_ver()}
    for tool, argv in (
        ("info-zip-unzip", [paths.get("info-zip-unzip"), "-v"]),
        ("7zip", [paths.get("7zip")]),
        ("libarchive", [paths.get("libarchive"), "--version"]),
    ):
        if not argv[0]:
            versions[tool] = None
            continue
        try:
            out = subprocess.run(argv, capture_output=True, text=True, errors="replace", timeout=30)
        except (OSError, subprocess.SubprocessError):
            versions[tool] = None
            continue
        text = (out.stdout or "") + (out.stderr or "")
        first = next((line.strip() for line in text.splitlines() if line.strip()), "")
        versions[tool] = first[:EXCERPT_WIDTH] or None
    return versions


def _py_ver() -> str:
    return "%d.%d.%d" % sys.version_info[:3]


# ----------------------------------------------------------------- 各工具的"实测"实现


def _run(argv: list[str], cwd: str) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            argv, capture_output=True, text=True, errors="replace", timeout=120, cwd=cwd
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return 127, "%s: %s" % (type(exc).__name__, exc)
    combined = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, combined


def _listing(directory: str) -> list[str]:
    out = []
    for root, dirs, files in os.walk(directory):
        for name in dirs + files:
            path = Path(root) / name
            rel = str(path.relative_to(directory)).replace(os.sep, "/")
            out.append(rel + ("/" if os.path.isdir(path) else ""))
    return sorted(out)


def _sanitize(text: str, workdir: str) -> str:
    """去掉本机绝对路径与临时目录，保留可读的节选（`data/README.md` §4.8：不输出本机绝对路径）。"""

    cleaned = text.replace(workdir, "<workdir>") if workdir else text
    # 兜底：任何残留的盘符路径整段替换（含 Windows 反斜杠与 MSYS 风格）
    cleaned = re.sub(r"[A-Za-z]:(?:\\\\|\\|/)[^\s'\"]*", "<path>", cleaned)
    cleaned = re.sub(r"/(?:tmp|var|home|Users)/[^\s'\"]*", "<path>", cleaned)
    lines = [line.rstrip() for line in cleaned.splitlines() if line.strip()]
    return "\n".join(lines[:EXCERPT_LINES])[: EXCERPT_WIDTH * EXCERPT_LINES]


def _sanitize_error(text: str, workdir: str) -> str:
    """异常消息同样要走清洗——它最容易把临时目录整条带进产物。"""

    return _sanitize(text, workdir)


def probe_python(src: Path, workdir: str) -> dict:
    target = os.path.join(workdir, "out")
    os.makedirs(target, exist_ok=True)
    command = "python -m zipfile -e <fixture> <workdir>/out"
    try:
        with zipfile.ZipFile(src) as archive:
            names = archive.namelist()
            archive.extractall(target)
    except Exception as exc:  # noqa: BLE001 —— 这里就是要记录任何异常
        return {
            "status": "refused",
            "command": command,
            "exit_code": None,
            "error": "%s: %s" % (type(exc).__name__, _sanitize_error(str(exc), workdir)),
            "written": _listing(target),
            "namelist": None,
            "output_excerpt": "",
        }
    return {
        "status": "ok",
        "command": command,
        "exit_code": 0,
        "written": _listing(target),
        "namelist": names,
        "output_excerpt": "",
    }


def probe_unzip(path: str, src: Path, workdir: str) -> dict:
    target = os.path.join(workdir, "out")
    os.makedirs(target, exist_ok=True)
    rc, out = _run([path, "-o", str(src), "-d", target], workdir)
    return {
        "status": "ok" if rc in (0, 1) else "failed",
        "command": "unzip -o <fixture> -d <workdir>/out",
        "exit_code": rc,
        "written": _listing(target),
        "output_excerpt": _sanitize(out, workdir),
    }


def probe_7zip(path: str, src: Path, workdir: str) -> dict:
    target = os.path.join(workdir, "out")
    os.makedirs(target, exist_ok=True)
    rc, out = _run([path, "x", "-y", "-o" + target, str(src)], workdir)
    return {
        "status": "ok" if rc in (0, 1) else "failed",
        "command": "7z x -y -o<workdir>/out <fixture>",
        "exit_code": rc,
        "written": _listing(target),
        "output_excerpt": _sanitize(out, workdir),
    }


def probe_libarchive(path: str, src: Path, workdir: str) -> dict:
    target = os.path.join(workdir, "out")
    os.makedirs(target, exist_ok=True)
    rc, out = _run([path, "-x", "-f", str(src), "-C", target], workdir)
    return {
        "status": "ok" if rc in (0, 1) else "failed",
        "command": "bsdtar -x -f <fixture> -C <workdir>/out",
        "exit_code": rc,
        "written": _listing(target),
        "output_excerpt": _sanitize(out, workdir),
    }


# ----------------------------------------------------------------- 主流程


def probe_one(src: Path, paths: dict[str, str | None]) -> dict:
    # 子进程的 cwd 是临时目录，因此**必须**传归档的绝对路径（相对路径会落到临时目录里找不到）。
    src = src.resolve()
    cells: dict[str, dict] = {}
    for tool in TOOLS:
        workdir = tempfile.mkdtemp(prefix="probe-")
        try:
            if tool == "python-zipfile":
                cells[tool] = probe_python(src, workdir)
            else:
                located = paths.get(tool)
                if not located:
                    cells[tool] = {
                        "status": "tool_unavailable",
                        "command": None,
                        "exit_code": None,
                        "written": [],
                        "output_excerpt": "",
                    }
                elif tool == "info-zip-unzip":
                    cells[tool] = probe_unzip(located, src, workdir)
                elif tool == "7zip":
                    cells[tool] = probe_7zip(located, src, workdir)
                else:
                    cells[tool] = probe_libarchive(located, src, workdir)
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    names = {tool: cells[tool].get("written", []) for tool in TOOLS}
    distinct = sorted({tuple(value) for value in names.values()})
    return {
        "fixture": src.name,
        "schema_version": SCHEMA_VERSION,
        "cells": cells,
        "agreement": {
            "distinct_written_sets": len(distinct),
            "tools_agree": len(distinct) == 1,
            "unavailable": sorted(tool for tool in TOOLS if cells[tool]["status"] == "tool_unavailable"),
            "refused": sorted(tool for tool in TOOLS if cells[tool]["status"] == "refused"),
        },
    }


def iter_fixtures(directory: Path) -> list[Path]:
    return sorted(
        path for path in directory.iterdir() if path.suffix in {".zip", ".epub"} and path.is_file()
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="probe_tools", description="四工具行为对照（可重跑）")
    parser.add_argument("--fixtures-dir", default="data/fixtures")
    parser.add_argument("--out", default="data/tool-matrix")
    parser.add_argument("--fixtures", nargs="*", default=None, help="只跑这些样本名（默认全部）")
    parser.add_argument("--check", action="store_true", help="只比对盘上记录，不写盘")
    args = parser.parse_args(argv)

    fixture_dir = Path(args.fixtures_dir)
    if not fixture_dir.is_dir():
        print(f"probe_tools: fixture 目录不存在: {fixture_dir}", file=sys.stderr)
        return EXIT_USAGE

    all_fixtures = iter_fixtures(fixture_dir)
    if args.fixtures:
        wanted = set(args.fixtures)
        selected = [p for p in all_fixtures if p.name in wanted]
        missing = sorted(wanted - {p.name for p in selected})
        if missing:
            print(f"probe_tools: fixture 不存在: {', '.join(missing)}", file=sys.stderr)
            return EXIT_USAGE
    else:
        selected = all_fixtures

    paths = {tool: locate(tool) for tool in TOOLS if tool != "python-zipfile"}
    versions = tool_versions(paths)
    unavailable = sorted(tool for tool in TOOLS if tool != "python-zipfile" and not paths.get(tool))

    out_dir = Path(args.out)
    mismatches: list[str] = []
    rows: list[dict] = []
    for src in selected:
        record = probe_one(src, paths)
        rows.append(record)
        target = out_dir / f"{src.name}.json"
        text = json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        if args.check:
            if not target.exists():
                mismatches.append(f"缺记录: {target.name}")
            elif target.read_text(encoding="utf-8") != text:
                mismatches.append(f"记录与实测不符: {target.name}")
        else:
            write_atomic(target, text)

    summary = {
        "schema_version": SCHEMA_VERSION,
        "tool_versions": versions,
        "fixtures": [row["fixture"] for row in rows],
        "rows": [
            {
                "fixture": row["fixture"],
                "written": {tool: row["cells"][tool].get("written", []) for tool in TOOLS},
                "exit_codes": {tool: row["cells"][tool].get("exit_code") for tool in TOOLS},
                "distinct_written_sets": row["agreement"]["distinct_written_sets"],
                "tools_agree": row["agreement"]["tools_agree"],
            }
            for row in rows
        ],
    }
    summary_text = json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    summary_path = out_dir / "_summary.json"
    if args.check:
        if not summary_path.exists():
            mismatches.append("缺 _summary.json")
        elif summary_path.read_text(encoding="utf-8") != summary_text:
            mismatches.append("_summary.json 与实测不符")
    else:
        write_atomic(summary_path, summary_text)

    disagreeing = [row["fixture"] for row in rows if not row["agreement"]["tools_agree"]]
    print(f"对照组：{len(rows)} 份 fixture × {len(TOOLS)} 工具")
    for tool in TOOLS:
        state = versions.get(tool) or "MISSING"
        print(f"  {tool:16s} {state}")
    if disagreeing:
        print(f"  四工具落盘名字不一致的样本（{len(disagreeing)}）: {', '.join(disagreeing)}")

    if mismatches:
        for item in mismatches:
            print(f"FAIL  {item}")
        return EXIT_MISMATCH
    if unavailable:
        print(f"probe_tools: 工具缺失 {', '.join(unavailable)} —— capability_missing", file=sys.stderr)
        return EXIT_CAPABILITY_MISSING
    print("OK  全部格实测完成，记录与盘上一致" if args.check else "OK  全部格实测完成，已落盘")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
