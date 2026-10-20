# HANDOFF-M3 · 跨平台折叠（下一棒交接单）

> 本文件由 M2 收尾轮撰写。库内一律相对路径；绝对路径只出现在用户侧启动命令里。
> 基线：`plan/00-README总览.md`（文档索引）｜口径：`data/README.md` §4｜里程碑：`plan/05` §二

## 1. 当前进度 + 证据（M2 已完成）

| 交付物 | 路径 | 证据 |
|---|---|---|
| 三层完整解析（EOCD / CD / LFH） | `src/extract_oracle/zip_reader.py` | `tests/test_cli_contract.py::test_inspect_reports_three_layers`；`EntryView` 含 `lfh_end`、两侧 flags/CRC/大小、两份 extra |
| MOD-1 六条规则 | `src/extract_oracle/rules/structure.py` | `tests/test_structure_diff.py`（16 条：六 fixture 各命中 + 零误报 + 误报控制 + 排序 + ZIP64） |
| MOD-2 骨架 | `src/extract_oracle/rules/encoding.py` | `tests/test_encoding_skeleton.py`（11 条：原始字节可逆 / bit11 / extra / `0x7075` CRC） |
| Finding 形状契约 | `src/extract_oracle/findings.py` | `Finding.to_dict()` + `sort_findings()`（`(cd_offset, ruleId)` 全序） |
| `capabilities.structure` 翻 True | `src/extract_oracle/capabilities.py` | `py -3.12 -m extract_oracle capabilities` → `structure … implemented` |
| 三工具行为断言 | `tests/test_tool_behaviour.py` | 本机 8 条全过（真跑 unzip / 7z / Python）；`ORACLE_REQUIRE_TOOLS=1` 时缺工具**失败**而非 skip |
| 矩阵结论固化 | `tests/test_m2_ci_assertions.py` | 13 条，任何 runner 都能跑（不依赖工具是否安装） |
| K10 AST 守门 | `tests/test_rule_boundaries.py` | 12 条；**已变异验证可红**（注入 `lower()` 与跨模块 import → 两条同时红） |
| CI 接入 | `.github/workflows/ci.yml` | 2 job / 5+10 steps；`yaml.safe_load` 解析通过；含工具安装与结构判定冒烟（断言退出码 0/1） |
| M2 常驻断言总数 | `py -3.12 -m pytest` | **181 passed**（M1 收尾时为 107） |

**M2 的关键实测结论（会改变 M3–M5 的判定口径）**：

1. **Python `zipfile` 在 `mismatch_name.zip` 上取 CD 名但拒绝**：`namelist()` = `['evil.txt']`（CD 名），
   `read()` 抛 `BadZipFile`。`data/tool-matrix` 记的 `written: []` 是 `-m zipfile -e` 整进程失败的口径，
   两者不矛盾（`plan/05` §五 U13）。
2. **7-Zip 也取 LFH**（`allowed.txt`，rc=2）。`PRECEDENTS` 枚举里没有 `7zip_reads_lfh`，
   所以它的读头选择只进 `evidence.readers`——**不要**为了它就地扩枚举（那是口径变更，要走 §4 流程）。
3. **`upath.zip` 四工具一致**写出 `café.txt`；分歧要用 `upath_badcrc.zip`（`plan/05` §五 U14）。
4. **`size_diverge` 上 Python 照收（rc=0）**，只有 `crc_diverge` 才抛 `BadZipFile`——
   "CRC 校验"与"大小校验"在 Python 里不是同一条路径。
5. **`overlap.zip` 的分歧方向是"一个拒绝、三个照解"**（不是四个都报错）。

## 2. 当前事实·状态不变量（下一棒动手前必须知道，否则一定踩）

1. **`check` 的默认语义没变**：不给 `--module` = 要求五模块齐备，缺一个即退 3。
   只有 `--module <name>` 才收窄范围；**点名未落地模块照样退 3**（收窄 ≠ 豁免）。
   报告里的 `modules` 字段是"本次范围"的唯一机读标记，M3 加 `fold` 时必须同提交把它加进 `_run_module`。
2. **`capabilities` 是 `check` 的唯一门（K08）**：M3 翻 `fold` 之前必须同提交补 `fold` 的验收测试，
   否则就是"翻了个没有靶子的门"。
