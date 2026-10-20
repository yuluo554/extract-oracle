# extract-oracle · 归档提取预言机

> **Status: v0.1.0 — M0 骨架（判定层未落地）**｜方法论：`ai-tool-project-sprint`｜布局门：`py -3.12 tools/check_sprint_layout.py`

**现有工具只做"单条规则检查"或"字段转储"，没有一个输出"谁会写出什么名字、谁覆盖谁、哪个工具会拒绝"。**

`extract-oracle` 是**提取结果预言机**：输入一个 ZIP，逐条目预言它在 {Windows 资源管理器, Info-ZIP unzip,
7-Zip, libarchive, Python zipfile, macOS Finder, Linux} 上会变成什么名字、是否被覆盖、是否应用层不可见、
是否被拒绝。**提取预言机不是体检器。**

> ⚠️ **这不是空白市场**。2026-10-05 至 10-19 两周内至少有 4 个同题仓库（其中 2 个含 CI、pre-commit hook、
> Windows 右键菜单、HTML 报告）。本项目只押它们文档里**明写"不做"**的三处：双头差分与重叠检测、编码推断与
> Unicode path extra field、真实文件系统折叠表。详见 `plan/01-题目文档.md` §1.2 / §1.5。

## 为什么需要它

同一个归档，四个工具四种结果（本机实测，详见 `data/README.md` §1.3）：

| 情形 | Python `zipfile` | Info-ZIP `unzip` | 7-Zip |
|---|---|---|---|
| LFH 名 `allowed.txt` / CD 名 `evil.txt` | **`BadZipFile` 硬失败** | 写 `evil.txt` | 写 `allowed.txt`，报 `Errors: 1` |
| `Readme.txt` + `README.TXT` | 只剩 1 个（内容 `LOWER`） | 只剩 1 个（`LOWER`） | 只剩 1 个（`LOWER`） |
| `CON.txt` | 写出 | 写出 | 写出（但应用层拿不到） |

分歧发生在**读哪个头**、**用哪种编码解**、**目标文件系统怎么折叠**——三者都是实现选择，不是规范条文。

## 里程碑状态

| 里程碑 | 状态 | 内容 |
|---|---|---|
| M0 | ✅ | 计划套件 + 方法论装订 + 可运行骨架 |
| M1 | ⬜ | fixture 补全 + `$UpCase` 取表 + 四工具对照 |
| M2 | ⬜ | MOD-1 双头差分与重叠 |
| M3 | ⬜ | MOD-3 跨平台折叠（写序→存活者） |
| M4 | ⬜ | MOD-4 三级可访问性 |
| M5 | ⬜ | MOD-5 容器与预算 + MOD-2 收尾 |
| M6 | ⬜ | 发布（tag + Release 附产物） |

> 状态副本共 4 处（本表 / `plan/00` 里程碑表 / `plan/00` 承诺-证据台账 / `plan/05` 状态表），任一处单独改动
> 都会让布局门变红——这是设计如此。CI 状态：**未接远端，待首推验证**。

## 安装

```bash
py -3.12 -m pip install -e ".[dev]"
```

零运行时依赖。Python ≥ 3.9。

## 用法

```bash
# 结构事实（现在就能用，不是判定）
extract-oracle inspect some.zip

# 能力状态：五个模块各自落地了没
extract-oracle capabilities

# 判定入口（M2 起逐步可用；判定层未就绪时退出码 3，绝不产出空 findings）
extract-oracle check some.zip --target windows
extract-oracle check some.zip --target windows,macos --format json
```

## 退出码

| 码 | 语义 |
|---|---|
| 0 | 检查完成，无 finding |
| 1 | 检查完成，有 finding |
| 2 | 输入无法解析（非 ZIP / 无 EOCD / 读不了） |
| 3 | 口径或平台表缺失 / 判定模块未落地——**绝不静默退化为 0** |
| 4 | 用法错误 |

口径唯一真相源：`data/README.md` §4.1。

## 已知限制（诚实清单）

- **判定层未落地**：五模块自 M2 起逐个实现；当前 `check` 返回 3 是**设计语义**，不是故障。
- **macOS / Linux 落盘行为未实测**（本机只有 Windows）：这些判定输出标 `table_simulated`，不是 `measured`。
- **APFS 归一化依据为中硬**：来自逆向文档与实操观察，**非 Apple 官方规范**，输出标 `evidence_strength: medium`。
- **不做**：解压、zip slip / zip bomb / 恶意检测、安全打分、"该用哪个工具"的建议、GUI/Web 界面。
- **单文件可执行**在 M6 产出；PyInstaller 产物含构建期时间戳，**不承诺跨机构建逐字节一致**。

## 仓库结构

```
src/extract_oracle/   解析 / 平台表 / 折叠 / 报告（分层见 plan/02 §一）
tools/                gen_fixtures.py（程序化 fixture）+ 布局门 + 脱敏门
tests/                契约 / 确定性 / fixture 对账 / 门自身的变异验证
data/                 依据台账（README.md）+ fixtures + truth（M1 扩充）
docs/                 rules.md（规范原句，M4）/ divergence.md（四工具实测，M6）
plan/                 00–06 计划套件 + HANDOFF + RELEASE
scripts/              build.py（PyInstaller onefile）
```

## 开发

```bash
py -3.12 tools/check_sprint_layout.py     # 布局门（新对话第一件事）
py -3.12 tools/check_desensitized.py      # 脱敏门（发布前必跑，CI 同 job）
py -3.12 tools/gen_fixtures.py --check    # fixture 重生成逐字节一致
py -3.12 -m pytest
```

## License

MIT（见 `LICENSE`）。
