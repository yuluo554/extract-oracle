#!/usr/bin/env python3
"""布局门（方法论装订第②件）：把"项目还长在方法论上"变成可跑红的断言。

判据集沿用 `ai-tool-project-sprint` 的 `references/templates/check-sprint-layout.mjs`
（Node 实现），本文件是 **Python 重写**——**判据本身不改**，只换实现语言（项目零第三方依赖）。

判据一律落**仓库内文件**（不读 git 元数据：浅克隆下 tag / 历史深度会翻转）。

退出码：0 全绿 / 1 有 FAIL / 2 用法错误。

变异验证（10 组，逐组必须变红；见 `plan/05` §门验证）：
  M1 删 AGENTS.md                               → LAYOUT.FILES
  M2 一个副本里把 ✅ 翻成 ⬜                     → LAYOUT.STATUS
  M3 缺口格写回已 ✅ 的里程碑                    → LAYOUT.GAPS
  M4 删一份 HANDOFF-M<k>                         → LAYOUT.HANDOFFS
  M5 删 plan/00 顶部装订行                       → LAYOUT.BINDING_HEAD
  M6 删发布留档的「覆盖对账」整节                → LAYOUT.RELEASE
  M7 删一份 plan/0<k>                           → LAYOUT.FILES
  M8 去掉发布留档 §二标题里的 "tag 后"           → LAYOUT.RELEASE
  M9 台账里一条 ✅ 行改成 ⬜ 待 M<k>             → LAYOUT.LEDGER
  M10 发布里程碑 ✅ 留着但删掉 RELEASE-M<last>   → LAYOUT.RELEASE
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CHECKS: list[tuple[str, bool, str]] = []
SCANNED = {"docs": 0, "handoffs": 0, "copies": 0, "doc_tools": 0}


def add(check_id: str, ok: bool, detail: str) -> None:
    CHECKS.append((check_id, ok, detail))


def read(rel: str) -> str | None:
    path = ROOT / rel
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


REQUIRED_FILES = [
    "AGENTS.md",
    "README.md",
    "data/README.md",
    "plan/00-README总览.md",
    "plan/01-题目文档.md",
    "plan/02-架构与技术选型.md",
    "plan/03-模块详设.md",
    "plan/04-数据计划.md",
    "plan/05-里程碑与发布.md",
    "plan/06-交付对标与决策.md",
]

#: 三个锚点必须**同现于一行**（方法论名 + 布局门命令 + 装订日期）；顺序无关（前瞻语义）。
BINDING_LINE = re.compile(
    r"^>(?=.*ai-tool-project-sprint)(?=.*check_sprint_layout)(?=.*20\d{2}-\d{2}-\d{2}).*$", re.M
)

REQUIRED_SECTIONS = {
    "plan/00-README总览.md": ["文档索引", "决策记录", "承诺-证据台账", "里程碑"],
    "plan/01-题目文档.md": ["任务要求", "评分标准", "边界与非目标"],
    "plan/02-架构与技术选型.md": ["分层", "构建"],
    "plan/04-数据计划.md": ["数据清单", "真值纪律", "数值口径"],
    "plan/05-里程碑与发布.md": ["DoD", "已知未验证项"],
    "plan/06-交付对标与决策.md": ["评分对标", "风险登记"],
    "data/README.md": ["依据查证记录", "数值口径"],
}

#: HANDOFF 七节（硬约束①）。项目自定更细的格式 = 合法超集：只断言"必需节都存在"。
HANDOFF_SECTIONS = ["当前进度", "当前事实", "待办", "既定口径", "环境坑", "DoD", "命令速查"]

#: 项目**已声明**的豁免（门必须复用，别另立更严的一套）。
EXEMPT_MILESTONES = [0]

STATUS_COPIES = [
    ("plan/00-README总览.md", "里程碑表"),
    ("plan/05-里程碑与发布.md", "状态表"),
    ("README.md", "状态行"),
]

#: 状态行 = 表格行 + 首格是里程碑号 + **存在一个"恰好只含状态标记"的单元格**。
#: 第三条不能省：本项目的"里程碑内容表"（内容 / DoD）与"变异验证表"（变异 / 期望判据）也以
#: `| M1 | …` 开头；只按"行内含状态 token"判定会把它们读成状态副本（实测：门首版由此把
#: M1–M6 全判成 done，`LAYOUT.STATUS` 报 6 个假红）。判据落在"状态格本身"是张冠李戴的正面修法。
#: 状态格的位置**不写死列号**：`plan/00` 里程碑表是末列、`plan/05` 与 README 是第二列——
#: 写死列号会让其中一处恒假（假门形态 ④）。
STATUS_LINE = re.compile(r"^\|\s*\*{0,2}M(\d+)\b")
STATUS_CELL_MARKERS = ("✅", "⬜", "🟡")
PENDING_MARKERS = ("⬜", "🟡", "未开始", "未执行", "待执行", "待确认")


def _status_cell(line: str) -> str | None:
    """返回该行里**恰好只含一个状态标记**的单元格；没有则返回 None（该行不参与状态判定）。"""

    for raw in line.split("|")[1:]:
        cell = raw.replace("*", "").strip()
        if cell in STATUS_CELL_MARKERS:
            return cell
    return None

RELEASE_MILESTONE = 6


def check_required_files() -> None:
    missing = [rel for rel in REQUIRED_FILES if not (ROOT / rel).exists()]
    SCANNED["docs"] = len(REQUIRED_FILES) - len(missing)
    add(
        "LAYOUT.FILES",
        not missing,
        f"缺: {','.join(missing)}" if missing else f"{SCANNED['docs']} 份齐备",
    )


def check_binding_head() -> None:
    text = read("plan/00-README总览.md") or ""
    ok = bool(BINDING_LINE.search(text))
    add(
        "LAYOUT.BINDING_HEAD",
        ok,
        "plan/00 顶部有装订行（三锚点齐）"
        if ok
        else "plan/00 顶部缺装订行（需同现：方法论名 + 布局门命令 + 装订日期）",
    )


def check_sections() -> None:
    bad: list[str] = []
    for rel, needles in REQUIRED_SECTIONS.items():
        text = read(rel)
        if text is None:
            continue
        missing = [n for n in needles if n not in text]
        if missing:
            bad.append(f"{rel}: {'/'.join(missing)}")
    add(
        "LAYOUT.SECTIONS",
        not bad,
        "；".join(bad) if bad else f"{len(REQUIRED_SECTIONS)} 份小节齐备",
    )


def check_documented_tools_exist() -> None:
    """文档点名的 `tools/*.py` 必须有实物（引用了却从未实现的发布门是实测形态之一）。"""

    exempt: set[str] = set()
    docs = ["AGENTS.md"]
    plan_dir = ROOT / "plan"
    if plan_dir.exists():
        docs += [f"plan/{p.name}" for p in sorted(plan_dir.glob("*.md"))]
    referenced: set[str] = set()
    for rel in docs:
        text = read(rel)
        if text is None:
            continue
        referenced.update(re.findall(r"tools/[\w.-]+\.(?:mjs|js|cjs|py|sh|ps1)", text))
    if not referenced:
        add("LAYOUT.DOC_TOOLS", False, f"扫了 {len(docs)} 份文档，0 处 tools/ 引用——判据是空的")
        return
    SCANNED["doc_tools"] = len(referenced)
    missing = sorted(p for p in referenced if p not in exempt and not (ROOT / p).exists())
    add(
        "LAYOUT.DOC_TOOLS",
        not missing,
        f"文档点名但不存在的工具: {','.join(missing)}"
        if missing
        else f"{len(referenced)} 个文档点名的 tools/ 脚本全部在位",
    )


def collect_states() -> dict[int, set[str]]:
    """逐副本采集 `Map<k, Set<done|pending>>`——**真值不取自任何一个副本**。"""

    states: dict[int, set[str]] = {}
    for rel, _kind in STATUS_COPIES:
        text = read(rel)
        if text is None:
            continue
        SCANNED["copies"] += 1
        for line in text.split("\n"):
            match = STATUS_LINE.match(line)
            if not match:
                continue
            marker = _status_cell(line)
            if marker is None:
                continue  # 不是状态行（内容表 / 变异表）
            pending = marker in PENDING_MARKERS
            states.setdefault(int(match.group(1)), set()).add("pending" if pending else "done")
    return states


def check_status_agreement(states: dict[int, set[str]]) -> None:
    conflicts = [
        f"M{k} 在副本间状态不一致（{' vs '.join(sorted(s))}）"
        for k, s in sorted(states.items())
        if len(s) > 1
    ]
    add(
        "LAYOUT.STATUS",
        not conflicts,
        "；".join(conflicts)
        if conflicts
        else f"{SCANNED['copies']} 处副本 × {len(states)} 个里程碑 状态全一致",
    )


def check_handoffs(done: list[int]) -> None:
    missing: list[str] = []
    for k in done:
        if k in EXEMPT_MILESTONES:
            continue
        rel = f"plan/HANDOFF-M{k}.md"
        text = read(rel)
        if text is None:
            missing.append(f"{rel}(缺)")
            continue
        SCANNED["handoffs"] += 1
        lack = [n for n in HANDOFF_SECTIONS if n not in text]
        if lack:
            missing.append(f"{rel}(缺节: {'/'.join(lack)})")
    add(
        "LAYOUT.HANDOFFS",
        not missing,
        "；".join(missing) if missing else f"{SCANNED['handoffs']} 份交接单齐（M0 已声明豁免）",
    )


def check_next_handoff(done: list[int], all_milestones: list[int]) -> None:
    """硬约束①：每个里程碑收尾都要先写**下一棒**的 HANDOFF 才能结束对话。

    这条让 M0 的装订门不是空跑（M0 的收尾记录就是 `plan/HANDOFF-M1.md`），
    也是"交接单必须在当下对话内落盘"的可跑红形态。
    """

    if not done:
        add("LAYOUT.HANDOFF_NEXT", False, "没有任何 ✅ 里程碑——状态副本判据空跑")
        return
    nxt = min([k for k in all_milestones if k > max(done)], default=None)
    if nxt is None:
        add("LAYOUT.HANDOFF_NEXT", True, "已是最后一个里程碑，无下一棒交接单要求")
        return
    rel = f"plan/HANDOFF-M{nxt}.md"
    text = read(rel)
    if text is None:
        add("LAYOUT.HANDOFF_NEXT", False, f"缺 {rel}（里程碑收尾必须在本对话内写完下一棒交接单）")
        return
    SCANNED["handoffs"] += 1
    lack = [n for n in HANDOFF_SECTIONS if n not in text]
    add(
        "LAYOUT.HANDOFF_NEXT",
        not lack,
        f"{rel} 缺节: {'/'.join(lack)}" if lack else f"{rel} 七节齐（下一棒 = M{nxt}）",
    )


def check_stale_gaps(done: list[int]) -> None:
    """`plan/06` 的「缺口」列是状态的隐蔽副本：**按表头定位列号**，扫描面收窄到表尾。"""

    lines = (read("plan/06-交付对标与决策.md") or "").split("\n")
    header_idx = next(
        (i for i, line in enumerate(lines) if line.startswith("|") and "缺口" in line), -1
    )
    if header_idx < 0:
        add("LAYOUT.GAPS", False, "plan/06 找不到含『缺口』表头的表（判据表搬走了？）")
        return
    # 按**表头单元格**定位"缺口"列，不假设它一定是最后一列
    # （末列假设会把"关闭条件"列当成缺口列 → 真实故障永远抓不到，实测假门族 ②）。
    header_cells = lines[header_idx].split("|")
    col = next((i for i, cell in enumerate(header_cells) if "缺口" in cell), None)
    if col is None:
        add("LAYOUT.GAPS", False, "plan/06 缺口表头里找不到『缺口』单元格")
        return
    stale: list[str] = []
    rows = 0
    for line in lines[header_idx + 2 :]:
        if not line.startswith("|"):
            break
        rows += 1
        cells = line.split("|")
        cell = cells[col] if col < len(cells) else ""
        # 里程碑号可能写在"关闭条件"列里（那是说明，不是状态）——本判据只看缺口格。
        for k in done:
            if re.search(rf"(^|[^0-9A-Za-z])M{k}([^0-9]|$)", cell):
                stale.append(f"plan/06 缺口列仍提 M{k}: {cell.strip()}")
    add(
        "LAYOUT.GAPS",
        not stale,
        "；".join(stale) if stale else f"plan/06 缺口列扫了 {rows} 行，无已 ✅ 里程碑",
    )


def check_ledger(done: list[int]) -> None:
    """承诺-证据台账是**第四份**状态副本，且不在"状态表"里（表头不同）。"""

    lines = (read("plan/00-README总览.md") or "").split("\n")
    header_idx = next(
        (
            i
            for i, line in enumerate(lines)
            if line.startswith("|") and "承诺" in line and "状态" in line
        ),
        -1,
    )
    if header_idx < 0:
        add("LAYOUT.LEDGER", False, "plan/00 找不到『承诺-证据台账』表头（承诺项与状态列）")
        return
    SCANNED["copies"] += 1
    bad: list[str] = []
    rows = 0
    for line in lines[header_idx + 2 :]:
        if not line.startswith("|"):
            break
        rows += 1
        cells = [c.strip() for c in line.split("|")]
        status = cells[-2] if len(cells) >= 2 else ""
        if not re.search(r"[⬜🟡]|未开始|待 M\d|待开工", status):
            continue
        for k in done:
            if re.search(rf"(^|[^0-9A-Za-z])M{k}([^0-9]|$)", status, re.I):
                bad.append(f"台账行仍挂未完成: {status[:60]}")
    add(
        "LAYOUT.LEDGER",
        not bad and rows > 0,
        "台账表 0 行——判据空跑"
        if rows == 0
        else ("；".join(bad) if bad else f"台账 {rows} 行，已成 ✅ 的里程碑无未完成标记"),
    )


def check_release_doc(done: list[int], all_milestones: list[int]) -> None:
    release = RELEASE_MILESTONE or max(all_milestones or [0])
    if release == 0 or release not in done:
        add(
            "LAYOUT.RELEASE",
            True,
            f"发布里程碑 M{release} 未完成，收尾记录尚不适用（已扫 {len(done)} 个 ✅ 里程碑）",
        )
        return
    text = read(f"plan/RELEASE-M{release}.md")
    wrapup = read(f"plan/WRAPUP-M{release}.md")
    if text is None and wrapup is None:
        add("LAYOUT.RELEASE", False, f"缺 plan/RELEASE-M{release}.md 或 plan/WRAPUP-M{release}.md")
        return
    if text is not None:
        cols = bool(re.search(r"^##\s*一、tag 前事实", text, re.M)) and bool(
            re.search(r"^##\s*二、tag 后追加", text, re.M)
        )
        heading = bool(re.search(r"^#{2,3}.*覆盖对账", text, re.M))
        rows = len(re.findall(r"^\|.*(实现|不适用|待首推).*\|$", text, re.M))
        add(
            "LAYOUT.RELEASE",
            cols and heading and rows >= 3,
            f"两栏:{cols} 覆盖对账小节:{heading} 三态行数:{rows}",
        )
        return
    add("LAYOUT.RELEASE", True, "WRAPUP 形态")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="check_sprint_layout", add_help=False)
    parser.add_argument("--selftest", action="store_true")
    ns, unknown = parser.parse_known_args(argv)
    if unknown:
        sys.stderr.write(f"check_sprint_layout: 未知参数 {unknown}\n")
        return 2
    if ns.selftest:
        # 门自身的非空跑自证：少一份必备件必须红（CI 里跑这条，防门被悄悄改空）
        text = read("plan/06-交付对标与决策.md")
        if text is None:
            print("selftest FAIL  缺少可证伪对象 plan/06-交付对标与决策.md")
            return 1
        print("selftest OK  锚点文件在位（完整变异验证见 plan/05 §3.1）")
        return 0
    return run()


def run() -> int:
    steps = [
        check_required_files,
        check_binding_head,
        check_sections,
        check_documented_tools_exist,
    ]
    for step in steps:
        try:
            step()
        except Exception as exc:  # 门永不崩：被检查对象不存在时报 FAIL 并继续
            add(step.__name__, False, f"{exc.__class__.__name__}: {exc}")

    states = collect_states()
    done = sorted(k for k, s in states.items() if "done" in s)
    all_milestones = sorted(states)
    for step in (
        lambda: check_status_agreement(states),
        lambda: check_handoffs(done),
        lambda: check_next_handoff(done, all_milestones),
        lambda: check_stale_gaps(done),
        lambda: check_ledger(done),
        lambda: check_release_doc(done, all_milestones),
    ):
        try:
            step()
        except Exception as exc:
            add(getattr(step, "__name__", "step"), False, f"{exc.__class__.__name__}: {exc}")

    failed = [c for c in CHECKS if not c[1]]
    print("布局门（方法论装订） · 判据只落仓库内文件")
    print("=" * 56)
    for check_id, ok, detail in CHECKS:
        print(f"{'PASS' if ok else 'FAIL'}  {check_id}  {detail}")
    print("=" * 56)
    print(
        f"这轮扫到：文档 {SCANNED['docs']} / 交接单 {SCANNED['handoffs']} / "
        f"状态副本 {SCANNED['copies']} / 文档点名工具 {SCANNED['doc_tools']}"
    )
    print(f"结论: {'全绿' if not failed else f'{len(failed)} 项 FAIL'}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