3. **`rules/` 之间不得互相 import（K10）**：M3 的 `fold.py` 若需要 MOD-1/2 的输出，
   **不要** import 它们——按 `plan/02` §二 的设计，MOD-3 消费的是"名字集合"这个**纯数据结构**，
   由调用方（`cli.py`）组装后传入。共享形状一律放包根（`findings.py` 的先例）。
4. **判定层不得出现 `casefold` / `lower()` / `upper()`**：`tests/test_rule_boundaries.py` 会红。
   折叠只能来自 `data/platforms/ntfs-upcase.bin`（M1 已取，65536 项 × uint16-le）。
5. **`precedent` 只对 MOD-1 必填**；`collision.*` 用 `evidence_strength` 而非 `precedent`
   （`data/README.md` §4.7 的四个枚举值：`measured` / `table_simulated` / `medium` / `inferred`）。
   macOS 侧必须标 `medium`，**且正文要重复写"实现观察，非 Apple 官方规范"**（决策 ④）。
6. **四份状态副本必须一起改**：`plan/00` 里程碑表、`plan/00` 承诺-证据台账、`plan/05` §二状态表、
   `README.md` 里程碑状态表。只改一处 → `LAYOUT.STATUS` / `LAYOUT.LEDGER` 红。
7. **一个 ✅ 里程碑 = 一份交接单 + 一份下一棒交接单**。M3 收尾要写 `HANDOFF-M4.md`。
8. **状态格必须是"恰好只含 ✅/⬜/🟡 的单元格"**；台账状态格里出现 `M<k>`（k 已 ✅）就红。
   写"待 M5 回填"这种指向**未完成**里程碑的才安全。
9. **口径数值只在 `data/README.md` §4**。M2 新加的两条 reason → 码（`cd_unreadable`/`lfh_unreadable` → 2、
   `zip64_unsupported` → 3）已在 §4.1 留痕；M3 加 reason 要照做。
10. **写盘只经 `report.write_atomic`**（`sort_keys=True` + `ensure_ascii=False` + LF + 尾换行）。
11. **展示形是 `backslashreplace` 不是 `surrogateescape`**（M2 实测改的口径，`plan/03` §0 有记）：
    精确字节一律走 `*_hex` 字段，别指望展示形可逆。
12. **`data/fixtures/truth/*.json` 的键集合受白名单约束**（`tests/test_fixtures.py::ALLOWED_TRUTH_KEYS`）。
    M3 若需新键（例如 `expected_survivor`），**必须先改那个白名单**。
13. **`_summary.json` 是矩阵目录**：加 fixture 要重跑 `tools/probe_tools.py`，否则
    `tests/test_m2_ci_assertions.py::test_summary_lists_every_fixture` 红。
14. **工具缺失不许 skip 成假绿**：本地缺工具时 `test_tool_behaviour.py` 会 skip；CI 设
    `ORACLE_REQUIRE_TOOLS=1` 后缺工具**失败**。别把这个变量从 CI 摘掉。
15. **`7z` 不在 PATH**（`C:\Program Files\7-Zip\7z.exe`）；`unzip` 在 Git for Windows 的 `/usr/bin/unzip`；
    `libarchive` 用 `C:\Windows\System32\tar.exe`（bsdtar 3.8.4）。**GNU tar 会被误当 bsdtar**——
    `probe_tools._is_bsdtar()` 已做版本串校验。

## 3. 下一棒待办（M3 折叠，只做 MOD-3）

M3 的交付，**不碰 MOD-4/5**：

1. **平台表接入**（`plan/02` §四 的三条契约）：
   - 读 `data/platforms/ntfs-upcase.bin` + `meta.json`，**`sha256` 必须与本体逐字节对上**，
     对不上 = 表被换过 → `platform_table_missing`（退出码 3），**不静默使用**；
   - `source` 只能取 `volume_read` / `host_probe`（`casefold` 不是合法值）；
   - `probed_at_utc` **不进报告 digest**（否则跨机复跑必红）。
   - `platforms --verify` 从"永远退 3 的占位"变成真校验（打印表指纹 + 卷标识）。
2. **`rules/fold.py`（MOD-3 四条）**：`collision.FILEDIR` / `CASEFOLD` / `NFC` / `TRIM`。
   **判定顺序固定**：FILEDIR → CASEFOLD → NFC → TRIM（同一对可命中多条，全部输出）。
   - `windows`：**真实 `$UpCase` 表**，禁止 `casefold`/`lower()`（AST 守门会红）；
   - `macos`：UAX #15 + TN1150 + libfsapfs，输出 `evidence_strength: medium`；
   - `linux`：不做大小写折叠；`/` 不可出现；长度按**字节**判。
