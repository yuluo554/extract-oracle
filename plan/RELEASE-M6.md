# RELEASE-M6 · 发布留档（extract-oracle v1.0.0）

> **两栏结构**（布局门 `LAYOUT.RELEASE` 断言：两栏齐 + `§三 覆盖对账` 小节 + 三态行数 ≥ 3）：
> **`§一` = tag 前事实**——本文件在 **tag 之前**落盘，随 tag 树一起发布；
> **`§二` = tag 后追加事实**——tag 之后用**追加提交**登记。
>
> **自指约束（`plan/05` §四 末段）**：本文件**就在 tag 树里**，所以 `§一` 内**不得出现** tag 对象 OID /
> tag 指向的 commit / 本包与附件的 sha256 —— 写进去的那一刻就失效（写完这个动作本身又会改掉它）。
> 字面值只写进 **`§二`** 或 **Release 正文**。
> 判别 = **"我要写的这个值，是不是'对装着本文件的这棵树的摘要'？"**——是 → 挪到 `§二`。
> **`§二` 在 tag 树内是明示的占位骨架**（自指约束下的唯一自洽写法，见 `plan/05` §四 第 4 步），不是漏填。
>
> **三个状态 token 的语义**（`§三` 逐条用）：**实现** = 有门/有实测覆盖，贴命令与结果；
> **不适用** = 写具体理由（不是"暂不"/"后续"）；**待首推** = 无远端期间如实标注，首推后在 `§二` 回填。

---

## 一、tag 前事实

### 1.1 版本与口径

| 项 | 值 | 依据 |
|---|---|---|
| 版本 | **v1.0.0** | `src/extract_oracle/__init__.py` 的 `__version__`（**唯一真源**；`pyproject.toml` 走 `dynamic = ["version"]`，不写第二份） |
| tag 名 | **`v1.0.0`**（annotated） | 取值判据见 `plan/06` §四 决策 **D17**：`plan/00` §六 M6 DoD 遗留的 `v0.1.0` 与 `plan/05` §四 的 `1.0.0` 冲突，按"版本号声明的是**能力状态**"取 `1.0.0`，并把那处字面值同提交改齐 |
| 报告 schema | `0.3` | `report.SCHEMA_VERSION`（M2 加 `entries`/`names`、M4 加 `entries[].accessibility`、M5 加 `encoding`/`container`） |
| 口径单点 | `data/README.md` §4 | 退出码 / 三级可访问性 / 折叠来源 / 容器五条 / 长度预算 / 序列化契约 |

### 1.2 交付面定稿顺序（本地，全部实跑）

顺序按"**构建必须排在交付面定稿之后**"（否则随包文档与产物会各说一套）：

1. **交付面改动全部落定**：`src/extract_oracle/{__init__,cli}.py`（定版 + LF stdout）、
   `scripts/build.py`（`--add-data` 平台表 + 中立目录自检）、`data/fixtures` **未动**；
2. **重生成样例并复算**：`py -3.12 tools/gen_fixtures.py --check` → 22/22 逐字节一致（fixture 不含版本串，已核对）；
3. **全量测试**（含两个"缺失即失败"开关）：`ORACLE_REQUIRE_TOOLS=1 ORACLE_REQUIRE_ARTIFACT=1 … pytest`；
4. **构建产物**：`py -3.12 scripts/build.py --clean`；
5. **中立目录冒烟**：仓库外中立目录（无同名模块、无 `data/`）四条命令；
6. `docs/divergence.md` 定稿（22×4 格逐格命令 + 输出节选）。

### 1.3 本地等价校验证据（这组数字在**留档已入库**的那棵树上、提交前最后一次重跑时采集）

