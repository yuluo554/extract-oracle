# HANDOFF-M6 · 发布（下一棒交接单）

> 本文件由 M5 收尾轮撰写。库内一律相对路径；绝对路径只出现在用户侧启动命令里。
> 基线：`plan/00-README总览.md`（文档索引）｜口径：`data/README.md` §4（M5 新增 §4.12 / §4.13）｜里程碑：`plan/05` §二

## 1. 当前进度 + 证据（M5 已完成）

| 交付物 | 路径 | 证据 |
|---|---|---|
| MOD-2 收尾（编码推断 + `0x7075` 全量） | `src/extract_oracle/rules/encoding.py` | `tests/test_encoding.py` 37 条（候选顺序 K02 + 三档置信度 + `0x7075` 两种 CRC 结局 + `predictedNames` + 与 `data/tool-matrix/` **逐格对账**） |
| `candidates[]` / `preferred` / `confidence` / `effectiveName` | 同上（`check` 返回块） | `data/README.md` §4.12 是唯一表述；`tests/test_encoding.py::test_predictions_match_the_documented_truth` 逐 fixture 对真值 |
| 四工具落盘名模型 | `encoding.predict_names` + `CP850_TRANSLITERATION`（33 码点实测表） | `tests/test_encoding.py::test_single_entry_decode_layer_matches_the_measured_matrix`（8 份样本逐格）；`::test_multi_entry_..._as_a_set`（8 份多条目样本） |
| MOD-5 容器五条 | `src/extract_oracle/rules/container.py` | `tests/test_container.py` 20 条（四 mimetype fixture 各命中**恰好一条**且互不串报 + ODF `inferred` 用现造样本验证 + `UTF8_REQUIRED` 只对非 ASCII 报） |
| MOD-5 预算两条 | `src/extract_oracle/rules/budget.py` | `tests/test_budget.py` 16 条（两条各命中 + U12 预算告警非截断 + U19 按组件切 + Linux 字节 / Windows 码元 + 表缺时预算仍可判） |
| `encoding` / `container` 翻 True | `src/extract_oracle/capabilities.py` | **五模块全 True**；不带 `--module` 的 `check` 对 `clean.zip` 退 0 且三数组皆空 |
| M5 三个新输出面进报告 | `cli.py::ModuleResult` + `cmd_check`；`report.py`（文本面 + `schema 0.3`） | `tests/test_report_determinism.py`（含 M5 新增 6 条双跑 / 无路径 / 无时间戳）；`::test_text_render_includes_m5_summaries` |
| 能力门不再有静默跳过 | `tests/test_cli_contract.py` / `tests/test_accessibility.py` | `test_check_refuses_while_modules_missing` 已改成**正向断言**（五模块齐备 → `clean.zip` 退 0）；`--module` 的那条改用**注入未实现模块**证伪 |
| CI 加两个冒烟步 | `.github/workflows/ci.yml`（`Encoding smoke` / `Container and budget smoke`） | `yaml.safe_load` 2 job / 5+14 steps；**本地等价脚本实跑通过**（`encoding smoke OK` / `container and budget smoke OK`） |
| `docs/rules.md` 加 §八 | `docs/rules.md` | 新增 #16（四工具落盘名 = 实现选择）+ 反查表逐规则；§八 记三条依据核对与一处"不升级强度"的诚实边界 |
| M5 常驻断言总数 | `py -3.12 -m pytest` | **397 passed**（M4 收尾时为 306；其中 M5 三份新测试 73 条 = `test_encoding` 37 + `test_container` 20 + `test_budget` 16） |

**M5 的两处实测收窄（会改变 M6 写 `docs/divergence.md` 的写法）**：

1. **`7zip` / `libarchive` 不做字符集探测，按宿主 ANSI 码页解释名字**。实测：`norm.zip` 里
   **有效的 UTF-8 字节**（`café`，bit 11 未置位）被 7-Zip / bsdtar 按 GBK 解成 `cafe茅.txt` / `cafe虂.txt`；
   CP932 字节被解成 `担杮岅柤.txt`。所以模型是"按声明的码页解"（`encoding.ANSI_CODEC = "gbk"`），
   不是"它会猜"——`plan/03` §MOD-2 原写的"`7z` → 多编码猜测"**不成立**（M6 写 divergence 时别照抄）。
