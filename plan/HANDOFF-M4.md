# HANDOFF-M4 · 可访问性分级（下一棒交接单）

> 本文件由 M3 收尾轮撰写。库内一律相对路径；绝对路径只出现在用户侧启动命令里。
> 基线：`plan/00-README总览.md`（文档索引）｜口径：`data/README.md` §4｜里程碑：`plan/05` §二

## 1. 当前进度 + 证据（M3 已完成）

| 交付物 | 路径 | 证据 |
|---|---|---|
| 平台表接入（`sha256` 对账 / `source` 枚举 / 两输出面分开） | `src/extract_oracle/platforms.py` | `tests/test_fold.py`（6 条：正向对账 + 篡改即拒 + 非法 `source` + 表缺 + `probed_at_utc` 不进报告 + 报告带表 sha256） |
| `platforms --verify` 真校验 | `src/extract_oracle/cli.py::cmd_platforms` | `tests/test_cli_contract.py::test_platforms_verify_reports_fingerprint`；实跑输出含 `entries=65536` / `sha256=41c26bc7a12bdaeb…` / `serial=445ED634` |
| `Collision` 形状 + 排序 | `src/extract_oracle/findings.py` | `Collision.to_dict()` + `sort_collisions()`（`(min(cd_offset), code)` 全序）；`test_fold.py::test_collision_shape_has_no_absent_fields` |
| MOD-3 四条规则 | `src/extract_oracle/rules/fold.py` | `tests/test_fold.py` 40 条（四规则分平台 + 真值逐条对账 + 判定顺序 + 跨规则不短路 + 零误报） |
| 写序 → 存活者 | 同上（`_pair_base` / `filedir_pairs`） | `case.zip` → `README.TXT`（`overwritten`）；`filedir.zip` → `a`（`skipped`，三平台一致） |
| `capabilities.fold` 翻 True | `src/extract_oracle/capabilities.py` | `test_fold.py::test_fold_module_is_implemented` + `::test_fold_module_is_dispatchable_from_cli` |
| CLI 接线 | `cli.py::_run_module` 的 `fold` 分支 + `collisions` 输出 + 退码含 collision | `test_fold.py::test_fold_targets_are_independently_assertable`、`::test_fold_entry_point_runs_in_subprocess` |
| CI 折叠冒烟 | `.github/workflows/ci.yml`（`Fold findings smoke`，11 steps） | `yaml.safe_load` 解析通过（2 job / 5+11 steps） |
| M3 常驻断言总数 | `py -3.12 -m pytest` | **227 passed**（M2 收尾时为 181） |

**M3 的四处口径决定（会改变 M4–M6 的判定口径）**：

1. **macOS 侧不报 `CASEFOLD`**（`plan/05` §五 U15）。libfsapfs 的观察是"**大小写不敏感卷**先 lower-case"
   ——折叠与否是**卷格式属性**，且 `meta.json` 没有 macOS 折叠表；`lower()` 近似违反决策 ③。
   所以 macOS 只报 `NFC`（`medium`）。**不要**为了"看起来更全"把它加回来。
2. **CASEFOLD 与 TRIM 是一个划分**：比较键都是 `trim(name)`，但"裁剪后逐字节相同"的对子**只归 TRIM**。
   写成两条独立计数会让 `trim.zip` 报两条（真值写的是 1 条）。
3. **FILEDIR 走平台的路径等价形**（Windows = `fold(trim())`、macOS = NFD、Linux = 逐字节），
   因此 `a`+`A`+`a/b` 能同时给出 `CASEFOLD` 与两条 `FILEDIR`。用原始字节比较会漏掉 `A` 挡住 `a/b`。
4. **FILEDIR 的 `survivor` 是先写者**（`verdict: skipped`）；其余三条是后写者（`overwritten`）。
   `plan/03` 原句"`survivor` = 最后写入者"只对后三条成立。

## 2. 当前事实·状态不变量（下一棒动手前必须知道，否则一定踩）