| 命令 | 结果 |
|---|---|
| `py -3.12 tools/check_sprint_layout.py` | 退出码 `0`，全绿：`这轮扫到：文档 10 / 交接单 6 / 状态副本 4 / 文档点名工具 7` |
| `py -3.12 tools/check_desensitized.py` | 退出码 `0`，`扫了 121 个文本文件，0 命中（豁免 tools/check_desensitized.py）` |
| `py -3.12 tools/check_publish_ready.py` | 退出码 `0`，**P1–P8 全绿**（提交后重跑：P2 扫 **139** 个跟踪文件无产物、P4 扫 114 个文本文件 0 命中；P7 干净树；P8 = `git bundle verify` 推送包自证） |
| `py -3.12 tools/gen_fixtures.py --check` | 退出码 `0`，22/22 重生成结果与盘上产物逐字节一致 |
| `py -3.12 tools/probe_tools.py --check` | 退出码 `0`，`22 份 fixture × 4 工具`；四工具自报版本与 `docs/divergence.md` §1.1 一致；`tools_agree = false` 的样本 **10** 份 |
| `PYTHONPATH=src … py -3.12 -m pytest` | **409 passed**（M5 收尾为 397；= 397 + 10 条交付态 e2e + 1 条 README 版本一致性 + 1 条"伪造 cp1252 控制台"） |
| 布局门自身的变异验证（M6 形态，**8 组**，在仓库副本里跑） | **8/8 拿到实跑红**、还原后全绿；`LAYOUT.RELEASE` 的三条判据（两栏 / 覆盖对账小节 / 缺档）**各自独立变红**（记录在 `plan/05` §三 3.1 的 M6 复跑记） |
| **CI 首推首轮**（六矩阵格 + 产物 job） | **红**——**五组缺陷全部照录、逐条定性、逐条修复**（明细在 `plan/05` §5.1：3.9 的 `write_text(newline=)`、子进程"最小环境"、cp1252 控制台崩、GitHub `bash -e` 吞掉期望退 1 的冒烟命令、`overlap.zip` 的平台/版本行为差异）。**没有一组是"平台差异导致的假红"** |
| **CI 收尾轮（tag 之后）** | 又经四轮：§5.2（版本分派判据写错）、§5.3（SIGPIPE 假红）、`import yaml` 收集期挂掉、Windows `which bash` 命中 WSL 启动器、3.9 上 `write_text(newline=)` **复发**。最后一轮 `a0fa03d` **8/8 全绿**（run `39536509454`）；台账与终止符见 `§二` |
| `py -3.12 scripts/build.py --clean` | 退出码 `0`；产物自报 `extract-oracle 1.0.0`；**第二条自检**在中立 cwd 里 `platforms --verify` 退 `0` |
| 中立目录四条命令（`--version` / `capabilities` / `inspect` / `check`） | 全通过：`--version` → 0；`capabilities` → 0（五模块 `implemented`）；`inspect clean.zip` → 0 且 `findings` 空；`check clean.zip --target windows` → 0 且三数组皆空；`check case.zip --target windows` → 1 且 `collision.CASEFOLD` / `survivor = README.TXT` / `evidenceStrength = table_simulated`；`check reserved.zip --target windows` → 1 且 `CON.txt` 三条证据齐、`aux.tar.gz` 为 `OK` |

> **门结论自变的处置**：上面这组数字在**留档本身写完之后**重测（留档会进扫描面，脱敏门的文件计数因此从 120 → 121）。
> 若提交后重跑与本节不符，以**提交后实测**为准并在 `§二` 登记——不就地美化。
> **另记一处本轮实测到的"瞬态断言"**（`tests/test_layout_gate.py::test_m10`）：它原先靠"仓库里**没有**
> `RELEASE-M6.md`"来表达缺档态，于是留档一落盘，**这条测试自己变红**——它测的是"任务还没做"，
> 不是门的模式语义。处置 = 在沙箱里**显式删掉**留档来构造缺件态（与项目进度解耦，见 `§三` E 组同名行）。

### 1.4 里程碑 DoD 推进状态（tag 树内的如实形态）

- **tag 树里 M6 仍是 ⬜**：`git tag` 打的是"发布动作开始"的那一刻，而 DoD 里的"Release 附产物"发生在
  tag **之后** → 按"**DoD 打勾只能在事实落地后**"，四份状态副本的 M6 翻 ✅ 归 `§二` 的追加提交。
- tag 树内已成立的部分：`docs/divergence.md` 定稿、版本定版、单文件可执行（含平台表随包分发）、
  本留档在 tag 前落盘（三件都可由 `§一` 的自检与 §三 的"实现"行独立复核）。

### 1.5 附件口径与命名（**不含 sha256**）

| 附件 | 口径 | 说明 |
|---|---|---|
| `extract-oracle.exe` | **构建产物本身** | PyInstaller onefile；**自带平台语义表**（`--add-data`）；含构建期 PE 时间戳 → **不承诺跨机构建逐字节一致**（`plan/05` §五 U5） |
| `extract-oracle-1.0.0.tar.gz` | **手工源码包** | 由 `git archive --format=tar --prefix=extract-oracle-1.0.0/ <tag> \| gzip -9n` 生成。**不用 GitHub 自动生成的 Source code 包**（后者的 sha256 本地复算不出来）。`gzip -9n` 去掉原始文件名与时间戳 → 同一 tag 重复生成逐字节一致 |

**两个"永不失效"的复验方法**（不依赖任何写死的值，因而不受自指约束）：

1. 从 tag 重新导出源码包 → 与下载件 `cmp` 逐字节一致；
2. 从 tag 树 `git clone --no-local --branch v1.0.0` → 重跑 `scripts/build.py` → 与下载的 `.exe` 比对
   **结构口径**（本机同机重建比对 sha256；换机构建只验"能跑 + 自报版本一致"，因为 PE 时间戳必然不同）。

### 1.6 本轮实测补上的两条缺陷（见 `plan/05` §五 U22/U23 与 `plan/06` §四 D18）

