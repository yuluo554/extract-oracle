# HANDOFF-M1 · 数据先行（下一棒交接单）

> 本文件由 M0 收尾轮撰写。库内一律相对路径；绝对路径只出现在用户侧启动命令里。
> 基线：`plan/00-README总览.md`（文档索引）｜口径：`data/README.md` §4｜里程碑：`plan/05` §二

## 1. 当前进度 + 证据（M0 已完成）

| 交付物 | 路径 | 证据 |
|---|---|---|
| 计划套件 | `plan/00–06` | 布局门 `LAYOUT.FILES` / `LAYOUT.SECTIONS` PASS |
| 方法论装订 | `AGENTS.md` + `tools/check_sprint_layout.py` + `tools/check_desensitized.py` + `plan/00` 顶部装订行 | 布局门 9 条判据全绿；`tests/test_layout_gate.py` 12 组变异逐组变红 |
| 可运行骨架 | `src/extract_oracle/`（`cli` / `zip_reader` / `report` / `errors` / `capabilities` / `exit_codes`） | `tests/test_cli_contract.py`、`tests/test_report_determinism.py`、`tests/test_zip_reader.py` |
| 生成器骨架 | `tools/gen_fixtures.py`（6/22 份，`--check` 两层断言） | `py -3.12 tools/gen_fixtures.py --check` → `OK` |
| fixture + 真值 | `data/fixtures/*.zip` + `data/fixtures/truth/*.json` | `tests/test_fixtures.py` |
| CI 预置 | `.github/workflows/ci.yml`（gate + 3×2 测试矩阵） | **未首推，CI 待验证**（`plan/05` §五 U1） |
| 产品页 / 许可 | `README.md` / `LICENSE` / `AGENTS.md` | 脱敏门 0 命中 |
| 冻结态链路 | `scripts/build.py` + `scripts/entry.py` | **M0 实测**：PyInstaller onefile 构建成功，产物 `--version` / `inspect` 通过；入口用 `__main__.py` 会崩（已修，`tests/test_freeze_entry.py` 钉住） |
| 可上传性 | `tools/check_publish_ready.py`（P1–P8）+ `tools/bootstrap_remote.py` | 发布就绪门全绿（含 `git bundle verify` 推送包自证）；11 组变异逐组变红（`tests/test_publish_ready.py`）。**远端尚未创建**——建仓是显式对外动作 |

**M0 的关键判定（D10）**：判定层未落地时 `check` 返回退出码 **3**（`capability_missing`），
**不产出空 findings**。这是"最坏的假绿"的防线，M2 起逐模块翻 `capabilities.MODULES[*].implemented`。

## 2. 当前事实·状态不变量（下一棒动手前必须知道，否则一定踩）

1. **四份状态副本必须一起改**：`plan/00` 里程碑表、`plan/00` 承诺-证据台账、`plan/05` §二状态表、
   `README.md` 里程碑状态表。只改一处 → 布局门 `LAYOUT.STATUS` / `LAYOUT.LEDGER` 红。
2. **一个 ✅ 里程碑 = 一份交接单 + 一份下一棒交接单**。M0 已豁免自己的交接单（`EXEMPT_MILESTONES = [0]`），
   但 `plan/HANDOFF-M1.md`（本文件）必须存在——`LAYOUT.HANDOFF_NEXT` 专测这条。M1 收尾时要写 `HANDOFF-M2.md`。
3. **状态格必须是"恰好只含 ✅/⬜/🟡 的单元格"**。`plan/03` 与 `plan/05` 里的内容表/变异表虽然也以
   `| M1 |` 开头，但状态格不是纯标记，门会跳过它们。新增状态副本时**别把标记写成"✅ 已完成"**——
   会掉出判据集合（这是有意收窄：宁可漏扫一处，不要张冠李戴）。
4. **口径数值只在 `data/README.md` §4**。退出码整数只在 `exit_codes.ExitCode`，映射只在
   `errors.EXIT_FOR_REASON`；改任何一处都要同提交改 §4 并跑 `tests/test_cli_contract.py`。
5. **真值不许出现 `observed_*`**；`tests/test_fixtures.py::test_truth_holds_input_and_expectation_only`
   是白名单断言，扩键必须先改那个白名单。
6. **写盘只经 `report.write_atomic`**（`sort_keys=True` + `ensure_ascii=False` + LF + 尾换行）。
   新增任何导出都要走它，否则 `tests/test_report_determinism.py` 的确定性门形同虚设。