2. **`info-zip-unzip` 的落盘名与 bit 11 无关**（实测：置位/未置位同一份 UTF-8 字节给出**同一**结果），
   且走 **CP850 解码 + OEM→ANSI best-fit**（128 个高位字节逐字节对照，命中 95/128；CP437 只命中 50）。
   `unzip` 那条路径的 `source` 字段显式标 `cp850`。

## 2. 当前事实·状态不变量（下一棒动手前必须知道，否则一定踩）

1. **五模块全 True，`missing_core()` 现在恒为空**：`check` 不给 `--module` = 要求五模块齐备，
   **已齐备** → 出完整报告。`ReasonCode.CAPABILITY_MISSING` 的**两个**分支（缺模块 / 点名未落地）
   都还在，但正常路径走不到——所以它们的靶子改成了**注入式**（`tests/test_cli_contract.py`
   临时把 `capabilities.MODULES` 与 `cli.MODULES` 一起翻回 False）。**M6 不要把那两条删掉**。
2. **退码 `1` 仍是三条来源**：`findings` **或** `collisions` **或** `accessibility_count > 0`
   （K13，`data/README.md` §4.1）。M5 的 `encoding` / `container` / `budget` 都出 `Finding`，
   所以落在 `findings` 这条上——**没有**第四条。`summary.low_confidence_count` **不参与**退码
   （编码猜不准是"不确定"，不是"发现问题"）。
3. **`rules/` 之间不得互相 import（K10）**：`budget.*` 与 `container.*` 同属 `container` 模块，
   但**两个文件互不 import**——`cli._run_module` 各调一次再把 findings 拼起来。
   `_run_module` 现在返回 `ModuleResult`（具名 dataclass，五种形状），**加新形状就加字段**。
4. **判定层不得出现 `casefold` / `lower()` / `upper()`**（`tests/test_rule_boundaries.py`）。
   M5 的 `encoding.is_common_zone` 是该判据的**第三个实质靶子**（它本可以用 `.lower()` 蒙混）；
   `CP850_TRANSLITERATION` 是**实测数据表**（逐码点替换），不是近似规则。
5. **`precedent` 是必填且按规则固定**：`encoding.UPATH_CRC_MISMATCH` 与 `encoding.predictedNames.*`
   用 `encoding.PRECEDENTS`；`container.*` / `budget.*` 用各自的 `PRECEDENTS` 枚举。
   新增取值**同提交**改 `docs/rules.md` §二 反查表。
6. **`predictedNames` 只预言解码层**（`data/README.md` §4.12 已写明作用域边界）：
   7-Zip 的 `_` 前缀、`: `的 ADS 截断、尾随空格/点裁剪分别归 `accessibility` / `collision`。
   **不要**把平台改写塞进编码层（靶子 `tests/test_encoding.py::test_prediction_level_is_decode_only`）。
7. **`encoding[]` / `container` 两个顶层块在范围外是 `null` 而不是 `{}`**（§4.12 / §4.13）：
   "没查"与"查了没问题"是两件事（同 §4.11 的 `accessibility_levels`）。
8. **`Finding.sort_key` 现在是四项**（多了 `evidence` 的确定性序列化）：`budget.*` 会**按平台**
   各出一条 finding（同一组件在两个目标上都超限时前三项相同），排序键必须是**全序**（K09）。
9. **四份状态副本必须一起改**：`plan/00` 里程碑表、`plan/00` 承诺-证据台账、`plan/05` §二状态表、
   `README.md` 里程碑状态表。只改一处 → `LAYOUT.STATUS` / `LAYOUT.LEDGER` 红。