| 编号 | 症状 | 处置 |
|---|---|---|
| U22 | 产物**不带** `data/platforms/`：在仓库根跑因 `Path.cwd()/data/platforms` 兜底而"假装"通过，**换到中立目录立刻退 3** | `scripts/build.py` 加 `--add-data` 打进产物；加"中立 cwd 里 `platforms --verify` 必须退 0"的第二条产物自检；靶子 `tests/test_artifact_e2e.py::test_artifact_carries_the_platform_table` |
| U23 | Windows 上 `stdout` 被 `TextIOWrapper` 翻成 CRLF → `check x --format json > a.json` 与 `--out a.json` 给出**不同字节**，默认输出路径违反 `data/README.md` §4.8 / K09 的换行口径 | `cli._force_lf_stdout()` 只改换行翻译、不动编码；靶子 `::test_artifact_json_is_byte_stable_across_two_runs` |

> 两条都是**先被断言抓住、再修、再回归**——`tests/test_artifact_e2e.py` 是它们第一次跑就抓出来的。
> 写在这里是因为"产物本体已验"这条出口门要能证伪里程碑自述，而不只是贴一句"已验"。

---

## 二、tag 后追加事实

> **两段形态**（自指约束下的写法）：**本文件在 tag 树里的那一版，本节是列名固定、值留空的占位骨架**
> ——字面值只能在 tag **之后**的追加提交里登记（tag 树不变 → 附件字节不变 → 值不会失效）。
> 当前你读到的是 **tag 之后的那一笔追加提交**，所以下表**已经填上实值**。
> **不许**把下表的值搬回 tag 树那一版（那正是自指陷阱的复发形态）。

| 项 | 值 | 核对命令 |
|---|---|---|
| tag 名 / 类型 | `v1.0.0` / **annotated** | `git cat-file -t v1.0.0` → `tag` |
| tag 对象 OID | `6d11592c6d0fbc6755b6fa29bf31edc0ff967295` | `git rev-parse v1.0.0` |
| tag 指向的 commit | `806d074af15463c4f328fd3e77f452a3bfe464d2` | `git rev-parse v1.0.0^{commit}` |
| tagger 身份 / 邮箱 | `yuluo554 <282769740+yuluo554@users.noreply.github.com>`，`2026-10-21T01:18:23Z`（`+0800`） | `git cat-file tag v1.0.0`；邮箱为 **noreply**（脱敏面通过） |
| 远端 annotated tag 两端一致 | 本地 `6d11592c…` == 远端 `refs/tags/v1.0.0` 的 `object.sha` `6d11592c…`（**对象哈希一致**，不是只对 `^{commit}`） | `gh api repos/…/git/ref/tags/v1.0.0` |
| 附件清单与 sha256 | `sha256: 42797dc77dab297939879e78935455c4d6bda41d4c2a12868fc78af025cda36a  extract-oracle.exe`<br>`sha256: fc0e2de675f83d625737b3766b228630e7a00c5fb9390fa39aba136153a597a2  extract-oracle-1.0.0.tar.gz` | `sha256sum` 两条；**Release 正文同步登记同一组值** |
| 回下载对账 | `gh release download v1.0.0` 取回两件 → sha256 复算**与上表逐字节相同** → `cmp` 与本地留档件一致（两件都 `CMP OK`）→ 下载件在**中立目录**原生冒烟：`--version`=0 / `capabilities`=0（五模块 implemented）/ `inspect`=0 / `check clean.zip`=0 / `check case.zip`=**1**（`collision.CASEFOLD`、`survivor=README.TXT`、`table_simulated`）/ `platforms --verify`=0 | 见左列命令 |
| 源码包正证（不依赖写死值） | 从 tag 重新 `git archive --format=tar --prefix=extract-oracle-1.0.0/ v1.0.0 \| gzip -9n` → 与**下载件** `cmp` **逐字节一致** | 已在本地实跑（两次重导出也互相 `cmp` 一致） |
| 附件 vs tag 树（共有文件逐字节） | 下载的源码包解包树 vs **干净 tag 导出**：**共有 139 个文件、sha256 全等、两侧"仅一侧"集合均为空**（非空自证成立） | 见左列口径；**不用 `diff -r`**（两棵树本来不同构的判据修正） |
| 干净 clone 直跑（DoD ⑤） | `git clone --no-local --branch v1.0.0` → `--version` = `extract-oracle 1.0.0`；全量测试 **399 passed / 10 skipped**（跳过的是"产物不在树里"的交付态 e2e，设计如此）；布局门全绿 / 脱敏门 0 命中 / `gen_fixtures --check` 逐字节一致 | 已在干净 clone 里实跑 |
| 发布包实测（解包树跑 README 命令） | 解包源码包 → 在**解包目录之外**用 `python -m extract_oracle` 逐条跑：`--version` / `capabilities` / `inspect` / `check`（退 0）/ `platforms --verify` 全部通过；解包树里 `pytest` **399 passed / 10 skipped**；三门全绿；`check_publish_ready.py` 在无 `.git` 树里报**环境缺失退 3**（设计如此，见 `§三` A 组同条） | 已实跑 |
| **已发布窗口内发现的缺陷**（处置：**不重打 tag**，走追加提交 + 登记） | 收尾轮补 3.9 兼容守门时，用同一守门扫 `tools/` 抓到两处 `write_text(newline=…)`（`gen_fixtures.py` 的真值写盘、`fetch_upcase.py` 的 `meta.json` 写盘）。**这两处在 v1.0.0 的源码包里仍是旧写法**（tag 树里的 `tools/` 与追加提交后的不同）：`gen_fixtures.py --check`（只读路径）在 3.8 上照常通过，但**写盘路径在 3.9 及以下会 `TypeError`**——实测：解包发布包后在 3.8 上直接调写盘 → `TypeError: write_text() got an unexpected keyword argument 'newline'`。**影响面**：仅"用源码包重新生成 fixture / 重取 `$UpCase` 表"这一条开发侧路径，**产物（`.exe`）与五模块判定完全不受影响**（`src/` 零差异）。**为什么不重打**：tag 与两件附件的 sha256 已登记、Release 已发布；按"已发布窗口关闭后的缺陷处置"纪律，重写 tag 会让已登记的哈希全部失效，代价大于收益。**用户侧补救**：用 `main` 分支的 `tools/`（已修），或直接用发布包里现成的 `data/fixtures`（不需重生成） | 见左列；`main` 已修，`v1.0.0` 保留原样并在此登记 |
| CI run 台账（快照式，登记到 `a0fa03d` 为止） | 十轮，**逐条照录、首跑红不抹除**：<br>`c79752ee0222 main run=39523836893 failure`（首推首轮：五组缺陷）<br>`7289f3d6ce62 main run=39525539941 failure`（复跑轮：1 格，版本分派判据写错）<br>`806d074af154 main run=39526198978 **success**`（8/8）<br>`806d074af154 v1.0.0 run=39526542472 **success**`（tag run，同 sha 两条合法）<br>`a8f8d22b6e8a main run=39528483550 failure`（收尾轮：SIGPIPE 假红）<br>`780ac995bd3c main run=39530778380 failure`（`import yaml` 收集期挂掉）<br>`6712c99e9948 main run=39532019837 failure`（Windows `#!/bin/sh` = WSL 启动器）<br>`cb19855836a0 main run=39532879370 failure`（同一格：`which bash` 命中 WSL 启动器）<br>`93020437bdad main run=39534395052 failure`（3.9 上 `write_text(newline=)` 复发）<br>`a0fa03d46c7f main run=39536509454 **success**`（8/8 全绿）<br>`d986557ba72d main run=39537600306 **success**`（台账回填这笔，8/8 仍绿）<br>**终止符**：登记到 `d986557` 为止；其后纯文档提交恒 1 push = 1 run，是否仍绿看 GitHub 上该 sha 的 run，**不看本表行数** | `gh run list --json databaseId,headSha,event,headBranch,conclusion` |
| 未验证项回填 | `plan/05` §五 **U1**（已实跑，首轮红 → 逐格定性在 §5.1）、**U9**（Ubuntu/macOS 六格已实跑）、**U10**（3.9 通道已实跑，且**证伪过**两处写法）——三条全部关闭 | `plan/05` §五 同名行 |
| POST_TAG 声明 | "tag 之后只有追加类提交，`git log --oneline v1.0.0..HEAD` 可逐条核对；交付面（`src/` `scripts/` `data/fixtures`）**零差异**"——本笔提交即首条追加（`plan/` 与 `docs/` 面），交付面按 `git -c core.quotepath=false diff --name-only v1.0.0..HEAD -- src/ scripts/ data/fixtures` **为空** | 见左列命令 |