7. **`tools/gen_fixtures.py` 的部分运行不得改写全集清单**（生成器目前没有 `--only`/`--suite`，
   加的时候必须同时加"部分运行不写全集真值"的测试——这是 skill 里实测过的静默污染形态）。
8. **门自身也会过期**：`plan/05` §3.1 表里有 5 组（STATUS/HANDOFFS/GAPS/LEDGER/RELEASE）在 M0
   是弱形态或无法构造靶子；M1 落地后**必须按当时仓库形态复跑这 5 组**，别沿用 M0 的"绿"。
9. **"能不能推"与"发不发布"是两件事**：`check_publish_ready.py` 判前者（P1–P8，每天都该绿），
   `plan/05` §四 判后者（M6 一次）。**不要因为 M6 没做就把发布就绪门当"不适用"**——它是
   唯一能拦住"dist/ 被跟踪""藏了个 token""工作树没提交"的常驻断言。
10. **建仓/推送是显式对外动作**：`tools/bootstrap_remote.py` 默认 dry-run，`--apply` 才写远端，
   且**没有 `--force`**（发布就绪门不绿就拒绝推）。推送成功的判据 = **远端 sha == 本地 sha**，
    不是 `git push` 的退出码（实测过"报 fatal 其实已成功"）。

## 3. 下一棒待办（M1 数据先行，只做数据不写产品逻辑）

M1 的交付是四样，**不碰 `src/` 的判定逻辑**：

1. **`tools/gen_fixtures.py` 补全 16 份待落地样本**（`PENDING` 列表逐条落地）：
   `alias_lfh.zip`、`overlap.zip`、`wrong_count.zip`、`crc_diverge.zip`、`size_diverge.zip`、
   `zh_gbk.zip`、`upath.zip`、`upath_badcrc.zip`、`trim.zip`、`filedir.zip`、`not_first.epub`、
   `compressed.epub`、`extra.epub`、`padding.epub`、`long_path.zip`、`long_comp.zip`。
   构造要点见 `data/README.md` §3.2 表；**每条都要同步真值**（`data/fixtures/truth/`）。
2. **`tools/fetch_upcase.py`（新）**：从 NTFS 卷取 `$UpCase` 表（或真机探测生成），写出
   `data/platforms/ntfs-upcase.bin` + `data/platforms/meta.json`；`meta.json` 必须带
   `source`（只允许 `volume_read` / `host_probe`）、卷标识、探测环境、表 sha256。
   契约见 `plan/02` §四。
3. **`tools/probe_tools.py`（新）**：跑四工具对照（Python `zipfile` / Info-ZIP `unzip` / 7-Zip /
   libarchive），把每格的命令 + 输出节选落 `data/tool-matrix/<fixture>.json`（中间产物），
   M6 定稿成 `docs/divergence.md`。**必须是可重跑脚本，不是手抄表**。
4. **`docs/rules.md` 的骨架**（M4 定稿）：先把 §1.4 表里的 11 条依据落成"规则 → URL → 原句"三列，
   M4 再逐条补齐到 `ruleId` 粒度。

**M1 的三条硬约束**（`plan/00` §八）：① 不得用 casefold 近似任何折叠判定；② 不得引"规范要求
LFH/CD 一致"；③ 不得下载任何真实归档。

## 4. 既定口径清单（K 编号，动了会打挂测试）

| 编号 | 约定 | 打挂什么 |
|---|---|---|
| K01 | 真值库不出现 `observed_*` 字段 | `tests/test_fixtures.py` 白名单 |
| K02 | 候选编码顺序固定 UTF-8/CP437/GBK/CP932/CP949/CP1251 | M5 编码测试 |
| K03 | 全部写盘经 `report.write_atomic`（sort_keys + ensure_ascii=False + LF + 尾换行） | `tests/test_report_determinism.py` |
| K04 | `$UpCase` 表 `source` ∈ {`volume_read`,`host_probe`} | `platforms --verify` |
| K05 | fixture DOS 时间恒 `1980-01-01 00:00`（`FIXED_DOS_TIME=0x0000`/`FIXED_DOS_DATE=0x0021`） | `gen_fixtures.py --check` |
| K06 | 新 fixture **追加在末尾**，不改既有样本 | 既有确定性序列 |
| K07 | 退出码整数只在 `ExitCode`，映射只在 `EXIT_FOR_REASON` | `tests/test_cli_contract.py::test_exit_code_table_is_total` |
| K08 | `capabilities.MODULES[*].implemented` 是 `check` 的唯一门 | `tests/test_cli_contract.py::test_check_refuses_while_modules_missing` |
| K09 | 报告键序 / 数组序（CD 偏移升序，同偏移按原始名字节字典序）/ 编码 / 换行 | 确定性双跑 |
| K10 | 判定模块互不 import；`rules` 不得 import `cli` | M2 起的 AST 守门 |