10. **一个 ✅ 里程碑 = 一份交接单 + 一份下一棒交接单**。M6 是**最后一个**里程碑，所以它收尾时
    `LAYOUT.HANDOFF_NEXT` 走"已是最后一个里程碑，无下一棒交接单要求"分支——**不需要** `HANDOFF-M7`。
11. **状态格必须是"恰好只含 ✅/⬜/🟡 的单元格"**；台账状态格里出现 `M<k>`（k 已 ✅）就红。
12. **`plan/06` 缺口表的缺口列里不得出现已 ✅ 的里程碑号**（`LAYOUT.GAPS`）。**M6 收尾时把
    "判定层未落地"整行也删掉**（M5 已关闭），并按 `plan/06` §三 的写法纪律**只描述不点名文件**。
13. **写盘只经 `report.write_atomic`**（`sort_keys=True` + `ensure_ascii=False` + LF + 尾换行）。
14. **`data/README.md` §N.M 引用必须有实物**（`tests/test_readme_commands.py::test_section_references_...`）：
   M5 新增了 §4.12 / §4.13，代码里的引用已对齐；M6 若加新节，同提交补。
15. **`schema_version` 已到 `0.3`**（`report.SCHEMA_VERSION`）：M2 加 `entries`/`names`、M4 加
   `entries[].accessibility`、M5 加 `encoding`/`container`。M6 若改报告形状要一起改。
16. **CI 现在是 5 + 14 steps**（M5 加了 `Encoding smoke` 与 `Container and budget smoke`）。
   新增冒烟步时保持"断言退出码"的写法，**不许** `|| true`。
17. **`budget.declared_platforms()` 恒空**：预算**不查平台表**，所以平台表缺失时 `--module container`
   仍出报告（不退 3）。**不要**把 `$UpCase` 表变成 `container` 模块的隐式依赖
   （靶子 `tests/test_budget.py::test_budget_works_without_platform_tables`）。
18. **`ANSI_CODEC` / `UNZIP_CODEC` 是环境事实**，不是规范：换宿主要重测并重写这两个常量
   （`docs/rules.md` §八 末段已写明"拿到逐格对得上 ≠ 拿到规范背书"）。
19. **`7z` 不在 PATH**（`C:\Program Files\7-Zip\7z.exe`）；`unzip` 在 Git for Windows 的 `/usr/bin/unzip`
   （`D:\program\Git\usr\bin\unzip.exe`）；`libarchive` 用 `C:\Windows\System32\tar.exe`（bsdtar 3.8.4）。
20. **Cygwin 的 `unzip` 不认 `-O` 选项**（实测 `-O cp437` → 退出码 10）。要复现名字转换只能
   造逐字节样本让它自己落盘（M5 就是这么做的：128 个目录，每个一个单字节名条目）。

## 3. 下一棒待办（M6 发布，做完即项目结束）

M6 的交付 = **发布面**，**不碰 M5 的判定面**（`src/` `scripts/` `data/fixtures` 在 tag 之后零差异）：

1. **`docs/divergence.md` 定稿**（`plan/00` §四 招牌动词表最后一项；`plan/06` §三 缺口的第 3 行）：
   以 `data/tool-matrix/` 的 22×4 格为原料，**每格附实测命令与输出节选**；按 `plan/01` §1.2 的
   三项差异化组织（双头差分 / 编码推断 + 0x7075 / 真实折叠表）。**必须**按本文件 §1 的两处
   实测收窄写（`7z` 不探测字符集、`unzip` 与 bit 11 无关）。
2. **版本定版**：`__version__` 从 `0.1.0` 提到实际发布版本（`plan/05` §四 第 2 步）；同提交
   重生成任何含版本指纹的样例（目前 fixture 不含版本串，核对一遍 `gen_fixtures.py --check`）。
3. **构建产物**：`py -3.12 scripts/build.py` → `dist/extract-oracle.exe`；在**仓库外的中立目录**
   跑一次原生冒烟（`--version` / `capabilities` / `inspect` / `check` 各一次）。
   **入口必须用 `scripts/entry.py`**（绝对导入），不能拿 `src/extract_oracle/__main__.py`。
   PyInstaller 产物含构建期时间戳 → **不承诺跨机构建逐字节一致**（`plan/05` §五 U5）。