---

## 三、阶段 7 出口门覆盖对账

> 判据 = **"我这轮绿，覆盖了出口门的哪几条？剩下的那几条，是谁判定不适用的？"**
> 下表逐条给出归宿，**三态不许留空**。门目按 `ai-tool-project-sprint` SKILL.md §「阶段 7 出口门」原序（A–E）。

### A. 干净环境与本体复核

| 出口门 | 状态 | 证据 / 不适用理由 |
|---|---|---|
| 发布物本体已验（真下载 + 中立目录，能证伪里程碑自述） | 实现 | `§一` §1.3：中立目录四条命令 + 产物自报版本 + 中立 cwd `platforms --verify` 退 0；**回下载侧**在 `§二` 登记（`gh release download` → sha256 复算 + `cmp` + 原生冒烟） |
| 入仓工具在无 `.git` 树里也要能跑 | 实现 | 布局门 / 脱敏门 / `gen_fixtures.py` / `probe_tools.py` 只读仓库内文件、不读 git 元数据（`§一` §1.3 逐条实跑）。**例外并显式声明**：`check_publish_ready.py` 与 `bootstrap_remote.py` **刻意**依赖 git 元数据（P7/P8 与建仓），在无 `.git` 树里报**环境缺失退 3**——这是它们的设计定位（"能不能推"这件事本身以 git 仓库为前提），不是缺陷 |
| 发布包实测 = 把 README 的每条命令在解包树里真敲一遍，包括前置条件 | 实现 | ① **parser 反射对账常驻**：`tests/test_readme_commands.py` 抽出 README 代码块里的每条 `extract-oracle …` → 逐条 `parse_args` → 任一 exit 2 即红（含多值参数三形态：单值 / 重复旗标 / 逗号分隔）；② README 的"开发/安装/打包/建仓"三节在**本机**逐条真敲过（`§一` §1.2）；③ **tag 树解包**侧（`git clone --no-local --branch v1.0.0` → 逐条敲，含"前置条件 = 先 `pip install -e .`"）在 `§二` 登记 |
| tag 树内留档与 tag 自身事实是自指关系 → `§三` 必须写占位骨架 | 实现 | 本文件：`§一` **零** OID/sha256 字面值；`§二` 是明示占位骨架并写明约束（`§一` 头部与 `§二` 头部各一处，防下一棒"好心补上"） |
| 附件与 tag 树逐字节同源 | 实现 | 判据不用 `diff -r`（两棵树**本来不同构**：`git archive` 独有 `.gitignore`/`.github/`，而 sdist 才有 `PKG-INFO`/`*.egg-info`）。用两条正证，**都已在 `§二` 登记实值**：① **从 tag 重导出源码包 → `cmp` 下载件逐字节一致**（两次重导出互相也一致）；② **下载的源码包解包树 vs 干净 tag 导出：共有 139 个文件、sha256 全等、两侧「仅一侧」集合均为空**。`.exe` 侧只做**结构口径**比对（同机重建可比 sha256；换机构建因 PE 时间戳必然不同，见 U5） |
| 源码包要自足（`MANIFEST.in` 白名单覆盖数据目录；验证 = 解包 → 装 → 从解包目录之外跑 CLI） | 实现 | **不适用 sdist 那一半**（附件是 `git archive` 出的 tag 树快照，不是 `python -m build` 的 sdist，无 `MANIFEST.in`）。**自足性本身**实现：`git archive` 是 tag 树的**完全快照**（含 `src/` `data/` `pyproject.toml` `README.md` `docs/`），解包 → `pip install` → 从中立目录跑 CLI 的实测在 `§二` 登记 |
| 构建必须排在交付面定稿之后（README/pyproject 会进包） | 实现 | `§一` §1.2 的六步顺序：交付面落定 → 重生成样例 → 全量测试 → **构建** → 中立冒烟。README 状态行在**定版提交里就写对**（只写**版本 + 能力**，`v1.0.0` 由 `tests/test_readme_commands.py::test_readme_status_line_carries_the_current_version` 断言）；"是否已发布 / CI 是否绿"**不由随包 README 承载** |
| README 提到的附件名必须真在 Release 里 | 不适用 | README **不点名任何附件名**（无可推导之名，故无"产物名由 setuptools 规范化"那类风险）。附件名在 `§二` 登记后逐条核对存在 |
| 对外附带的样例产物要在中立示意目录生成 | 不适用 | 本项目附件不含"样例产物/配置来源"（无运行时绝对路径会随附件出行）：附件 = 一个自包含可执行 + tag 树源码快照。分发样本是 `data/fixtures/`（由 `struct.pack` 程序化生成、入库、逐字节可复算），不是"定稿后现生成"的产物 |
| 冻结态入口与产物命名（`.exe` vs POSIX） | 实现 | 入口固定为 `scripts/entry.py`（绝对导入薄壳），由 `tests/test_freeze_entry.py` 三条常驻断言钉住（不得用 `__main__.py`；构建脚本必须指向该入口；自检失败必须显式退 1）。产物命名 `extract-oracle.exe` / `extract-oracle` 由 `scripts/build.py` 按 `sys.platform` 决定 |

