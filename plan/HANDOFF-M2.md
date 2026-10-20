# HANDOFF-M2 · 双头差分（下一棒交接单）

> 本文件由 M1 收尾轮撰写。库内一律相对路径；绝对路径只出现在用户侧启动命令里。
> 基线：`plan/00-README总览.md`（文档索引）｜口径：`data/README.md` §4｜里程碑：`plan/05` §二

## 1. 当前进度 + 证据（M1 已完成）

| 交付物 | 路径 | 证据 |
|---|---|---|
| fixture 生成器（22/22） | `tools/gen_fixtures.py` | `py -3.12 tools/gen_fixtures.py --check` → `OK 重生成结果与盘上产物逐字节一致；真值成对且与生成器一致`；`PENDING == []` |
| fixture + 真值（22 对） | `data/fixtures/*.zip`、`*.epub` + `data/fixtures/truth/*.json` | `tests/test_fixtures.py` + `tests/test_m1_data.py` |
| `$UpCase` 折叠表 | `data/platforms/ntfs-upcase.bin`（131072 字节 = 65536 × uint16-le）+ `meta.json` | `tools/fetch_upcase.py --source host-probe` 退出 0；`meta.json` 带 `source/volume/probed_at_utc/probe_host/entries/sha256/generator_version` + 8 组真实卷校验 |
| 四工具对照矩阵（22×4） | `data/tool-matrix/*.json` + `_summary.json` | `tools/probe_tools.py --check` → `OK 全部格实测完成，记录与盘上一致`（重跑逐字节一致、无本机绝对路径） |
| 规则原句台账骨架 | `docs/rules.md` | 14 行 × URL × 原句；5 行标 `⬜ 原句待回填（M4）` |
| M1 常驻断言 | `tests/test_m1_data.py`（33 条） | `py -3.12 -m pytest` → 107 passed |
| 口径修订留痕 | `data/README.md` §1.3.3 / §3.2 / §4.2 | 三处按实测改（见 §2 第 1 条） |

**M1 的关键实测结论（会改变 M2–M5 的判定口径）**：

1. **`mismatch_name.zip` 的分歧方向已复现**：Python `zipfile` 取 **CD** 名（`evil.txt`，不拒绝）、
   `unzip` 取 CD 名并打警告（rc=1）、7-Zip 与 libarchive 取 **LFH** 名（`allowed.txt`）。
   → **`structure.NAME_DIVERGES` 的 `precedent` 字段按满贯写，别按 M0 `data/README.md` §1.3.1 的
   "Python 硬失败"写**（M0 那格是构造不同的样本留下的）。
2. **`overlap.zip`**：Python `zipfile` 抛 `BadZipFile: Overlapped entries`；unzip/7-Zip/bsdtar 全部 rc=0 解出。
3. **`upath.zip`** 四工具**一致**写出 `café.txt`（0x7075 有效时压过 CP437/GBK 猜测）；
   **`upath_badcrc.zip`** 才产生四方分歧（CP437 两种 + GBK 两种）。
   → 想让 `upath` 展示分歧，用 **badcrc** 那份，别用 `upath.zip`。
4. **`filedir.zip`** 三平台都表现为失败（不是只有 Windows/macOS）。
5. **`compressed.epub` 的 CRC 必须按未压缩内容算**（生成器已修；`tests/test_m1_data.py` 钉住）。

## 2. 当前事实·状态不变量（下一棒动手前必须知道，否则一定踩）