1. **`check` 的默认语义没变**：不给 `--module` = 要求五模块齐备，缺一个即退 3（现在缺三个：`encoding`
   / `accessibility` / `container`）。点名未落地模块照样退 3（收窄 ≠ 豁免）。
2. **`collisions` 也是判定产出**（K13）：退码 `1` 的判据是 `findings` **或** `collisions` 非空。
   改退码逻辑时这两条要一起想（`data/README.md` §4.1）。
3. **`capabilities` 是 `check` 的唯一门（K08）**：M4 翻 `accessibility` 之前必须同提交补验收测试。
4. **`rules/` 之间不得互相 import（K10）**：M4 的 `access.py` 若需要 MOD-3 的"会写出什么名字"，
   **不要** import `fold.py`——把判定结果作为参数由 `cli.py` 组装后传入（`_run_module` 现在是两个返回值：
   `(findings, collisions)`；M4 若产出第三种形状，同提交扩这个元组并在 `cmd_check` 里接上）。
5. **判定层不得出现 `casefold` / `lower()` / `upper()`**：`tests/test_rule_boundaries.py` 会红。
   M4 判保留名时若要大小写无关比较，用 `platforms.PlatformTables.windows.fold()`（表已注入）。
6. **`precedent` 只对 MOD-1 必填**；`collision.*` 与 M4 的 `accessibility.*` 用 `evidence_strength`
   （`data/README.md` §4.7 的四枚举：`measured` / `table_simulated` / `medium` / `inferred`）。
   **按 `(platform, code)` 固定，不看本机是什么系统**（U16；否则同输入跨机不同输出）。
7. **三级可访问性的定义只在 `data/README.md` §4.2**；`OK` 是第四种取值但**不是级别**。
8. **四份状态副本必须一起改**：`plan/00` 里程碑表、`plan/00` 承诺-证据台账、`plan/05` §二状态表、
   `README.md` 里程碑状态表。只改一处 → `LAYOUT.STATUS` / `LAYOUT.LEDGER` 红。
9. **一个 ✅ 里程碑 = 一份交接单 + 一份下一棒交接单**。M4 收尾要写 `HANDOFF-M5.md`。
10. **状态格必须是"恰好只含 ✅/⬜/🟡 的单元格"**；台账状态格里出现 `M<k>`（k 已 ✅）就红。
    写"待 M5 回填"这种指向**未完成**里程碑的才安全。**M3 现在已 ✅ → 台账里不得再出现"待 M3"。**
11. **`plan/06` 缺口列里不得出现已 ✅ 的里程碑号**（`LAYOUT.GAPS`）。M3 落地时已把
    "判定层未落地"行的 `M3–M5` 改成 `M4–M5`；**M4 收尾时要再改成 `M5`**。
12. **写盘只经 `report.write_atomic`**（`sort_keys=True` + `ensure_ascii=False` + LF + 尾换行）。
13. **展示形是 `backslashreplace` 不是 `surrogateescape`**（`plan/03` §0 有记）：精确字节一律走 `*_hex`。
    `rules/fold.py::_as_text` 用 `surrogateescape` 是**判定内部比较**用的，别抄到报告输出里。
14. **`data/fixtures/truth/*.json` 的键集合受白名单约束**（`tests/test_fixtures.py::ALLOWED_TRUTH_KEYS`）。
    M4 的 `expected_accessibility` 已在白名单里（`reserved.zip` / `trailing.zip` / `trim.zip` /
    `long_comp.zip` / `long_path.zip` 已写），**不需要扩白名单**。
15. **平台表缺失/被换 → 退 3**：`platforms.load()` 的校验顺序固定（见 `plan/02` §四）。
    任何"表没读到就跳过该平台判定"的写法都是假绿。
16. **`ORACLE_PLATFORM_DIR` 是权威覆盖**：设了就用它、缺文件即拒。测试里改它要 `monkeypatch`，
    别忘了同时 `chdir`（cwd 也是候选之一）。
17. **`collisions` 四个数组同长同序**（K14）；M4 若给 `entries[]` 加 `accessibility` 字段，
    **不要**改动 `collisions` 的既有键集（M3 的报告面已冻结，K09 双跑会红）。