### B. 附件与校验和

| 出口门 | 状态 | 证据 / 不适用理由 |
|---|---|---|
| 发布附件口径 = 手工源码包而非 GitHub 自动 Source code 包；复核三步 | 实现 | 口径与生成命令见 `§一` §1.5（`git archive` + `gzip -9n`）；"真下载 → sha256 复算 + 与留档件 `cmp` → 与 tag 重导出件 `cmp`"三步在 `§二` 登记结果 |
| `diff -r` 是这条判据的错形态 | 实现 | 判据按修正口径设计：**共有文件逐个 sha256 相等** + **两个"仅一侧"集合逐项点名**（源码包侧独有 `PKG-INFO`/`*.egg-info`，`git archive` 侧独有 `.gitignore`/`.github/`）。`§一` §1.5 已把两棵树"本来不同构"写成前提 |
| 附件 sha256 只有两个不动点（tag 后追加提交 / Release 正文） | 实现 | `§一` **零**哈希字面值；登记位置 = `§二`（tag 后提交）+ Release 正文。**包内只写复验方法**（`§一` §1.5 的两条正证） |
| 判据的扫描面要限定到 tag 树那一半（`§二` 允许登记哈希） | 实现 | 本文件按此写成两栏：`§一`（进 tag 树的那一半）无哈希/OID；`§二`（tag 后追加）允许登记 |
| `SHA256SUMS` 的两种合法形态（`<hex>  <name>` / `<hex>  *<name>`） | 实现 | 本项目**不生成** `SHA256SUMS` 文件；`§二` 用 `sha256: <hex>  <name>` 逐行登记（三种合法形态之一），复核时以"重新计算并比对"为准，不依赖清单文件的文法 |