4. **`plan/RELEASE-M6.md` 在 tag 之前落盘**（两栏：§一 tag 前事实 / §二 tag 后追加事实，
   + §三 阶段 7 出口门覆盖对账表）。**自指约束**：tag 树内**不得**写 tag OID 与本包 sha256 的字面值。
5. **推送与发布**：`py -3.12 tools/check_publish_ready.py` 必须全绿（**不提供 `--force`**）→
   `py -3.12 tools/bootstrap_remote.py --repo <owner>/<repo> --apply --wait-seconds 90` 建仓首推
   （判据 = **远端 sha == 本地 sha**，不是 `git push` 的退出码）→ `git tag -a` → `gh release create`
   附 `dist/extract-oracle.exe` + 确定性源码包，本地留副本并记 sha256。
6. **回填 CI 实跑**（`plan/05` §五 U1）：首推后把真实 run id 写进 `plan/05` §五 U1 与
   `plan/RELEASE-M6.md`；矩阵口径按实况记（v1.0.0 时为三平台 × Python 3.9/3.12；
   **v1.0.1 起抬到 3.12/3.13**，U9/U10 的结论不受影响）。
7. **收尾**（按 §6 checklist）：四份状态副本 M6 翻 ✅、`plan/06` 缺口表逐行关闭、
   `README.md` 去掉"待 M5/M6"措辞、`AGENTS.md` 与 `plan/00` 顶部状态行同步。
   **M6 是最后一个里程碑**：收尾只需把状态翻 ✅，**不需要**写 `HANDOFF-M7.md`
   （`LAYOUT.HANDOFF_NEXT` 会走"最后里程碑"分支）。

**M6 的三条硬约束**（`plan/00` §八，M1 立、一路有效）：① 不得用 casefold 近似任何折叠判定；
② 不得引"规范要求 LFH/CD 一致"；③ 不得下载任何真实归档。

## 4. 既定口径清单（K 编号，动了会打挂测试）