1. **M1 实测推翻了三条初版口径**（`plan/05` §五 U11）：
   - `:` **不导致创建失败** —— `CreateFileW('colon:name.txt')` 成功，NTFS 按 **ADS** 只存冒号前的 `colon`
     → 可访问性判 `WRITTEN_TRUNCATED`，**不是** `BLOCKED`；
   - 保留名只按**最后一个点之前**整体匹配 —— `AUX.txt`/`AUX.tar` 不可读，但 **`aux.tar.gz` 真可读**
     （PowerShell `Test-Path` = True）→ `reserved.zip` 的对照组别判错；
   - 单组件 256 码元 **创建即失败**（`ERROR_INVALID_NAME` 123，`\\?\` 前缀也一样）
     → `long_comp.zip` 判 `BLOCKED`，不是 `WRITTEN_TRUNCATED`。
2. **`LongPathsEnabled=1` 时 260 不是硬墙**（`plan/05` §五 U12）：本机 314 字节路径可直接创建。
   `budget.PATH_OVER_260` 是**可移植性预算告警**，**不得**据此断言"必然截断"。M5 要把它与"创建失败"分开。
3. **`data/README.md` §1.3.3 的 8 组字符对已按三种独立手段复核**：`İ/i` 与 `é/É` 两格 M0 记错，已改。
   **结论方向不变且更强**：`ǅ/Ǆ` 上 `casefold` 判冲突而 NTFS 不冲突 → 近似法必须放弃。
   M3 的 8 组回归要按**复核后**的表写（`docs/rules.md` §四 有全表）。
4. **四份状态副本必须一起改**：`plan/00` 里程碑表、`plan/00` 承诺-证据台账、`plan/05` §二状态表、
   `README.md` 里程碑状态表。只改一处 → `LAYOUT.STATUS` / `LAYOUT.LEDGER` 红。
5. **一个 ✅ 里程碑 = 一份交接单 + 一份下一棒交接单**。M1 收尾时已写本文件；M2 收尾要写 `HANDOFF-M3.md`。
6. **状态格必须是"恰好只含 ✅/⬜/🟡 的单元格"**，也别在已 ✅ 的台账行状态格里写 `M1`（`LAYOUT.LEDGER` 会红）。
7. **台账状态格里出现 `M<k>`（k 已 ✅）就红**——写"待 M4 回填"这种指向**未完成**里程碑的才安全。
8. **口径数值只在 `data/README.md` §4**。退出码整数只在 `exit_codes.ExitCode`，映射只在
   `errors.EXIT_FOR_REASON`；改任何一处都要同提交改 §4 并跑 `tests/test_cli_contract.py`。
9. **真值不许出现 `observed_*`**；键集合白名单在 `tests/test_fixtures.py::ALLOWED_TRUTH_KEYS`
   （M1 新加 `expected_encoding` / `expected_names`，扩键必须先改那个白名单）。
10. **写盘只经 `report.write_atomic`**（`sort_keys=True` + `ensure_ascii=False` + LF + 尾换行）。
    `tools/probe_tools.py` 已经照做；新工具也要照做。
11. **平台表契约**（`plan/02` §四）：`source` ∈ {`volume_read`,`host_probe`}，`sha256` 必须与本体逐字节对上，
    `probed_at_utc` **不进报告 digest**（否则跨机复跑必红）。
12. **`volume-read` 通道需要管理员**：本机非提权会话 `CreateFileW('\\\\.\\C:')` 返回
    `ERROR_ACCESS_DENIED(5)`，脚本据此显式退 3（**不静默降级**）。有提权环境可再验一次。
13. **`tools/probe_tools.py` 子进程的 cwd 是临时目录** → 传归档必须用**绝对路径**
    （M1 踩过：相对路径导致 19 份样本被误判成"工具失败"）。
14. **四工具定位**：`unzip` 在 `/usr/bin/unzip`（Git for Windows，`D:\program\Git\usr\bin\unzip.exe`）；
    `7z` 不在 PATH（`C:\Program Files\7-Zip\7z.exe`）；`libarchive` 用 `C:\Windows\System32\tar.exe`（bsdtar 3.8.4）。
    **GNU tar 会被误当 bsdtar**——`probe_tools._is_bsdtar()` 已做版本串校验。

## 3. 下一棒待办（M2 双头差分，只做 MOD-1 + MOD-2 骨架）

M2 的交付，**不碰 MOD-3/4/5**：

1. **`zip_reader` 完整化**：拆 LFH / CD / EOCD 三层的完整解析（当前只有 EOCD 探测）。
   要给出每个条目的 `lfh_offset`、`lfh_end`（= offset + 30 + len(name) + len(extra) + comp_size）、
   `cd_offset`、`lfh_flags`、`cd_flags`、`lfh_crc`、`cd_crc`、`lfh_comp_size`、`cd_comp_size` 等。
2. **MOD-1 六条规则**（`plan/03` §MOD-1）：`structure.NAME_DIVERGES` / `CRC_DIVERGES` /
   `SIZE_DIVERGES` / `FLAG_DIVERGES` / `LFH_OVERLAP` / `CD_COUNT_MISMATCH`。
   **每条都要有 `precedent` 字段**（写清哪个工具取哪个头），**不得**引"规范要求 LFH/CD 一致"。
3. **MOD-2 骨架**：原始名字节 + bit 11 + extra fields 的解析（编码推断留 M5，但**原始字节必须留**）。
4. **`capabilities.MODULES` 翻 True**：`structure`（和 `encoding` 若已能做骨架级输出）。
   **翻之前必须同提交补该模块的验收测试**。
5. **三工具行为断言进 CI**：把 `data/tool-matrix/` 的结论固化成断言（**只锁分歧方向，不锁 stderr 文案**，见 `plan/05` R4）。
6. **`isort`/AST 守门**：`plan/05` K10 —— 判定模块互不 import，`rules` 不得 import `cli`。

**M2 的三条硬约束**（`plan/00` §八）：① 不得用 casefold 近似任何折叠判定；② 不得引"规范要求
LFH/CD 一致"；③ 不得下载任何真实归档。

## 4. 既定口径清单（K 编号，动了会打挂测试）

| 编号 | 约定 | 打挂什么 |
|---|---|---|
| K01 | 真值库不出现 `observed_*` 字段；键集合受白名单约束 | `tests/test_fixtures.py::test_truth_holds_input_and_expectation_only` |
| K02 | 候选编码顺序固定 UTF-8/CP437/GBK/CP932/CP949/CP1251 | M5 编码测试 |
| K03 | 全部写盘经 `report.write_atomic`（sort_keys + ensure_ascii=False + LF + 尾换行） | `tests/test_report_determinism.py` |
| K04 | `$UpCase` 表 `source` ∈ {`volume_read`,`host_probe`}；`sha256` 与本体一致 | `tests/test_m1_data.py`（M1 已落地） |
| K05 | fixture DOS 时间恒 `1980-01-01 00:00`（`FIXED_DOS_TIME=0x0000`/`FIXED_DOS_DATE=0x0021`） | `gen_fixtures.py --check` + `tests/test_fixtures.py` |
| K06 | 新 fixture **追加在末尾**，不改既有样本 | `tests/test_m1_data.py::test_new_fixtures_are_appended_after_m0_ones` |
| K07 | 退出码整数只在 `ExitCode`，映射只在 `EXIT_FOR_REASON` | `tests/test_cli_contract.py::test_exit_code_table_is_total` |
| K08 | `capabilities.MODULES[*].implemented` 是 `check` 的唯一门 | `tests/test_cli_contract.py::test_check_refuses_while_modules_missing` |
| K09 | 报告键序 / 数组序（CD 偏移升序，同偏移按原始名字节字典序）/ 编码 / 换行 | 确定性双跑 |
| K10 | 判定模块互不 import；`rules` 不得 import `cli` | M2 起的 AST 守门 |
| K11 | 推送前 `check_publish_ready.py` 必须全绿；不提供 `--force` | `tests/test_publish_ready.py` |
| K12 | `bootstrap_remote.py` 默认 dry-run；推送成功判据 = 远端 sha == 本地 sha | 同上 + `plan/05` §四 第 0 步 |

## 5. 本机环境坑（只写实测过的，2026-10-21）

- `python` 是商店占位符 → 一律 `py -3.12`。本项目 `requires-python >= 3.9`。
- 命令一律带 `PYTHONUTF8=1`，否则中文输出在某些控制台会炸。
- `7z` 不在 PATH：`C:\Program Files\7-Zip\7z.exe`；`unzip` 在 Git for Windows 的 `/usr/bin/unzip`
  （`D:\program\Git\usr\bin\unzip.exe`）；`libarchive` 用 `C:\Windows\System32\tar.exe`（bsdtar）。
- 本机 Git Bash 里用 `grep`/`sed` 看中文 UTF-8 文件可能显示乱码——**那是控制台不是文件**。
- `gh` 已登录 `yuluo554`（keyring，HTTPS）；远端尚未创建，**首次 push 前先建仓**。
- **非提权会话打不开卷句柄**（`ERROR_ACCESS_DENIED` 5）→ `fetch_upcase --source volume-read` 会退 3，
  `host-probe` 是可用通道（同一张 OS 上表 + 真实卷校验）。
- **`/tmp` 里有别人留下的 `inspect.py`**：在 `/tmp` 下跑本工具会劫持标准库 `inspect`。
  中立目录验证一律用**仓库外、无同名模块的任意目录**。
- **冻结态入口必须用 `scripts/entry.py`**（绝对导入），不能拿 `src/extract_oracle/__main__.py`；
  `tests/test_freeze_entry.py` 做 AST 反向断言。
- **探测脚本别落在仓库内**：M1 把临时探测脚本放进 `.tmp_probe/` 导致发布就绪门 `P4.DESENSITIZED` 变红
  （临时脚本里有绝对路径）。**探测一律在仓库外**（例如用户侧临时目录）。

## 6. DoD 逐项 checklist（M2）

- [ ] `zip_reader` 给出 LFH/CD/EOCD 三层的完整结构事实（含 `lfh_end`）
- [ ] MOD-1 六条规则全部落地，每条带 `precedent` 字段
- [ ] 六个 fixture 各命中对应 `structure.*`：`mismatch_name` / `alias_lfh` / `overlap` / `wrong_count` / `crc_diverge` / `size_diverge`
- [ ] `clean.zip` 零 `structure.*`（零误报基线）
- [ ] MOD-2 骨架：原始名字节 + bit 11 + extra 解析可用
- [ ] `capabilities` 里 `structure` 翻 True（同提交补验收测试）
- [ ] 三工具行为断言进 CI（只锁分歧方向）
- [ ] `py -3.12 -m pytest` 全绿
- [ ] 布局门 + 脱敏门 + 发布就绪门全绿；§3.1 五组弱形态再跑一次（M1 已 4/5 红过）
- [ ] 四处状态副本 M2 翻 ✅；写 `plan/HANDOFF-M3.md`（七节）
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

# 测试
PYTHONUTF8=1 py -3.12 -m pytest
PYTHONUTF8=1 py -3.12 -m pytest tests/test_fixtures.py tests/test_m1_data.py -q

# 骨架命令（需先 pip install -e .）
py -3.12 -m extract_oracle inspect data/fixtures/clean.zip --format json
py -3.12 -m extract_oracle capabilities
py -3.12 -m extract_oracle check data/fixtures/clean.zip --target windows   # 期望退出码 3

# 启动下一棒对话
/goal 读取 "<项目绝对路径>\plan\HANDOFF-M2.md" 继续完成任务
```