### C. tag 与留档时序

| 出口门 | 状态 | 证据 / 不适用理由 |
|---|---|---|
| 版本号"多处一致"要由机器断言，别靠手抄 | 实现 | 四处的落法：① `pyproject.toml` 走 `dynamic = ["version"]` + `attr = "extract_oracle.__version__"`（`check_publish_ready.py` P6 断言**无字面量版本**）；② 根模块声明 `__version__`；③ **产物自报** = `scripts/build.py` 自检 + `tests/test_artifact_e2e.py::test_artifact_version_is_the_single_source_of_truth`（断言 `extract-oracle {__version__}`）；④ **README 状态行**含 `v{__version__}`（`tests/test_readme_commands.py::test_readme_status_line_carries_the_current_version`）。tag 名与 Release 名 tag 后才存在 → 归 `§二` |
| 已发布窗口关闭后的缺陷处置（不重写 tag，走追加提交 + 登记） | 实现 | **本轮真出现了**：收尾轮用 3.9 兼容守门扫到 `tools/` 里两处 `write_text(newline=…)`，而它们**已在 v1.0.0 的源码包里**。处置按本条纪律执行——**不重打 tag**（已登记的 sha256 会全部失效），改为 `main` 上追加修复 + 在 `§二` 逐条登记（影响面、为什么不重打、用户侧补救都写了）。**判据是"缺陷落在哪一层"**：这次落在**开发侧工具**（不进 `.exe`、`src/` 零差异），所以不构成重发理由；若落在交付面（`src/`）就必须升版本号重发 |
| DoD 打勾只能在事实落地后 | 实现 | tag 树内四份状态副本的 **M6 = ⬜**（`§一` §1.4）；翻 ✅ 归 `§二` 的追加提交 |
| 随包 README 的状态行不要承载"发布到哪一步" | 实现 | 走模板给的第①条口径：README 状态行 = **版本 + 能力**（`v1.0.0 — M6 发布（五模块全部落地…）`），"是否已发布"交 Release 页与 `plan/`。**如实留档一处落后**：tag 树里的 `AGENTS.md` / `plan/00` 仍写着「未接远端，CI 待首推验证」——那是**tag 时点的真实状态**（当时确实未首推）；首推后由 tag 之后的追加提交更新，**不回填 tag 树** |
| 定版会改变"参与摘要的指纹字段" → 样例必须同轮重生成 | 实现 | 定版提交里重跑 `gen_fixtures.py --check` → 22/22 逐字节一致（`data/fixtures` 与 `data/tool-matrix/` 都**不含**工具版本串，核对过：矩阵带的是 `schema_version` 与四工具自报版本）。**唯一一处版本指纹在报告面**（`tool_version`），本项目**没有入仓的报告样例**（`tests/test_report_determinism.py` 用的是内存构造的 payload，且 `tool_version` 已改为读根模块）→ 无"已入仓样例摘要失效"这一类对象 |
| `POST_TAG` 的处置 = 声明 + 可核对，不是消除 WARN | 实现 | 声明写进 `§二`，并**按实况核对**：`git log --oneline v1.0.0..HEAD` 逐条可读；`git -c core.quotepath=false diff --name-only v1.0.0..HEAD -- src/ scripts/ data/fixtures` **为空**（交付面零差异）。本笔提交即首条追加（`plan/` + `docs/` 面），提交信息用「复盘 / 复跑轮修复 / 回填」这类语义词 |
| 发布门报红先看它读的是 tag 树还是工作树 | 不适用 | 本项目**没有**"读 tag 树"的发布门：`check_publish_ready.py` 只判**工作树 + 本地完整仓库**（P7/P8），并**刻意不进 CI**（浅克隆下 P7/P8 会翻转）；tag 侧事实由本留档 `§二` 手工登记，不经过门 |
| annotated tag 两端一致 = **对象哈希**一致 | 实现 | 本地 `git rev-parse v1.0.0` = `6d11592c…` == 远端 `refs/tags/v1.0.0` 的 `object.sha`（**不是** `^{commit}`：那个是 `806d074a…`）；tagger 与消息在 `§二` 逐项登记（邮箱为 noreply） |
| tag 之后只允许**非交付面**提交（拆两条判据） | 实现 | ① `POST_TAG_SCOPE`：改动集合 ⊆ 非交付面（`plan/` `tests/` `tools/` `docs/` `README` `AGENTS` `.github/`）；② `DELIVERABLE_UNCHANGED`：交付面前缀（`src/` `scripts/` `data/fixtures`）**零差异**。两条都在 `§二` 用 `git -c core.quotepath=false diff --name-only v1.0.0..HEAD` 逐行核对（`core.quotepath=false` 防中文路径八进制转义击穿白名单判定）。tag 树内已按此纪律冻结交付面 |

