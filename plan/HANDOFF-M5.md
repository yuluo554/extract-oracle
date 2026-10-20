# HANDOFF-M5 · 容器约定与编码推断（下一棒交接单）

> 本文件由 M4 收尾轮撰写。库内一律相对路径；绝对路径只出现在用户侧启动命令里。
> 基线：`plan/00-README总览.md`（文档索引）｜口径：`data/README.md` §4（新增 §4.11）｜里程碑：`plan/05` §二

## 1. 当前进度 + 证据（M4 已完成）

| 交付物 | 路径 | 证据 |
|---|---|---|
| MOD-4 三级分级 + `reasons[]` / `evidence[]` | `src/extract_oracle/rules/access.py` | `tests/test_accessibility.py` 60 条（逐格分级表 + 两个封闭词表 + 报告面 + 退码 + 双跑） |
| `entries[].accessibility` 进 `check` 报告 | `src/extract_oracle/cli.py::_entry_facts` / `cmd_check` | `::test_entries_carry_accessibility_only_when_module_in_scope`、`::test_inspect_never_reports_accessibility` |
| `summary.accessibility_count` / `accessibility_levels` | `cli.py::cmd_check` | `::test_summary_counts_are_per_level_and_match_entries`、`::test_summary_accessibility_fields_are_null_outside_scope` |
| 文本面渲染分级计数 | `src/extract_oracle/report.py::render_text` + `ACCESS_LEVELS` | `::test_report_level_order_matches_rules`（两处枚举一致性） |
| `capabilities.accessibility` 翻 True | `src/extract_oracle/capabilities.py` | `::test_accessibility_module_is_implemented` + `::test_accessibility_module_is_dispatchable_from_cli` |
| 三平台各自可断言 | `rules/access.py::check` 返 `{index: {platform: verdict}}` | `::test_targets_are_independently_assertable` |
| `docs/rules.md` 定稿 | `docs/rules.md` | 15 行全部直引（5 行回填 + 新增 #15）；反查表**逐规则一个 `#` 行号**；§五 记两处出处更正 |
| CI 分级冒烟 | `.github/workflows/ci.yml`（`Accessibility smoke`，12 steps） | `yaml.safe_load` 2 job / 5+12 steps；**本地等价脚本实跑通过**（`accessibility smoke OK`） |
| M4 常驻断言总数 | `py -3.12 -m pytest` | **306 passed**（M3 收尾时为 240；其中 `tests/test_accessibility.py` 60 条） |

**M4 的四处实测收窄（会改变 M5 的写法，尤其第 3 条）**：

1. **上标 ¹²³ 变体不算保留名**（`plan/05` §五 U17）。`CreateFileW('COM¹.txt')`/`'COM².txt'`/`'LPT³.log'`
   创建成功、`Test-Path=True`、`Get-Content` 读得到。MS Learn 的 `echo test > COM¹` 失败是 **CMD 走设备命名空间**；
   提取器走 Win32 文件 API。**不要**为了"看起来更全"把它们加回保留名集合。
2. **`COM0`/`LPT0` 才是保留名，`COM10` 起不是**（U17）。MS Learn 的枚举从 1 起，机器从 0 起都拿不到。
3. **`/` 是路径分隔符，不是 Linux 的非法字符**（U19）。`plan/03` 原表第 2 步会让**每一份带子目录的归档**
   假报 `BLOCKED`；落地改为按组件判，只有**空组件**（`a//b`、`a/`、`/a`）才 `BLOCKED`。
   M5 写 `budget.*`（组件/路径长度）时**必须沿用"按组件切"的口径**，否则会与 MOD-4 的结论打架。
4. **保留名按裁剪后组件匹配，且优先于裁剪档**（U18）：`con.txt.` 落盘为 `con.txt`，而 `con.txt` 读不到 →
   级别取 `WRITTEN_UNREADABLE`，`reasons` 两条都留。

## 2. 当前事实·状态不变量（下一棒动手前必须知道，否则一定踩）

1. **`check` 的默认语义没变**：不给 `--module` = 要求五模块齐备，**缺两个即退 3**（现在缺 `encoding` / `container`）。
   点名未落地模块照样退 3（收窄 ≠ 豁免）。