3. **写序 → 存活者**：`writeOrder` = CD 顺序；`survivor` = 最后写入者；
   `verdict` ∈ {`overwritten`, `renamed`, `skipped`}。`collisions` 按 `(min(cd_offset), code)` 升序。
4. **`capabilities.fold` 翻 True**：同提交补 `tests/test_fold.py`（否则 K08 的靶子是空的）。
5. **8 组字符对回归**：按 `docs/rules.md` §四 的**复核后**表写，**不要**按 `data/README.md` §1.3.3 的
   M0 原值（`İ/i` 与 `é/É` 两格 M0 记错，M1 已复核改正）。这条回归要同时证明
   "真表结果 = 卷实测" 与 "`casefold` 近似结果 ≠ 真表结果"。
6. **CLI 接线**：`_run_module` 加 `fold` 分支；`check --module fold` 可用；
   `--target` 三个平台各自的结论要能分开断言。

**M3 的三条硬约束**（`plan/00` §八）：① 不得用 casefold 近似任何折叠判定；
② 不得引"规范要求 LFH/CD 一致"；③ 不得下载任何真实归档。

## 4. 既定口径清单（K 编号，动了会打挂测试）

| 编号 | 约定 | 打挂什么 |
|---|---|---|
| K01 | 真值库不出现 `observed_*` 字段；键集合受白名单约束 | `tests/test_fixtures.py::test_truth_holds_input_and_expectation_only` |
| K02 | 候选编码顺序固定 UTF-8/CP437/GBK/CP932/CP949/CP1251 | M5 编码测试（M2 已在 `rules/encoding.py` 登记顺序） |
| K03 | 全部写盘经 `report.write_atomic`（sort_keys + ensure_ascii=False + LF + 尾换行） | `tests/test_report_determinism.py` |
| K04 | `$UpCase` 表 `source` ∈ {`volume_read`,`host_probe`}；`sha256` 与本体一致 | `tests/test_m1_data.py` + M3 的 `platforms --verify` |
| K05 | fixture DOS 时间恒 `1980-01-01 00:00` | `gen_fixtures.py --check` |
| K06 | 新 fixture **追加在末尾**，不改既有样本 | `tests/test_m1_data.py::test_new_fixtures_are_appended_after_m0_ones` |
| K07 | 退出码整数只在 `ExitCode`，映射只在 `EXIT_FOR_REASON` | `tests/test_cli_contract.py::test_exit_code_table_is_total` |
| K08 | `capabilities.MODULES[*].implemented` 是 `check` 的唯一门 | `tests/test_cli_contract.py::test_check_refuses_while_modules_missing` + `::test_check_module_scope_refuses_unimplemented_module` |
| K09 | 报告键序 / 数组序（`(cd_offset, ruleId)`）/ 编码 / 换行 | `tests/test_report_determinism.py`（含 M2 新输出面双跑） |
| K10 | 判定模块互不 import；`rules` 不得 import `cli`；不得用近似大小写 | `tests/test_rule_boundaries.py`（**已变异验证可红**） |
| K11 | 推送前 `check_publish_ready.py` 必须全绿；不提供 `--force` | `tests/test_publish_ready.py` |
| K12 | `bootstrap_remote.py` 默认 dry-run；推送成功判据 = 远端 sha == 本地 sha | 同上 + `plan/05` §四 第 0 步 |

## 5. 本机环境坑（只写实测过的，2026-10-21）

- `python` 是商店占位符 → 一律 `py -3.12`。本项目 `requires-python >= 3.9`。
- 命令一律带 `PYTHONUTF8=1`，否则中文输出在某些控制台会炸。
- **跑测试要带 `PYTHONPATH=src`**（未 `pip install -e .` 时）；已安装则不需要。
- `7z` 不在 PATH：`C:\Program Files\7-Zip\7z.exe`；`unzip` 在 Git for Windows 的 `/usr/bin/unzip`
  （`D:\program\Git\usr\bin\unzip.exe`）；`libarchive` 用 `C:\Windows\System32\tar.exe`（bsdtar）。