18. **工具缺失不许 skip 成假绿**：CI 设 `ORACLE_REQUIRE_TOOLS=1`，别把这个变量从 CI 摘掉。
19. **`7z` 不在 PATH**（`C:\Program Files\7-Zip\7z.exe`）；`unzip` 在 Git for Windows 的 `/usr/bin/unzip`；
    `libarchive` 用 `C:\Windows\System32\tar.exe`（bsdtar 3.8.4）。GNU tar 会被误当 bsdtar——
    `probe_tools._is_bsdtar()` 已做版本串校验。

## 3. 下一棒待办（M4 可访问性，只做 MOD-4）

M4 的交付，**不碰 MOD-2 收尾与 MOD-5**：

1. **`rules/access.py`（MOD-4 三级 + `reasons[]` + `evidence[]`）**，分级算法顺序固定
   （`plan/03` §MOD-4 的 7 步，先命中先返回，同时输出全部 `reasons`）：
   - 空名 / `.` / `..` / 含 NUL → `BLOCKED`；
   - `linux` 含 `/` → `BLOCKED`；
   - `windows` 含 `< > : " / \ | ? *` 或 0x00–0x1F → `BLOCKED`；
   - `windows` 保留设备名（**按最后一个点之前整体匹配**）→ `WRITTEN_UNREADABLE`；
   - `windows` 有尾随空格/点 → `WRITTEN_TRUNCATED`；
   - 组件超长 → `WRITTEN_TRUNCATED`（`long_comp.zip` 的实测是**创建直接失败**；`data/README.md`
     §4.2 的修订已把"单组件 256 码元"归 `BLOCKED`，**按 §4.2 走，不要按 `plan/03` 原表**）；
   - 其余 → `OK`。
2. **`evidence` 固定枚举**：`test_path_false` / `get_content_error` / `open_readable`（`CON.txt` 三条齐）。
   这三条是**实测来源**，不是编的——`data/README.md` §1.3.2。
3. **`entries[].accessibility` 进报告**：`cli._entry_facts` 现在只给结构事实，M4 加判定字段时
   **同提交改 `data/README.md` §4.9 的邻近节（新增 `entries[].accessibility` 的形状）**，
   否则"新增键"与"漏写键"分不清。
4. **`capabilities.accessibility` 翻 True**：同提交补 `tests/test_accessibility.py`（否则 K08 的靶子是空的）。
   验收：`reserved.zip` 的 `CON.txt`/`NUL.txt` → `WRITTEN_UNREADABLE`（三证据齐）、`aux.tar.gz` → `OK`；
   `trailing.zip` 的 `trailing. ` / `trailingdot.` / `colon:name.txt` → `WRITTEN_TRUNCATED`；
   `trim.zip` 的 `readme.` → `WRITTEN_TRUNCATED`、`readme` → `OK`；`long_comp.zip` → `BLOCKED`；
   `clean.zip` → 全 `OK`（零误报基线）。
5. **CLI 接线**：`_run_module` 加 `accessibility` 分支；`check --module accessibility` 可用；
   三个 `--target` 各自的结论要能分开断言。
6. **`docs/rules.md` 定稿（M4 的 DoD 第二项）**：回填 §一 表里 5 行"⬜ 原句待回填（M4）"
   （#2 UAX #15 / #4 libfsapfs / #5 pathname(7) / #6 APPNOTE D.1-D.2 / #7 APPNOTE D.6），
   并把 §二 反查表补齐到**每条规则一个 `#` 行号**。**APFS 行必须逐字写"实现观察，非 Apple 官方规范"**。

**M4 的三条硬约束**（`plan/00` §八）：① 不得用 casefold 近似任何折叠判定；
② 不得引"规范要求 LFH/CD 一致"；③ 不得下载任何真实归档。

## 4. 既定口径清单（K 编号，动了会打挂测试）

