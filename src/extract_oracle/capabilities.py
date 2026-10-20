"""能力登记表：五模块的落地状态。

唯一用途 = 让 `check` 在判定层未就绪时**显式拒绝**（退出码 3），而不是产出空 findings。
模块落地时把对应 `implemented` 翻 True；翻的时候必须同提交补该模块的验收测试
（见 `plan/03` 的验收表与 `plan/HANDOFF-M<k>.md` 的 K 清单）。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Capability:
    name: str
    milestone: str
    rule_prefix: str
    implemented: bool = False


#: 与 `plan/01` §2 的五个模块编号一一对应（顺序即 module id 顺序）。
#:
#: 翻 True 的判据（K08）：同提交必须有该模块的验收测试。
#: - M2 翻 `structure`（验收在 `tests/test_structure_diff.py`：六个 fixture 各命中对应 code + `clean.zip` 零误报）；
#: - M3 翻 `fold`（验收在 `tests/test_fold.py`：`case.zip`/`norm.zip`/`trim.zip`/`filedir.zip` 分平台结论
#:   + 写序→存活者 + 8 组字符对回归 + 平台表 `sha256` 对账）；
#: - M4 翻 `accessibility`（验收在 `tests/test_accessibility.py`：`reserved.zip` 的 `CON.txt`/`NUL.txt`
#:   → `WRITTEN_UNREADABLE` 且三证据齐、`aux.tar.gz` → `OK`；`trailing.zip` 三条 → `WRITTEN_TRUNCATED`；
#:   `trim.zip` 两条 + 仍触发 `collision.TRIM`；`long_comp.zip` → `BLOCKED`；`clean.zip` 三平台全 `OK`）。
#: `encoding` 保持 False——M2 只做了骨架（原始字节 / bit11 / extra 解析），
#: `encoding.candidates[]` 与 `predictedNames` 在 M5，**骨架不冒充模块落地**。
MODULES: tuple[Capability, ...] = (
    Capability("structure", "M2", "structure.*", implemented=True),
    Capability("encoding", "M2/M5", "encoding.*"),
    Capability("fold", "M3", "collision.*", implemented=True),
    Capability("accessibility", "M4", "accessibility", implemented=True),
    Capability("container", "M5", "container.* / budget.*"),
)

#: `check` 产出完整报告所需的最小能力集合（顺序即报告中的固定顺序）。
CORE_MODULES: tuple[str, ...] = tuple(c.name for c in MODULES)


def missing_core() -> list[str]:
    """返回尚未实现的模块名（按 `CORE_MODULES` 顺序）。空列表 = 可以出报告。"""

    return [c.name for c in MODULES if not c.implemented]


__all__ = ["Capability", "MODULES", "CORE_MODULES", "missing_core"]