| 编号 | 约定 | 打挂什么 |
|---|---|---|
| K01 | 真值库不出现 `observed_*` 字段；键集合受白名单约束 | `tests/test_fixtures.py::test_truth_holds_input_and_expectation_only` |
| K02 | 候选编码顺序固定 UTF-8/CP437/GBK/CP932/CP949/CP1251 | `tests/test_encoding.py::test_candidate_order_is_the_frozen_one` |
| K03 | 全部写盘经 `report.write_atomic`（sort_keys + ensure_ascii=False + LF + 尾换行） | `tests/test_report_determinism.py` |
| K04 | `$UpCase` 表 `source` ∈ {`volume_read`,`host_probe`}；`sha256` 与本体一致 | `tests/test_m1_data.py` + `tests/test_fold.py` + `platforms --verify` |
| K05 | fixture DOS 时间恒 `1980-01-01 00:00` | `gen_fixtures.py --check` |
| K06 | 新 fixture **追加在末尾**，不改既有样本 | `tests/test_m1_data.py::test_new_fixtures_are_appended_after_m0_ones` |
| K07 | 退出码整数只在 `ExitCode`，映射只在 `EXIT_FOR_REASON` | `tests/test_cli_contract.py::test_exit_code_table_is_total` |
| K08 | `capabilities.MODULES[*].implemented` 是 `check` 的唯一门 | `tests/test_cli_contract.py`（**注入式**两条）+ 各模块自己的 `test_*_module_is_implemented` |
| K09 | 报告键序 / 数组序 / 编码 / 换行 | `tests/test_report_determinism.py`（含 M5 三个新输出面双跑） |
| K10 | 判定模块互不 import；`rules` 不得 import `cli`；不得用近似大小写 | `tests/test_rule_boundaries.py`（M5 加 `encoding.is_common_zone` 为第三个实质靶子） |
| K11 | 推送前 `check_publish_ready.py` 必须全绿；不提供 `--force` | `tests/test_publish_ready.py` |
| K12 | `bootstrap_remote.py` 默认 dry-run；推送成功判据 = 远端 sha == 本地 sha | 同上 + `plan/05` §四 第 0 步 |
| K13 | **三条**判定产出：`findings` / `collisions` / `accessibility_count`，任一非空即退 `1` | `data/README.md` §4.1；`tests/test_accessibility.py::test_exit_code_counts_accessibility_as_judgement_output`；**M5 的三个模块落 `findings` 这条，不加第四条** |
| K14 | `collisions` 四个数组（`names`/`onDiskNames`/`writeOrder`/`cdOffsets`）同长同序 | `data/README.md` §4.9；`tests/test_fold.py::test_collision_shape_has_no_absent_fields` |
| K15 | 判定报告**不含** `probed_at_utc` 与 `volume` | `data/README.md` §4.10；`tests/test_fold.py::test_probed_at_utc_is_not_a_judgement_input` |
| K16 | `entries[].accessibility` 的键集 = `level` / `reasons` / `evidence`；**只在范围内时出现** | `data/README.md` §4.11；`tests/test_accessibility.py::test_entries_carry_accessibility_only_when_module_in_scope` |
| K17 | `reasons[]` / `evidence[]` 两个词表封闭 | `tests/test_accessibility.py::test_judge_never_emits_unknown_reasons` |
| K18 | **M5 新增**：`encoding[]` / `container` 两块**只在范围内时出现**，范围外是 `null` | `data/README.md` §4.12 / §4.13；`tests/test_container.py::test_container_block_is_null_outside_module_scope`；`tests/test_report_determinism.py::test_container_block_is_null_outside_scope_and_encoding_too` |
| K19 | **M5 新增**：`predictedNames[*].rule` 是封闭词表（6 值）；`null` 名必带 `reason` | `data/README.md` §4.12；`tests/test_encoding.py::test_predictions_never_fabricate_a_name` |
| K20 | **M5 新增**：`container.kind` 三值封闭（`epub`/`odf`/`none`）；`none` = 不做容器检查 | `data/README.md` §4.13；`tests/test_container.py::test_clean_zip_is_not_a_container_and_has_no_container_findings` |
| K21 | **M5 新增**：`budget.*` 的 `evidence.kind` 区分 `portability_budget` / `platform_limit` | `data/README.md` §4.6；`tests/test_budget.py::test_path_over_260_is_a_budget_warning_not_a_local_truncation` |

## 5. 本机环境坑（只写实测过的，2026-10-21）

- `python` 是商店占位符 → 一律 `py -3.12`。本项目 `requires-python >= 3.12`（v1.0.1 起；v1.0.0 时为 `>= 3.9`，3.9 已于 2025-10 EOL）。
- 命令一律带 `PYTHONUTF8=1`，否则中文输出在某些控制台会炸。
- **跑测试要带 `PYTHONPATH=src`**（未 `pip install -e .` 时）；已安装则不需要。
- `7z` 不在 PATH：`C:\Program Files\7-Zip\7z.exe`；`unzip` 在 Git for Windows 的 `/usr/bin/unzip`
  （`D:\program\Git\usr\bin\unzip.exe`）；`libarchive` 用 `C:\Windows\System32\tar.exe`（bsdtar）。
- **`$TEMP%` 下的探测目录要先 `mkdir -p` 再 cd**：M5 踩过——`cd "$TEMP" && ...` 在目录不存在时
  会静默不切目录，样本落到仓库根（`git status` 里看见一堆 `.zip` 才发现）。
- **Git Bash 里 `/tmp` 与 `$TEMP` 不是同一处**：脚本写到 `/tmp/x.zip`，而从 Git Bash 起 Python 时
  它看到的是 `D:\tmp`（若存在）——**用 `$TEMP` 并显式 `cygpath` 对账**。