| 编号 | 约定 | 打挂什么 |
|---|---|---|
| K01 | 真值库不出现 `observed_*` 字段；键集合受白名单约束 | `tests/test_fixtures.py::test_truth_holds_input_and_expectation_only` |
| K02 | 候选编码顺序固定 UTF-8/CP437/GBK/CP932/CP949/CP1251 | M5 编码测试（M2 已在 `rules/encoding.py` 登记顺序） |
| K03 | 全部写盘经 `report.write_atomic`（sort_keys + ensure_ascii=False + LF + 尾换行） | `tests/test_report_determinism.py` |
| K04 | `$UpCase` 表 `source` ∈ {`volume_read`,`host_probe`}；`sha256` 与本体一致 | `tests/test_m1_data.py` + `tests/test_fold.py`（篡改即拒）+ `platforms --verify` |
| K05 | fixture DOS 时间恒 `1980-01-01 00:00` | `gen_fixtures.py --check` |
| K06 | 新 fixture **追加在末尾**，不改既有样本 | `tests/test_m1_data.py::test_new_fixtures_are_appended_after_m0_ones` |
| K07 | 退出码整数只在 `ExitCode`，映射只在 `EXIT_FOR_REASON` | `tests/test_cli_contract.py::test_exit_code_table_is_total` |
| K08 | `capabilities.MODULES[*].implemented` 是 `check` 的唯一门 | `tests/test_cli_contract.py::test_check_refuses_while_modules_missing` + `::test_check_module_scope_refuses_unimplemented_module` |
| K09 | 报告键序 / 数组序 / 编码 / 换行 | `tests/test_report_determinism.py`（含 M2/M3 新输出面双跑） |
| K10 | 判定模块互不 import；`rules` 不得 import `cli`；不得用近似大小写 | `tests/test_rule_boundaries.py`（**已变异验证可红**） |
| K11 | 推送前 `check_publish_ready.py` 必须全绿；不提供 `--force` | `tests/test_publish_ready.py` |
| K12 | `bootstrap_remote.py` 默认 dry-run；推送成功判据 = 远端 sha == 本地 sha | 同上 + `plan/05` §四 第 0 步 |
| K13 | `collisions` 是判定产出：退码 `1` = `findings` 或 `collisions` 非空 | `data/README.md` §4.1；`tests/test_fold.py::test_fold_entry_point_runs_in_subprocess` |
| K14 | `collisions` 四个数组（`names`/`onDiskNames`/`writeOrder`/`cdOffsets`）同长同序 | `data/README.md` §4.9；`tests/test_fold.py::test_collision_shape_has_no_absent_fields` |
| K15 | 判定报告**不含** `probed_at_utc` 与 `volume` | `data/README.md` §4.10；`tests/test_fold.py::test_probed_at_utc_is_not_a_judgement_input` |

## 5. 本机环境坑（只写实测过的，2026-10-21）

- `python` 是商店占位符 → 一律 `py -3.12`。本项目 `requires-python >= 3.9`。
- 命令一律带 `PYTHONUTF8=1`，否则中文输出在某些控制台会炸。
- **跑测试要带 `PYTHONPATH=src`**（未 `pip install -e .` 时）；已安装则不需要。
  M3 的 `tests/test_fold.py` 还要 `tests/` 在路径里（它 `sys.path.insert(0, tools)` 但用相对 fixtures）。
- `7z` 不在 PATH：`C:\Program Files\7-Zip\7z.exe`；`unzip` 在 Git for Windows 的 `/usr/bin/unzip`
  （`D:\program\Git\usr\bin\unzip.exe`）；`libarchive` 用 `C:\Windows\System32\tar.exe`（bsdtar）。
- 本机 Git Bash 里用 `grep`/`sed` 看中文 UTF-8 文件可能显示乱码——**那是控制台不是文件**。
- `gh` 已登录 `yuluo554`（keyring，HTTPS）；远端尚未创建，**首次 push 前先建仓**。
- **非提权会话打不开卷句柄**（`ERROR_ACCESS_DENIED` 5）→ `fetch_upcase --source volume-read` 会退 3，
  `host-probe` 是可用通道。**M4 不需要重取表**。