### D. CI 与对账

| 出口门 | 状态 | 证据 / 不适用理由 |
|---|---|---|
| push 数 = run 数对账（口径 = push 事件数；权威 = push 流水 ↔ `gh run list --json event,headBranch,headSha,conclusion`；写 sha 台账不写会自追的总数） | 实现 | 台账（本文件 `§二`）**已建**：首推 `event=push` 有 run 记录，**首轮结论 = 失败**，逐条定性见 `plan/05` §5.1（五组缺陷，无一为平台假红）；**首跑红照录不抹除**（DoD 纪律）。台账写成"快照式：登记到 `<sha>` 为止，其后纯文档提交恒 1 push = 1 run，是否仍绿看 GitHub 上该 sha 的 run" |
| 四矩阵同点全红 = CI 步骤接线缺陷非平台差异 | 实现 | 首轮**确实是"多点同红"**，按本条判定归因：①③④ 是测试/工作流自身缺陷（与平台无关），②是"最小环境传参"在 Windows 上的必然结果，⑤是真实的工具行为差异——**逐格定性写在 `plan/05` §5.1**，没有拿"平台差异"当挡箭牌 |
| 多平台冻结产物走 CI 原生构建 + 原生冒烟（PyInstaller 不能交叉编译） | 实现 | 新增 `single-file-artifact` job（`windows-latest` + Python 3.12）：`pip install -e ".[dev,build]"` → `scripts/build.py --clean` → `ORACLE_REQUIRE_ARTIFACT=1 pytest tests/test_artifact_e2e.py`。**只跑一个平台一个解释器**：产物不承诺跨机构建逐字节一致，要证的是"产物自洽可跑"；本机等价实跑已通过（`§一` §1.3）。**CI 侧已在首轮真跑**：该 job 第一次就红，抓出的正是 U23 的"编码"那一半（cp1252 控制台 ⇒ `UnicodeEncodeError` 崩进程），修复后按 `§二` 台账复跑 |
| CI 内联脚本优先落 `tools/` 脚本（heredoc 终止符 + 工作流文件 LF） | 实现 | 六个冒烟步是 `run: \|` 内联 bash，**不含 heredoc**（无终止符歧义）；工作流文件为 LF（`.gitattributes` 口径）。判定入口本身是交付态 CLI + `tools/` 里的门与生成器，没有"内联脚本里藏着唯一实现" |
| 每条已交付命令都要有一条离线 CI 冒烟 | 实现 | 四个子命令各有着落：`capabilities` / `inspect` → `Console script smoke`；`check` → 五个判定冒烟（structure / fold / accessibility / encoding / container+budget）；`platforms --verify` → `fold smoke` 末条；**产物形态** → 新 `single-file-artifact` job。台账见 `plan/05` §五 U1 |
| "能力缺失"的降级冒烟不许用 PATH 隔离伪造缺失 | 实现 | 本项目**不用 PATH 隔离**：`tests/test_cli_contract.py` 用**注入式**变异（把 `capabilities.MODULES` 与 `cli.MODULES` 一起翻回 False）证明"缺模块 → 退 3 且不产空 findings"；工具缺失侧用显式开关 `ORACLE_REQUIRE_TOOLS=1`（缺失即失败，不 skip 成假绿） |
| tag push 与 branch push 各一条 run（同 sha 两条合法，tag run 也必须绿） | 实现 | 同一 sha `806d074af154` 上两条 run：`branch=main run=39526198978 success` + `branch=v1.0.0 run=39526542472 success` —— **两条都绿**；台账与终止符在 `§二` |
| CI 检出形态会让"标注 tag 对象"整类不存在 | 实现 | **不把这类推到 CI**：tag 对象（tagger 邮箱属脱敏"提交元数据面"）在**本地**对账，结果写进 `§二`——这正是本条给的出路（"或在留档里如实写'本地验的'"） |
| 推送前先在本地解析 workflow 并断言 job/step 数 | 实现 | **3 job / 5 + 14 + 5 steps**（`gate` / `test` / `artifact`）。落地形态 = `tests/test_ci_smoke_scripts.py::test_workflow_has_the_expected_jobs_and_step_counts`，**只用标准库**按缩进做最小解析（`PyYAML` 不是本项目的依赖——CI 首跑实测：`import yaml` 让该测试模块在**收集期**就 `ModuleNotFoundError`，把整个 job 拖红）。另用 GitHub 的 `bash -e -o pipefail` **实跑**六个冒烟步（见 `plan/05` §5.3） |

### E. 门自身的纪律

