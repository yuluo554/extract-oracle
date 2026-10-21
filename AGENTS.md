# AGENTS.md

本仓库遵循 **`ai-tool-project-sprint`** 方法论（装订日期：2026-10-21）。

## 任何新对话的第一件事

```bash
py -3.12 tools/check_sprint_layout.py
py -3.12 tools/check_desensitized.py
```

- 续接对话：读 `plan/HANDOFF-M<k>.md`（那是第 k 棒的收尾交接单），**先跑上面两条门**。
- 接手对话（无 HANDOFF）：先读 `plan/00`、`plan/05`、`plan/06` 与各 HANDOFF，重建"当前状态 + K 口径清单"再动手。
- **门不存在 = 本项目没装订** → 先补第零步三件（本文件 + 布局门 + `plan/00` 顶部一行），再做别的。
- **要推 GitHub 之前**：`py -3.12 tools/check_publish_ready.py` 必须全绿（它判"能不能推"，不判"发没发布"）。
- **本项目已发布（v1.0.0）**：交付面（`src/` `scripts/` `data/fixtures`）**不得再改**；任何改动都要升版本号重发。

## 强制布局（布局门逐条断言，改动前先看这里）

| 项 | 位置 | 判据 |
|---|---|---|
| 计划套件 | `plan/00–06` + `data/README.md` | 存在且各含必需小节（标题关键词） |
| 数据台账 | `data/` | 台账在位（来源 + 三态） |
| 交接单 | `plan/HANDOFF-M<k>.md` | 每个 ✅ 里程碑一份（M0 已声明豁免），**七节**齐（含"当前事实·状态不变量"） |
| 里程碑状态副本 | `plan/00` 里程碑表 + `plan/00` 承诺-证据台账 + `plan/05` 状态表 + `README` 状态行 | **逐处一致**，枚举式断言（台账单独一条判据 `LAYOUT.LEDGER`） |
| 发布留档 | `plan/RELEASE-M<last>.md`（两栏）或 `plan/WRAPUP-M<n>.md` | **两栏**齐（`§一 tag 前事实` / `§二 tag 后追加`）+ `§三 覆盖对账`小节 + 三态行数 ≥ 3。**`§二` 在 tag 树内是明示的自指占位骨架**——留档自己就在 tag 树里，写进去的 OID / sha256 会被"写它"这个动作改掉；"占位"在这里是**规定动作**，不是漏填 |
| 发布门覆盖对账 | `plan/RELEASE-M<last>.md` §覆盖对账 | 阶段 7 出口门逐条：实现 / 不适用 + 理由 / 待首推 |
| 文档点名的工具 | `tools/*.py` | 文档里出现的每个 `tools/` 脚本都必须有实物（`LAYOUT.DOC_TOOLS`） |

## 五条硬纪律（违反即返工）

1. **不解压到磁盘**：所有判定建立在"读字节 + 模拟目标平台语义"上；解压产物只允许出现在测试临时目录并由测试清理。
2. **零网络**：无任何网络调用；不下载真实样本；平台语义表随包分发。
3. **口径单点**：退出码、三级可访问性、折叠规则来源、容器五条、长度预算只在 `data/README.md` §4 定义一次。
4. **确定性**：同输入 + 同平台表 → 同一输出；不含时间戳/随机 ID/本机绝对路径；写盘只经 `report.write_atomic`。
5. **不得用 casefold 近似 NTFS，不得引"规范要求 LFH/CD 一致"**（规范没有；只引实现选择）。

## 环境事实与禁忌（实测日期：2026-10-21）

- 本机 `python` 是商店占位符，一律用 `py -3.12`（3.8 也在，但本项目 `requires-python >= 3.9`）。
- 本机有 Node 24 与 7-Zip 25.01、`unzip`（Git for Windows 自带）；`7z` 不在 PATH，在 `C:\Program Files\7-Zip\7z.exe`。
- 跑脚本建议 `PYTHONUTF8=1`（CI 也设）；中文输出不要依赖控制台编码。
- **禁止**：把"未执行"写成已完成；在 tag 之后改交付面（`src/` `scripts/` `data/fixtures`）。
- **冻结态产物自带平台语义表**（M6 实测补的接线）：`dist/extract-oracle.exe` 把 `data/platforms/` 打进包，
  所以**在中立目录**也能跑 `check` / `platforms --verify`。改动 `scripts/build.py` 的 `--add-data` 会让
  `tests/test_artifact_e2e.py::test_artifact_carries_the_platform_table` 变红——那是设计如此。
- **stdout 的换行是 LF**（M6 实测补的口径）：`cli._force_lf_stdout()` 只改换行翻译、**不动编码**；
  别把"修复换行"写成"改 `PYTHONIOENCODING`"（那会让非 UTF-8 控制台上的中文表标签变乱码）。
- CI 状态：**已首推并全绿（2026-10-21，共十轮，首跑红照录）**——`plan/05` §5.1/§5.2/§5.3 记了前三轮的逐条定性，其后四轮分别修了"版本分派判据写错 / `import yaml` 收集期挂掉 / Windows `which bash` 命中 WSL 启动器 / 3.9 上 `write_text(newline=)` 复发"；最后一轮 `a0fa03d` **8/8 全绿**，run 台账在发布留档 §二。**M6 已收尾：项目无下一棒交接单**（`plan/HANDOFF-M6.md` 是最后一棒的交接单）。
- **本机 `github.com:443` 不可达**（curl 21s connect timeout / `Recv failure: Connection was reset`；实测 2026-10-21），
  但 `api.github.com` / `codeload.github.com` / `uploads.github.com` / `ssh.github.com:443` / `github.com:22` 都可达。
  ⇒ `gh repo create`、`gh api`、`gh release create` 正常，**git over HTTPS 推不动** →
  `origin` 用 SSH 形态（`git@github.com:<owner>/<repo>.git`）。换机器/换网络时**先复核这一条**再谈推送。

## 关键命令

| 用途 | 命令 |
|---|---|
| 布局门 | `py -3.12 tools/check_sprint_layout.py` |
| 脱敏门 | `py -3.12 tools/check_desensitized.py` |
| 发布就绪门（可上传性） | `py -3.12 tools/check_publish_ready.py` |
| 建仓 + 首推（默认 dry-run） | `py -3.12 tools/bootstrap_remote.py --repo <owner>/<repo>` |
| fixture 自检 | `py -3.12 tools/gen_fixtures.py --check` |
| 重取 `$UpCase` 表 | `py -3.12 tools/fetch_upcase.py --source host-probe` |
| 四工具对照矩阵 | `py -3.12 tools/probe_tools.py` / `--check` |
| 测试 | `py -3.12 -m pytest` |
| 结构事实 | `py -3.12 -m extract_oracle inspect <zip>`（需先 `pip install -e .`） |
| 能力状态 | `py -3.12 -m extract_oracle capabilities` |
| 打包 | `py -3.12 scripts/build.py`（产物 + 中立目录平台表自检） |
| 交付态 e2e（对产物跑） | `ORACLE_REQUIRE_ARTIFACT=1 py -3.12 -m pytest tests/test_artifact_e2e.py` |