- **`/tmp` 里有别人留下的 `inspect.py`**：在 `/tmp` 下跑本工具会劫持标准库 `inspect`。
  中立目录验证一律用**仓库外、无同名模块的任意目录**。
- **冻结态入口必须用 `scripts/entry.py`**（绝对导入），不能拿 `src/extract_oracle/__main__.py`。
- **探测脚本别落在仓库内**：临时脚本里有绝对路径会让发布就绪门 `P4.DESENSITIZED` 变红。探测一律在仓库外。
- **变异验证的锚点要先断言存在**：`assert old in text` 再替换。M1 踩过（全角字符没对上、替换静默失败、
  门照常绿）。M2/M3 的复跑都带这条断言。
- **平台表的 `label` 是中文**（`新加卷`）：断言它时用 UTF-8 读文件，别依赖控制台编码。

## 6. DoD 逐项 checklist（M4）

- [ ] `rules/access.py`：三级分级 + `reasons[]` + `evidence[]`，分级顺序按 `data/README.md` §4.2
      （**不是** `plan/03` 原 7 步表的第 6 条——§4.2 的修订把单组件超长归 `BLOCKED`）
- [ ] `entries[].accessibility` 进 `check` 报告（形状写进 `data/README.md`）
- [ ] `reserved.zip`：`CON.txt`/`NUL.txt` → `WRITTEN_UNREADABLE` 且三证据齐；`aux.tar.gz` → `OK`
- [ ] `trailing.zip`：`trailing. `/`trailingdot.`/`colon:name.txt` → `WRITTEN_TRUNCATED`
- [ ] `trim.zip`：`readme.` → `WRITTEN_TRUNCATED`、`readme` → `OK`，且仍触发 `collision.TRIM`
- [ ] `long_comp.zip` → `BLOCKED`；`clean.zip` 三平台全 `OK`（零误报基线）
- [ ] `capabilities` 里 `accessibility` 翻 True（同提交补 `tests/test_accessibility.py`）
- [ ] `docs/rules.md` §一 的 5 行原句回填 + §二 反查表补到逐规则行号 + APFS 行"非 Apple 官方规范"
- [ ] `py -3.12 -m pytest` 全绿
- [ ] 布局门 + 脱敏门 + 发布就绪门全绿；§3.1 六组弱形态再跑一次（M3 已 5/6 拿到实跑红）
- [ ] 四处状态副本 M4 翻 ✅；写 `plan/HANDOFF-M5.md`（七节）
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
py -3.12 tools/fetch_upcase.py --source host-probe     # 重取表（带真实卷校验）
py -3.12 tools/probe_tools.py                          # 重跑四工具矩阵
py -3.12 tools/probe_tools.py --check                  # 只比对，不写盘

# 测试（未 pip install -e . 时要带 PYTHONPATH=src）
PYTHONPATH=src PYTHONUTF8=1 py -3.12 -m pytest
PYTHONPATH=src PYTHONUTF8=1 py -3.12 -m pytest tests/test_fold.py -q
PYTHONPATH=src PYTHONUTF8=1 py -3.12 -m pytest tests/test_structure_diff.py tests/test_encoding_skeleton.py -q
ORACLE_REQUIRE_TOOLS=1 PYTHONPATH=src py -3.12 -m pytest tests/test_tool_behaviour.py -q

# 骨架命令（需先 pip install -e .）
PYTHONPATH=src py -3.12 -m extract_oracle inspect data/fixtures/upath.zip --format json
PYTHONPATH=src py -3.12 -m extract_oracle capabilities
PYTHONPATH=src py -3.12 -m extract_oracle platforms --verify
PYTHONPATH=src py -3.12 -m extract_oracle check data/fixtures/case.zip --target windows --module fold
PYTHONPATH=src py -3.12 -m extract_oracle check data/fixtures/norm.zip --target macos --module fold
PYTHONPATH=src py -3.12 -m extract_oracle check data/fixtures/clean.zip --target windows   # 期望退出码 3

# 启动下一棒对话
/goal 读取 "<项目绝对路径>\plan\HANDOFF-M4.md" 继续完成任务
```