- 本机 Git Bash 里用 `grep`/`sed` 看中文 UTF-8 文件可能显示乱码——**那是控制台不是文件**。
- `gh` 已登录 `yuluo554`（keyring，HTTPS）；远端尚未创建，**首次 push 前先建仓**。
- **非提权会话打不开卷句柄**（`ERROR_ACCESS_DENIED` 5）→ `fetch_upcase --source volume-read` 会退 3。
  **M6 不需要重取表**。
- **`/tmp` 里有别人留下的 `inspect.py`**：在 `/tmp` 下跑本工具会劫持标准库 `inspect`
  （M5 实测：`import gen_fixtures` 抛 `AttributeError: module 'inspect' has no attribute 'get_annotations'`）。
  中立目录验证一律用**仓库外、无同名模块的任意目录**。
- **冻结态入口必须用 `scripts/entry.py`**（绝对导入），不能拿 `src/extract_oracle/__main__.py`。
- **探测脚本别落在仓库内**：临时脚本里有绝对路径会让发布就绪门 `P4.DESENSITIZED` 变红。探测一律在仓库外。
- **变异验证的锚点要先断言存在**：`assert old in text` 再替换。M1 踩过（全角字符没对上、替换静默失败、
  门照常绿）。M2–M5 的复跑都带这条断言。
- **平台表的 `label` 是中文**（`新加卷`）：断言它时用 UTF-8 读文件，别依赖控制台编码。
- **Cygwin 的 `unzip` 不认 `-O`**（退出码 10）：要复现它的名字转换只能造逐字节样本让它自己落盘。
- **`curl` 在本机对部分站点报 `CRYPT_E_REVOCATION_OFFLINE`**：加 `--ssl-no-revoke` 可绕过。
  `raw.githubusercontent.com` 走 `gh api -H "Accept: application/vnd.github.raw"` 更稳。

## 6. DoD 逐项 checklist（M6）

> **收尾状态（2026-10-23，v1.0.1 发布后逐项复核）**：十条全部成立。逐条给可复跑的证据；
> 其中第 3/6/10 条的最新值取自 **v1.0.1**（v1.0.0 的历史值仍在 `plan/RELEASE-M6.md` §二）。

- [x] `docs/divergence.md` 定稿：22×4 格每格有实测命令与输出节选；按 §1 的两处收窄写
      → 机器判据 `tests/test_m1_data.py`（数表格行正则）实测 **3 passed**（88 格一一对应）
- [x] `__version__` 定版；`gen_fixtures.py --check` 仍逐字节一致
      → `__version__ = "1.0.1"`（v1.0.0 时为 `1.0.0`）；`gen_fixtures.py --check` → 22/22 逐字节一致 exit 0
- [x] `py -3.12 scripts/build.py` 出 `dist/extract-oracle.exe`；仓库外中立目录原生冒烟四条命令通过
      → 自报 `extract-oracle 1.0.1`；中立目录 `--version` / `capabilities` / `platforms --verify` /
        `check` 全通（`platforms --verify` 退 0，平台表随包分发）
- [x] `plan/RELEASE-M6.md` **在 tag 之前**落盘（两栏 + §三 覆盖对账表，三态齐）；tag 树内不写 OID/sha 字面值
      → §一 零 OID/sha256 字面值；v1.0.1 的实值登记在 §二.2（tag 之后的追加提交）
- [x] `check_publish_ready.py` 全绿；`bootstrap_remote.py` 建仓首推成功（远端 sha == 本地 sha）
      → **9 条判据全绿**（v1.0.1 起含 P9，`--online` 时 PASS）；实测 `git rev-parse HEAD` ==
        `gh api …/commits/main --jq .sha`（两边都是 `400f45d`）
- [x] tag + `gh release create` 附产物；回下载件 sha256 对账 + 原生冒烟
      → `v1.0.1` 非 draft 非 prerelease、**Latest**、2 附件；回下载 `sha256sum -c` 两条 OK、
        `cmp` 逐字节一致、解包树 `pytest` **484 passed / 10 skipped**（该 skip 的是产物不在树里的 e2e）