| 出口门 | 状态 | 证据 / 不适用理由 |
|---|---|---|
| 发布终态自检门（离线 + `--online` 两模 + `--pre-tag` 第三模，刻意不进 CI） | 不适用 | 本项目**没有**独立的"发布终态自检门"脚本，对应角色分给两件已存在的实物：① `tools/check_publish_ready.py`（**可上传性** P1–P8，任何时候可跑、**刻意不进 CI**、11 组变异在 `tests/test_publish_ready.py`）；② 本留档 `§三` 这张覆盖对账表。因此"离线/在线两模"与 `--pre-tag` 模在本项目无对应对象 |
| 离线模式报 SKIP 不报 PASS | 不适用 | 上述门**不联网**（零网络是形态红线），没有"在线/离线两模"这一维；不存在把 SKIP 写成 PASS 的空间 |
| 门的结果会被"为满足它而写入的产物"改变（别把门结论写死在留档/HANDOFF） | 实现 | `§一` §1.3 的表头与脚注都写明"**这组数字是在留档已入库的那棵树上测的**"，并给出"提交后重跑、以实测为准、不就地美化"的处置；HANDOFF/计划侧对应的是 `plan/05` §五 U1 的"待首推 + 首推后回填"口径（不写死 run 数）。`LAYOUT.RELEASE` 的靶子本轮最后一次用**真实留档**跑（见 `plan/05` §3.1 M6 复跑记） |
| 门读"人写的文档"时，作者为读者写的样例行会被当成真值登记 | 不适用 | 本项目的门**不解析留档里的登记行**：`LAYOUT.RELEASE` 只数"含实现/不适用/待首推的行数"、只匹配两个标题小节；`check_publish_ready.py` 不读 `plan/` 的登记内容。故"样例行被登记"这一类无对象 |
| 门要自己数「这轮扫到了几个」 | 实现 | 三门的非空跑自证都进结论：布局门 `文档 10 / 交接单 6 / 状态副本 4 / 文档点名工具 7`；脱敏门 `扫了 120 个文本文件，0 命中（豁免 1 份）`；发布就绪门 `跟踪文件 136 / 判据 8` |
| `gh` 是原生程序，`/tmp/...` 路径它不认（`--notes-file` / 附件参数要 Windows 形态） | 实现 | **实测踩到两次**：① `gh release download --dir <MSYS 形态路径>` 失败并报 `failed to run git: fatal: not a git repository`（它把该路径当仓库解析）；处置 = 从**仓库根**发起并给原生路径。② `gh release create` 的 `--notes-file` 与两个附件参数一律给**原生 Windows 形态**（`D:/…`），创建成功并回显 URL。两条都写进 `AGENTS.md` 环境事实（与「`/tmp` 与 `$TEMP` 不是同一处」同族） |
| 常驻测试要能"构造缺件态"（否则测的是瞬态） | 实现 | 四处 seam：`tests/test_artifact_e2e.py` 的 `ORACLE_REQUIRE_ARTIFACT=1`（产物缺失 → 失败；不设 → 响亮 skip）；`tests/test_tool_behaviour.py` 的 `ORACLE_REQUIRE_TOOLS=1`；`tests/test_publish_ready.py` 用**临时 sandbox 仓库**构造"dist/ 被跟踪""`.gitignore` 规则被删"等缺件态；**本轮补的第四处** = `tests/test_layout_gate.py::test_m10`——它原先靠"仓库里**没有**留档"表达缺档态，留档一落盘**这条测试自己变红**（测的是"任务还没做"，不是门的模式语义），改为在沙箱里**显式删掉**留档并加"缺件态自证"断言（`§一` §1.3 脚注同一条） |
| 发布门的判据要按"真实发布动作序列"设计 | 实现 | `bootstrap_remote.py` 的判据 = **远端 sha == 本地 sha**（不是 `git push` 的退出码，K12）；`tests/test_publish_ready.py` 11 组变异按真实形态构造。**首推已按真实序列走通**（建仓 → 首推 → sha 对账），首轮随即暴露"`bootstrap_remote.py` 的 push 判据是对的、但**推送通路**在本机不可用"这一环境事实（见下条），处置见 `§二` |
| "发布未达成"与"环境缺失"必须是两个退出码语义 | 实现 | `check_publish_ready.py`：`0` 全绿 / `1` 有 FAIL / `3` 非 git 工作树或无 git 可执行。`bootstrap_remote.py` 同族（缺 `gh`/未登录 = 环境缺失；远端 sha 不符 = 未达成）。两者都不把"事情没做完"报成"这台机器做不了" |
| 新增/改写的守门要做一次变异验证（含九形态假门族） | 实现 | 布局门：M1–M5 各按当轮形态复跑、**M6 按"六 ✅ 里程碑 + 真实留档"复跑**（记录在 `plan/05` §三 3.1）；脱敏门 4 组、发布就绪门 11 组各在 `tests/` 里有常驻变异。**本轮新增/改写的门**：`scripts/build.py` 的第二条产物自检与 `tests/test_artifact_e2e.py` 的 10 条——前者当场抓住 U22（改前红）、后者当场抓住 U23（改前红），即"弄坏被测行为 → 门必须变红"的实证（记录在 `§一` §1.6） |

> **两条最常被跳过的出口门**（判定语义不虚高 / 新增改写守门做变异）在上表末两行；本表**没有留空的格子**，
> 凡"不适用"都写了**具体理由**（本项目形态为什么不涉及），凡"待首推"都写清了**在哪一节回填**。