2. **退码 `1` 现在有三条来源**（K13 扩了第三条）：`findings` **或** `collisions` **或** `accessibility_count > 0`。
   改退码逻辑时三条要一起想（`data/README.md` §4.1）。M5 若给 `container`/`budget` 也出 `Finding`，
   它们落在 `findings` 这条上，**不需要**第四条。
3. **`capabilities` 是 `check` 的唯一门（K08）**：M5 翻 `encoding` / `container` 之前必须同提交补验收测试。
4. **`rules/` 之间不得互相 import（K10）**：`_run_module` 现在返回**三个**值
   `(findings, collisions, accessibility)`；M5 若产出第四种形状，同提交扩这个元组并在 `cmd_check` 里接上。
5. **判定层不得出现 `casefold` / `lower()` / `upper()`**（`tests/test_rule_boundaries.py`）。
   M5 做编码推断时**尤其注意**：候选顺序是 UTF-8/CP437/GBK/CP932/CP949/CP1251，走 `codecs` 解码，
   不要用任何大小写转换做"近似匹配"。
6. **`precedent` 只对 MOD-1 必填**；`accessibility` 与 `collision` 用各自的机读依据
   （MOD-4 是 `reasons[]` + `evidence[]`，不是 `evidence_strength`）。M5 的 `container.*` / `budget.*`
   是 `Finding`，**可以**带 `precedent`（每条规则一个出处，`docs/rules.md` §二 已给到逐规则行号）。
7. **三级可访问性的定义只在 `data/README.md` §4.2**，形状只在 §4.11。M5 不要另写第二份。
8. **四份状态副本必须一起改**：`plan/00` 里程碑表、`plan/00` 承诺-证据台账、`plan/05` §二状态表、
   `README.md` 里程碑状态表。只改一处 → `LAYOUT.STATUS` / `LAYOUT.LEDGER` 红。
9. **一个 ✅ 里程碑 = 一份交接单 + 一份下一棒交接单**。M5 收尾要写 `HANDOFF-M6.md`。
10. **状态格必须是"恰好只含 ✅/⬜/🟡 的单元格"**；台账状态格里出现 `M<k>`（k 已 ✅）就红。
    **M4 现在已 ✅ → 台账里不得再出现"待 M4"。**
11. **`plan/06` 缺口列里不得出现已 ✅ 的里程碑号**（`LAYOUT.GAPS`）。M4 已把"判定层未落地"行改成
    `M5`、把"规则原句未逐条整理"整行删掉（已关闭，证据写进表下的"已关闭"段）。**M5 收尾时把
    "判定层未落地"整行也删掉**（那时五模块齐备）。
12. **写盘只经 `report.write_atomic`**（`sort_keys=True` + `ensure_ascii=False` + LF + 尾换行）。
13. **展示形是 `backslashreplace` 不是 `surrogateescape`**：`rules/*` 内部比较可以用 `surrogateescape`
    （`fold._as_text`、`access._as_text`），但**报告输出面不得用**。
14. **判定用的字符串必须能喂给 `encode("utf-16-le")`**：M4 踩过——`surrogateescape` 产生的孤立代理项
    在 `utf-16-le` 下抛 `UnicodeEncodeError`，要用 `surrogatepass`（`access._utf16_units`）。
    M5 做字节口径的长度判定时同理：**按字节就按字节**，别中途 `encode()` 成 UTF-16。
15. **`data/fixtures/truth/*.json` 的键集合受白名单约束**（`tests/test_fixtures.py::ALLOWED_TRUTH_KEYS`）。
    现有键：`fixture` / `expected_findings` / `expected_collisions` / `expected_accessibility` /
    `expected_encoding` / `expected_names` / `note`。M5 的 `expected_encoding` 与 `expected_names` 已可用。
16. **平台表缺失/被换 → 退 3**：`platforms.load()` 的校验顺序固定。M5 的 `budget.*` 若需要平台表
    （Windows 组件口径），**同提交**把 `access` 的那条 `needs_tables` 分支扩成三模块，别复制一份加载逻辑。