- 本机 Git Bash 里用 `grep`/`sed` 看中文 UTF-8 文件可能显示乱码——**那是控制台不是文件**。
- `gh` 已登录 `yuluo554`（keyring，HTTPS）；远端尚未创建，**首次 push 前先建仓**。
- **非提权会话打不开卷句柄**（`ERROR_ACCESS_DENIED` 5）→ `fetch_upcase --source volume-read` 会退 3，
  `host-probe` 是可用通道。
- **`/tmp` 里有别人留下的 `inspect.py`**：在 `/tmp` 下跑本工具会劫持标准库 `inspect`。
  中立目录验证一律用**仓库外、无同名模块的任意目录**。
- **冻结态入口必须用 `scripts/entry.py`**（绝对导入），不能拿 `src/extract_oracle/__main__.py`。
- **探测脚本别落在仓库内**：临时脚本里有绝对路径会让发布就绪门 `P4.DESENSITIZED` 变红。
  探测一律在仓库外。
- **变异验证的锚点要先断言存在**：`assert old in text` 再替换。M1 踩过（全角字符没对上、
  替换静默失败、门照常绿）。M2 的六组复跑都带这条断言。

## 6. DoD 逐项 checklist（M3）

- [ ] 平台表接入：`sha256` 对账、`source` 枚举、`probed_at_utc` 不进 digest
- [ ] `platforms --verify` 给出真指纹（不再是无条件退 3 的占位）
- [ ] MOD-3 四条规则全部落地，判定顺序固定 FILEDIR → CASEFOLD → NFC → TRIM
- [ ] `windows` 折叠走真实 `$UpCase` 表（AST 守门零命中 `casefold`/`lower()`/`upper()`）
- [ ] `case.zip --target windows` → 1 条 `CASEFOLD`，`survivor=README.TXT`；macos/linux 无 `CASEFOLD`
- [ ] `norm.zip --target windows` → **不得**报 NFC；`--target macos` → **必须**报 `collision.NFC`
- [ ] `trim.zip` → `collision.TRIM` + `survivor=readme`；`filedir.zip` → 三平台都报 `FILEDIR`
- [ ] 8 组字符对回归全通过，且与 `casefold` 近似结果**不同**
- [ ] `capabilities` 里 `fold` 翻 True（同提交补 `tests/test_fold.py`）
- [ ] `py -3.12 -m pytest` 全绿
- [ ] 布局门 + 脱敏门 + 发布就绪门全绿；§3.1 六组弱形态再跑一次（M2 已 5/6 拿到实跑红）
- [ ] 四处状态副本 M3 翻 ✅；写 `plan/HANDOFF-M4.md`（七节）
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

# 建仓 + 首推（默认 dry-run；--apply 才真推）
py -3.12 tools/bootstrap_remote.py --repo <owner>/<repo>
py -3.12 tools/bootstrap_remote.py --repo <owner>/<repo> --apply --wait-seconds 90

# 数据面
py -3.12 tools/gen_fixtures.py            # 写盘
py -3.12 tools/gen_fixtures.py --check    # 两层断言，不写盘
py -3.12 tools/fetch_upcase.py --source host-probe     # 重取表（带真实卷校验）
py -3.12 tools/probe_tools.py                          # 重跑四工具矩阵
py -3.12 tools/probe_tools.py --check                  # 只比对，不写盘

# 测试（未 pip install -e . 时要带 PYTHONPATH=src）
PYTHONPATH=src PYTHONUTF8=1 py -3.12 -m pytest
PYTHONPATH=src PYTHONUTF8=1 py -3.12 -m pytest tests/test_structure_diff.py tests/test_encoding_skeleton.py -q
ORACLE_REQUIRE_TOOLS=1 PYTHONPATH=src py -3.12 -m pytest tests/test_tool_behaviour.py -q

# 骨架命令（需先 pip install -e .）
PYTHONPATH=src py -3.12 -m extract_oracle inspect data/fixtures/upath.zip --format json
PYTHONPATH=src py -3.12 -m extract_oracle capabilities
PYTHONPATH=src py -3.12 -m extract_oracle check data/fixtures/mismatch_name.zip --target windows --module structure
PYTHONPATH=src py -3.12 -m extract_oracle check data/fixtures/clean.zip --target windows   # 期望退出码 3

# 启动下一棒对话
/goal 读取 "<项目绝对路径>\plan\HANDOFF-M3.md" 继续完成任务
```