## 5. 本机环境坑（只写实测过的，2026-10-21）

- `python` 是商店占位符 → 一律 `py -3.12`。`py -0p` 显示 3.8.8 与 3.12 两条通道；本项目 `requires-python >= 3.9`。
- 命令一律带 `PYTHONUTF8=1`（CI 也设了这个 env），否则中文输出在某些控制台会炸。
- `7z` 不在 PATH：`C:\Program Files\7-Zip\7z.exe`；`unzip` 在 PATH（Git for Windows 自带）。
- 本机 Git Bash 里用 `grep`/`sed` 看中文 UTF-8 文件可能显示乱码——**那是控制台不是文件**；
  验收走"Python 以 utf-8 读回"或编辑器。
- `gh` 已登录 `yuluo554`（keyring，HTTPS）；远端尚未创建，**首次 push 前先建仓**。
- `pytest` 8.4.2 / PyYAML 6.0.3 / PyInstaller 已装（3.12 通道）；3.8 通道不保证有。
- **`/tmp` 里有别人留下的 `inspect.py`**（`C:\Users\<user>\AppData\Local\Temp\inspect.py`）：
  在 `/tmp` 下跑本工具会**劫持标准库 `inspect`**，报 `module 'inspect' has no attribute 'get_annotations'`。
  判别 = **"报错栈里 `inspect.__file__` 指向临时目录"** → 换工作目录即可，不是本项目缺陷。
  中立目录验证一律用**仓库外、无同名模块的任意目录**（本机实测用过的那个路径不入库）。
- **冻结态入口必须用 `scripts/entry.py`（绝对导入）**，不能拿 `src/extract_oracle/__main__.py`：
  PyInstaller 把入口当顶层脚本执行，相对导入会 `ImportError: attempted relative import with no
  known parent package`（M0 首次打包实测，脚本态全绿、产物直接起不来）。
  `tests/test_freeze_entry.py` 对这条做 AST 反向断言（把入口改回 `__main__.py` 必须红）。

## 6. DoD 逐项 checklist（M1）

- [ ] `PENDING` 列表清零：22 份 fixture 全部由生成器产出
- [ ] `py -3.12 tools/gen_fixtures.py --check` 通过（重生成逐字节一致 + 真值成对）
- [ ] 每个判定项至少一个 fixture + 一份真值（按 `plan/00` §七的对照表逐行核）
- [ ] `data/platforms/ntfs-upcase.bin` + `meta.json` 在位；`meta.json` 带卷标识、探测环境、sha256
- [ ] 四工具对照脚本可重跑，每格有命令与输出节选（落 `data/tool-matrix/`）
- [ ] `docs/rules.md` 骨架（11 条依据 × URL × 原句）
- [ ] `py -3.12 -m pytest` 全绿
- [ ] 布局门 + 脱敏门全绿；§3.1 的 5 组弱形态变异已按当时形态复跑
- [ ] 四处状态副本 M1 翻 ✅；写 `plan/HANDOFF-M2.md`（七节）
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

# fixture
py -3.12 tools/gen_fixtures.py            # 写盘
py -3.12 tools/gen_fixtures.py --check    # 两层断言，不写盘

# 测试
PYTHONUTF8=1 py -3.12 -m pytest
PYTHONUTF8=1 py -3.12 -m pytest tests/test_fixtures.py -q

# 骨架命令（需先 pip install -e .）
py -3.12 -m extract_oracle inspect data/fixtures/clean.zip --format json
py -3.12 -m extract_oracle capabilities
py -3.12 -m extract_oracle check data/fixtures/clean.zip --target windows   # 期望退出码 3

# 启动下一棒对话
/goal 读取 "<项目绝对路径>\plan\HANDOFF-M1.md" 继续完成任务
```