17. **`ORACLE_PLATFORM_DIR` 是权威覆盖**：测试里改它要 `monkeypatch`，同时 `chdir`。
18. **工具缺失不许 skip 成假绿**：CI 设 `ORACLE_REQUIRE_TOOLS=1`，别把那个变量摘掉。
19. **`7z` 不在 PATH**（`C:\Program Files\7-Zip\7z.exe`）；`unzip` 在 Git for Windows 的 `/usr/bin/unzip`；
    `libarchive` 用 `C:\Windows\System32\tar.exe`（bsdtar 3.8.4）。
20. **CI 现在是 5 + 12 steps**（M4 加了 `Accessibility smoke`）。新增冒烟步时保持"断言退出码"的写法，
    不许 `|| true`。

## 3. 下一棒待办（M5 容器与编码，做完 MOD-5 + MOD-2 收尾）

M5 的交付，**不碰 M6 的发布面**：

1. **`rules/encoding.py` 补完推断**（MOD-2 收尾）：候选顺序固定 UTF-8/CP437/GBK/CP932/CP949/CP1251；
   置信度 `high` / `medium` / `low` 按 `data/README.md` §4.4；`0x7075` CRC 有效 → 覆盖且 `high`，
   失配 → 失效 + 降级 `low` + `encoding.UPATH_CRC_MISMATCH`。
   验收：`zh_gbk.zip` 三提取器预测互不相同；`upath.zip` 四工具一致 `café.txt`；`upath_badcrc.zip` 四方分歧。
2. **`rules/container.py`（MOD-5 五条）**：`container.MIMETYPE_NOT_FIRST` / `MIMETYPE_COMPRESSED` /
   `MIMETYPE_EXTRA` / `MIMETYPE_PADDING`（ODF 上下文带 `inferred: true`）/ `UTF8_REQUIRED`。
   验收：四 mimetype fixture 各命中一 code；`clean.zip` 零误报。
3. **`rules/budget.py`（`budget.*`）**：`PATH_OVER_260`（**预算告警**，不是本机截断——`plan/05` §五 U12）、
   `COMPONENT_OVER_255`。**按组件切的口径与 MOD-4 一致**（U19），Linux 侧按字节（POSIX `{NAME_MAX}`，
   `docs/rules.md` #15）。
4. **`capabilities.encoding` / `container` 翻 True**：同提交补 `tests/test_encoding.py` / `test_container.py` /
   `test_budget.py`（`plan/06` §二 点名的三份靶子）。
5. **确定性导出收尾**（`plan/06` §二 的"确定性导出"行仍是"骨架已通"）：把 M5 三个新输出面纳入
   `tests/test_report_determinism.py` 的双跑比对，然后把该行改成 ✅。
6. **跑通"不给 `--module`"的完整 `check`**：五模块齐备后 `missing_core()` 为空，
   `tests/test_cli_contract.py::test_check_refuses_while_modules_missing` 会走 `pytest.skip` 分支——
   **同提交**把它改成"五模块齐备时 `clean.zip` 必须退 0 且三数组皆空"的正向断言，别让它变成静默跳过。

**M5 的三条硬约束**（`plan/00` §八）：① 不得用 casefold 近似任何折叠判定；
② 不得引"规范要求 LFH/CD 一致"；③ 不得下载任何真实归档。

## 4. 既定口径清单（K 编号，动了会打挂测试）