- [x] `plan/05` §五 U1/U9/U10 回填真实 CI run 结果（或按实况记）
      → U1/U9/U10 均有结论行；**U10 的 3.9 通道已随 floor 抬到 3.12 而整条退出**（不再是"未验证"）
- [x] 四份状态副本 M6 翻 ✅；`plan/06` 缺口表逐行关闭（含"判定层未落地"整行删除）
      → `LAYOUT.STATUS 3 处副本 × 7 个里程碑 状态全一致`；`LAYOUT.GAPS 缺口列扫了 1 行，无已 ✅ 里程碑`；
        `LAYOUT.LEDGER 台账 18 行，已成 ✅ 的里程碑无未完成标记`
- [x] `README.md` / `AGENTS.md` / `plan/00` 顶部状态行同步；`pytest` 全绿；三门下全绿
      → 三处均写 `v1.0.1`；`pytest` **494 passed**；布局门 / 脱敏门 / 发布就绪门（9 条）全绿
- [x] M6 收尾：**无需** `HANDOFF-M7.md`（最后一个里程碑）；本地等价校验 vs CI 实跑按实况写
      → `LAYOUT.HANDOFF_NEXT 已是最后一个里程碑，无下一棒交接单要求`；CI 实跑台账在
        `plan/RELEASE-M6.md` §二（v1.0.0）与 §二.2（v1.0.1：main `39927313597` / tag `39927758433` /
        追加提交 `39928653627`，三条 success）

## 7. 关键命令速查

```bash
# 门（新对话第一件事）
py -3.12 tools/check_sprint_layout.py
py -3.12 tools/check_desensitized.py
py -3.12 tools/check_sprint_layout.py --selftest

# 发布就绪门（推 GitHub 之前必须绿）
py -3.12 tools/check_publish_ready.py
py -3.12 tools/check_publish_ready.py --allow-dirty   # 开发中允许未提交改动

# 数据面
py -3.12 tools/gen_fixtures.py            # 写盘
py -3.12 tools/gen_fixtures.py --check    # 两层断言，不写盘
py -3.12 tools/probe_tools.py             # 重跑四工具矩阵（M6 写 divergence 要用）
py -3.12 tools/probe_tools.py --check     # 只比对，不写盘

# 测试（未 pip install -e . 时要带 PYTHONPATH=src）
PYTHONPATH=src PYTHONUTF8=1 py -3.12 -m pytest
PYTHONPATH=src PYTHONUTF8=1 py -3.12 -m pytest tests/test_encoding.py -q
PYTHONPATH=src PYTHONUTF8=1 py -3.12 -m pytest tests/test_container.py tests/test_budget.py -q
ORACLE_REQUIRE_TOOLS=1 PYTHONPATH=src py -3.12 -m pytest tests/test_tool_behaviour.py -q

# 五模块齐备后的完整判定（需先 pip install -e .）
PYTHONPATH=src py -3.12 -m extract_oracle capabilities
PYTHONPATH=src py -3.12 -m extract_oracle check data/fixtures/clean.zip --target windows      # 期望 0
PYTHONPATH=src py -3.12 -m extract_oracle check data/fixtures/upath_badcrc.zip --target windows --module encoding
PYTHONPATH=src py -3.12 -m extract_oracle check data/fixtures/padding.epub --target windows --module container
PYTHONPATH=src py -3.12 -m extract_oracle check data/fixtures/long_comp.zip --target windows,linux --module container

# 建仓 + 首推 + 回读 CI（默认 dry-run，加 --apply 才真推）
py -3.12 tools/bootstrap_remote.py --repo <owner>/<repo>
py -3.12 tools/bootstrap_remote.py --repo <owner>/<repo> --apply --wait-seconds 90

# 打包
py -3.12 scripts/build.py

# 启动下一棒对话
/goal 读取 "<项目绝对路径>\plan\HANDOFF-M6.md" 继续完成任务
```