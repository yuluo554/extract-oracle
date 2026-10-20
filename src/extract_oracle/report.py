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

#: 报告 schema 版本。M2 起 `inspect` 增加 `entries` / `names` 两层（加法，不改既有键）。
SCHEMA_VERSION = "0.2"


def dumps_json(payload: dict[str, Any]) -> str:
    """确定性 JSON 文本（`sort_keys` + `ensure_ascii=False` + 两空格缩进 + 结尾换行）。"""

    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def render_text(payload: dict[str, Any]) -> str:
    """人读面。M3 起渲染 `summary` + `findings` + `collisions`；字段集由 `plan/03` 固定。"""

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