| 编号 | 约定 | 打挂什么 |
|---|---|---|
| K01 | 真值库不出现 `observed_*` 字段；键集合受白名单约束 | `tests/test_fixtures.py::test_truth_holds_input_and_expectation_only` |
| K02 | 候选编码顺序固定 UTF-8/CP437/GBK/CP932/CP949/CP1251 | M5 编码测试（顺序已在 `rules/encoding.py` 登记） |
| K03 | 全部写盘经 `report.write_atomic`（sort_keys + ensure_ascii=False + LF + 尾换行） | `tests/test_report_determinism.py` |
| K04 | `$UpCase` 表 `source` ∈ {`volume_read`,`host_probe`}；`sha256` 与本体一致 | `tests/test_m1_data.py` + `tests/test_fold.py` + `platforms --verify` |
| K05 | fixture DOS 时间恒 `1980-01-01 00:00` | `gen_fixtures.py --check` |
| K06 | 新 fixture **追加在末尾**，不改既有样本 | `tests/test_m1_data.py::test_new_fixtures_are_appended_after_m0_ones` |
| K07 | 退出码整数只在 `ExitCode`，映射只在 `EXIT_FOR_REASON` | `tests/test_cli_contract.py::test_exit_code_table_is_total` |
| K08 | `capabilities.MODULES[*].implemented` 是 `check` 的唯一门 | `tests/test_cli_contract.py::test_check_refuses_while_modules_missing` + `::test_check_module_scope_refuses_unimplemented_module` |
| K09 | 报告键序 / 数组序 / 编码 / 换行 | `tests/test_report_determinism.py`（含 M3/M4 新输出面双跑） |
| K10 | 判定模块互不 import；`rules` 不得 import `cli`；不得用近似大小写 | `tests/test_rule_boundaries.py`（**已变异验证可红**） |
| K11 | 推送前 `check_publish_ready.py` 必须全绿；不提供 `--force` | `tests/test_publish_ready.py` |
| K12 | `bootstrap_remote.py` 默认 dry-run；推送成功判据 = 远端 sha == 本地 sha | 同上 + `plan/05` §四 第 0 步 |
| K13 | **三条**判定产出：`findings` / `collisions` / `accessibility_count`，任一非空即退 `1` | `data/README.md` §4.1；`tests/test_accessibility.py::test_exit_code_counts_accessibility_as_judgement_output` |
| K14 | `collisions` 四个数组（`names`/`onDiskNames`/`writeOrder`/`cdOffsets`）同长同序 | `data/README.md` §4.9；`tests/test_fold.py::test_collision_shape_has_no_absent_fields` |
| K15 | 判定报告**不含** `probed_at_utc` 与 `volume` | `data/README.md` §4.10；`tests/test_fold.py::test_probed_at_utc_is_not_a_judgement_input` |
| K16 | `entries[].accessibility` 的键集 = `level` / `reasons` / `evidence`；**只在 `accessibility` 在范围内时出现** | `data/README.md` §4.11；`tests/test_accessibility.py::test_entries_carry_accessibility_only_when_module_in_scope` |
| K17 | `reasons[]` / `evidence[]` 两个词表封闭（新增取值同提交改 §4.11） | `tests/test_accessibility.py::test_judge_never_emits_unknown_reasons` |

## 5. 本机环境坑（只写实测过的，2026-10-21）

- `python` 是商店占位符 → 一律 `py -3.12`。本项目 `requires-python >= 3.9`。
- 命令一律带 `PYTHONUTF8=1`，否则中文输出在某些控制台会炸。
- **跑测试要带 `PYTHONPATH=src`**（未 `pip install -e .` 时）；已安装则不需要。
- `7z` 不在 PATH：`C:\Program Files\7-Zip\7z.exe`；`unzip` 在 Git for Windows 的 `/usr/bin/unzip`
  （`D:\program\Git\usr\bin\unzip.exe`）；`libarchive` 用 `C:\Windows\System32\tar.exe`（bsdtar）。
- 本机 Git Bash 里用 `grep`/`sed` 看中文 UTF-8 文件可能显示乱码——**那是控制台不是文件**。
- `gh` 已登录 `yuluo554`（keyring，HTTPS）；远端尚未创建，**首次 push 前先建仓**。
- **非提权会话打不开卷句柄**（`ERROR_ACCESS_DENIED` 5）→ `fetch_upcase --source volume-read` 会退 3。
  **M5 不需要重取表**。
- **`/tmp` 里有别人留下的 `inspect.py`**：在 `/tmp` 下跑本工具会劫持标准库 `inspect`。
  中立目录验证一律用**仓库外、无同名模块的任意目录**。
- **冻结态入口必须用 `scripts/entry.py`**（绝对导入），不能拿 `src/extract_oracle/__main__.py`。
- **探测脚本别落在仓库内**：临时脚本里有绝对路径会让发布就绪门 `P4.DESENSITIZED` 变红。探测一律在仓库外。
  M4 的保留名探测就放在 `%TEMP%` 下的 `mkdtemp()` 里（每个名字一个目录，避免相互干扰）。
