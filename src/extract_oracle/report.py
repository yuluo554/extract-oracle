"""报告导出：JSON 与文本双轨，确定性（同输入双跑逐字节一致）。

确定性纪律（`plan/01` §2 四条纪律之一）：
- 不含时间戳、不含随机 ID、不含本机绝对路径；
- 键序固定（`sort_keys=True`）、数组排序在调用方确定；
- 数值格式固定（整数；不做浮点四舍五入）；
- 换行恒为 LF、文件结尾恒有换行（`data/README.md` §4.8）。

全部写盘必须经本模块的 `dump_json` / `dump_text` / `write_atomic`——别在子命令里各写各的。
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

#: 报告 schema 版本。M2 起 `inspect` 增加 `entries` / `names` 两层（加法，不改既有键）；
#: M4 起 `check` 的 `entries[]` 增加 `accessibility`（同样只加不改）。
SCHEMA_VERSION = "0.2"

#: 文本面渲染 `accessibility` 计数时的行内顺序（`data/README.md` §4.2 的四个取值）。
#:
#: 这里刻意**不** import `rules/access.py`：报告层与判定层是并列的下游（都只被 `cli` 使用），
#: 加一条 `report → rules` 的边会让分层图多出一个方向。两份枚举的一致性由
#: `tests/test_accessibility.py::test_report_level_order_matches_rules` 钉住。
ACCESS_LEVELS: tuple[str, ...] = ("BLOCKED", "WRITTEN_UNREADABLE", "WRITTEN_TRUNCATED", "OK")


def dumps_json(payload: dict[str, Any]) -> str:
    """确定性 JSON 文本（`sort_keys` + `ensure_ascii=False` + 两空格缩进 + 结尾换行）。"""

    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def render_text(payload: dict[str, Any]) -> str:
    """人读面。M3 起渲染 `summary` + `findings` + `collisions`；M4 加 `accessibility`。

    行序由 payload 的固定键顺序决定，不遍历 dict（`data/README.md` §4.8）。
    """

    lines: list[str] = []
    summary = payload.get("summary", {})
    lines.append(f"extract-oracle {payload.get('tool_version', '?')}")
    lines.append(f"schema {payload.get('schema_version', '?')}")
    lines.append(
        "target={target} entries={entries} findings={findings} collisions={collisions}".format(
            target=payload.get("target", "-"),
            entries=summary.get("entry_count", 0),
            findings=summary.get("finding_count", 0),
            collisions=summary.get("collision_count", 0),
        )
    )
    if summary.get("accessibility_levels") is not None:
        levels = summary["accessibility_levels"]
        lines.append(
            "accessibility "
            + " ".join(f"{name}={levels.get(name, 0)}" for name in ACCESS_LEVELS)
        )
    findings = payload.get("findings", [])
    if findings:
        lines.append("")
        for item in findings:
            lines.append(f"- {item.get('ruleId', '?')}: {item.get('message', '')}")
    collisions = payload.get("collisions", [])
    if collisions:
        lines.append("")
        for item in collisions:
            lines.append(
                "- {code} [{platform}] {names} → survivor {survivor} ({verdict}, {strength})".format(
                    code=item.get("code", "?"),
                    platform=item.get("platform", "?"),
                    names=" + ".join(item.get("names", [])),
                    survivor=item.get("survivor", "?"),
                    verdict=item.get("verdict", "?"),
                    strength=item.get("evidenceStrength", "?"),
                )
            )
    return "\n".join(lines) + "\n"


def write_atomic(path: Path, text: str) -> None:
    """原子写（临时文件 + rename），字节形态由调用方给定，不依赖平台默认换行。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    handle, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=path.suffix)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


__all__ = ["SCHEMA_VERSION", "dumps_json", "render_text", "write_atomic"]