- **变异验证的锚点要先断言存在**：`assert old in text` 再替换。M1 踩过（全角字符没对上、替换静默失败、门照常绿）。
  M2/M3/M4 的复跑都带这条断言。
- **平台表的 `label` 是中文**（`新加卷`）：断言它时用 UTF-8 读文件，别依赖控制台编码。
- **`CreateFileW` 探测要独占还是共享**：M4 首跑用 `dwShareMode=0` 后立刻 `open()`，被自己的锁挡住 →
  读不到任何文件、差点把 `CON.txt` 判成"可读"。**先 `CloseHandle` 再读**，或 `dwShareMode=7`。
- **`curl` 在本机对部分站点报 `CRYPT_E_REVOCATION_OFFLINE`**：加 `--ssl-no-revoke` 可绕过。
  `raw.githubusercontent.com` 走 `gh api -H "Accept: application/vnd.github.raw"` 更稳（M4 就是这么取到 APPNOTE 的）。

## 6. DoD 逐项 checklist（M5）

- [ ] `encoding.candidates[]` + `predictedNames`（候选顺序按 K02，置信度按 §4.4）
- [ ] `0x7075`：CRC 有效 → 覆盖 + `high`；失配 → 降级 `low` + `encoding.UPATH_CRC_MISMATCH`
- [ ] `container.*` 五条；`MIMETYPE_PADDING` 在 ODF 上下文带 `inferred: true`
- [ ] `budget.PATH_OVER_260` 是**预算告警**（U12）；`COMPONENT_OVER_255` 按组件（U19 口径）、Linux 按字节
- [ ] `zh_gbk.zip` / `upath.zip` / `upath_badcrc.zip` 预测与 `data/tool-matrix/` 实测一致
- [ ] 四 mimetype fixture 各命中一 code；`clean.zip` 五模块零误报
- [ ] `capabilities` 里 `encoding` / `container` 翻 True（同提交补三份验收测试）
- [ ] `py -3.12 -m pytest` 全绿；`test_check_refuses_while_modules_missing` 改成正向断言（别再 skip）
- [ ] 布局门 + 脱敏门 + 发布就绪门全绿；§3.1 五组弱形态按**六 ✅ 里程碑形态**再跑一次
- [ ] 四处状态副本 M5 翻 ✅；`plan/06` 的"判定层未落地"整行删掉；写 `plan/HANDOFF-M6.md`（七节）
- [ ] commit（+ 有远端则 push 等 CI 绿；无远端写"本地等价校验，CI 待首推验证"）

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
py -3.12 tools/probe_tools.py             # 重跑四工具矩阵（M5 对账编码预测时要用）
py -3.12 tools/probe_tools.py --check     # 只比对，不写盘

# 测试（未 pip install -e . 时要带 PYTHONPATH=src）
PYTHONPATH=src PYTHONUTF8=1 py -3.12 -m pytest
PYTHONPATH=src PYTHONUTF8=1 py -3.12 -m pytest tests/test_accessibility.py -q
PYTHONPATH=src PYTHONUTF8=1 py -3.12 -m pytest tests/test_encoding_skeleton.py -q
ORACLE_REQUIRE_TOOLS=1 PYTHONPATH=src py -3.12 -m pytest tests/test_tool_behaviour.py -q

# 骨架命令（需先 pip install -e .）
PYTHONPATH=src py -3.12 -m extract_oracle capabilities
PYTHONPATH=src py -3.12 -m extract_oracle platforms --verify
PYTHONPATH=src py -3.12 -m extract_oracle check data/fixtures/reserved.zip --target windows --module accessibility
PYTHONPATH=src py -3.12 -m extract_oracle check data/fixtures/long_comp.zip --target windows --module accessibility
PYTHONPATH=src py -3.12 -m extract_oracle check data/fixtures/clean.zip --target windows --module accessibility   # 期望 0
PYTHONPATH=src py -3.12 -m extract_oracle check data/fixtures/clean.zip --target windows                        # 期望 3（还缺两模块）

# 启动下一棒对话
/goal 读取 "<项目绝对路径>\plan\HANDOFF-M5.md" 继续完成任务
```
