# extract-oracle · 归档提取预言机

> **Status: v1.0.0 — M6 发布（五模块全部落地：`structure.*` 六条 + `collision.*` 四条 + `accessibility` 三级 + `encoding.*` 推断 + `container.*` 五条 + `budget.*` 两条）**｜方法论：`ai-tool-project-sprint`｜布局门：`py -3.12 tools/check_sprint_layout.py`

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
| M1 | ✅ | fixture 补全（22/22）+ `$UpCase` 取表 + 四工具对照 |
| M2 | ✅ | 三层解析 + MOD-1 双头差分与重叠（六条规则） + MOD-2 骨架 |
| M3 | ✅ | 平台表接入 + MOD-3 跨平台折叠（四条规则、写序→存活者） |
| M4 | ✅ | MOD-4 三级可访问性 + `docs/rules.md` 定稿（5 行原句回填 + 反查表到逐规则） |
| M5 | ✅ | MOD-5 容器与预算 + MOD-2 收尾（编码推断 + `0x7075` + 确定性导出） |
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
# 结构事实（现在就能用，不是判定）：EOCD / CD / 每条 LFH 三层 + 原始名字节
extract-oracle inspect some.zip

# 能力状态：五个模块各自落地了没
extract-oracle capabilities

# 判定入口（五模块全部落地；有问题退 1，零问题退 0，能力/输入问题退 2/3）
extract-oracle check some.zip --target windows
extract-oracle check some.zip --target windows,macos --format json

# 只跑点名模块（报告里 modules 字段写明本次范围）
extract-oracle check some.zip --target windows --module structure
extract-oracle check some.zip --target windows,macos --module fold
extract-oracle check some.zip --target windows --module accessibility
extract-oracle check some.zip --target windows --module encoding
extract-oracle check some.zip --target windows --module container
```

**M2 起可用的判定**：`structure.*` 六条（`NAME_DIVERGES` / `CRC_DIVERGES` / `SIZE_DIVERGES` /
`FLAG_DIVERGES` / `LFH_OVERLAP` / `CD_COUNT_MISMATCH`），每条 finding 带 `precedent` 字段写清
"哪个工具读哪个头"——**不引"规范要求 LFH/CD 一致"**（规范没有这句话，见 `data/README.md` §1.4）。

**M3 起可用的判定**：`collision.*` 四条（`FILEDIR` / `CASEFOLD` / `NFC` / `TRIM`），输出在
`collisions[]`（不是 `findings[]`）。Windows 侧大小写折叠走**真实 NTFS `$UpCase` 表**
（`data/platforms/ntfs-upcase.bin`，`sha256` 逐字节对账），**不用 `str.lower()`/`casefold()` 近似**；
每条冲突给出 `writeOrder` 与 `survivor`——**不只是"会冲突"，而是"最后剩谁"**：

```bash
# Readme.txt + README.TXT → survivor README.TXT（后写覆盖，内容 LOWER）
extract-oracle check data/fixtures/case.zip --target windows --module fold

# 表指纹 + 卷标识（表被换过则退出码 3，不静默使用）
extract-oracle platforms --verify
```

macOS 侧**只报 NFC**（`evidence_strength: medium`，依据为 UAX #15 + TN1150 + 逆向文档观察）；
**不报** `CASEFOLD`——大小写折叠与否是卷格式属性，而我们没有 macOS 折叠表，所以不猜（见
`data/README.md` §4.3、`plan/05` §五 U15）。

**M4 起可用的判定**：`entries[].accessibility`——每条目在每个目标平台上分四档
（`BLOCKED` / `WRITTEN_UNREADABLE` / `WRITTEN_TRUNCATED` / `OK`，`OK` 不是"级别"），
带 `reasons[]` 与 `evidence[]`。**第三档是本题的差异点**：`CON.txt` 不违规、写入成功、名字也没变，
但应用层拿不到（`Test-Path`=False、`Get-Content` 报错、`open()` 读得到——三条都在 `evidence[]` 里）。
竞品的判定停在"合不合规"，这里区分"**能不能写进去**"、"**写进去能不能被应用层拿到**"、
"**拿到的还是不是原来那个名字**"：

```bash
# CON.txt / NUL.txt → WRITTEN_UNREADABLE（三证据齐）；aux.tar.gz 是可读对照组 → OK
extract-oracle check data/fixtures/reserved.zip --target windows --module accessibility

# 尾随空格/点被裁剪、`:` 被按 ADS 截断 → WRITTEN_TRUNCATED
extract-oracle check data/fixtures/trailing.zip --target windows --module accessibility
```

分级口径（含 `COM0`/`LPT0` 也是保留名、上标 ¹²³ 变体**不是**、保留名按裁剪后组件匹配等
本机实测收窄）唯一表述在 `data/README.md` §4.2，输出形状在 §4.11。

**M5 起可用的判定**：`encoding[]`（每条目：候选编码按固定顺序、置信度 `high`/`medium`/`low`、
**四个提取器各自的落盘名预测**）+ `container`（容器识别）+ `container.*` 五条 + `budget.*` 两条。
两条值得单独看：

- **`0x7075` 的 CRC 校验**：通过 → 覆盖生效（`upath.zip` 四工具一致 `café.txt`）；
  失配 → 覆盖失效 + 降级 `low` + `encoding.UPATH_CRC_MISMATCH`，四方分歧
  （`unzip` 出 `Íð+-+¹.txt`、Python 出 `╓╨╬─├√.txt`、7-Zip 与 libarchive 出 `中文名.txt`）。
- **`budget.PATH_OVER_260` 是预算告警，不是"本机截断"**：本机 `LongPathsEnabled=1` 时 314 字节的
  路径可直接创建（`plan/05` §五 U12）——所以它说"未开启长路径支持时不可移植"，
  `evidence.kind` 显式标 `portability_budget`；组件超限那条才是平台硬限。

```bash
# 0x7075 CRC 有效 → 四工具一致 café.txt（退 0）；失配 → 唯一一条 finding + 降级 low（退 1）
extract-oracle check data/fixtures/upath.zip --target windows --module encoding
extract-oracle check data/fixtures/upath_badcrc.zip --target windows --module encoding

# 四 mimetype 样本各命中一条：NOT_FIRST / COMPRESSED / EXTRA / PADDING
extract-oracle check data/fixtures/padding.epub --target windows --module container
extract-oracle check data/fixtures/long_comp.zip --target windows,linux --module container
```

**四提取器的落盘名模型是按本机实测写的**（不是"应该和谁一致"推的）：`python` 读 0x7075 → bit 11 →
回退 CP437；`unzip` 走 CP850 解码 + OEM→ANSI best-fit（128 个高位字节逐字节实测，33 码点替换表）；
`7zip`/`libarchive` 按**宿主 ANSI 码页**解释且**不做字符集探测**（有效的 UTF-8 字节照样被解成乱码）。
`predictedNames` 只预言**解码层**——7-Zip 的 `_` 前缀、冒号截断、尾随裁剪分别归
`accessibility` / `collision`。口径唯一表述在 `data/README.md` §4.4 / §4.12 / §4.13，
依据核对在 `docs/rules.md` §八。

## 退出码

| 码 | 语义 |
|---|---|
| 0 | 检查完成，无 finding、无 collision、无可访问性异常 |
| 1 | 检查完成，有 finding / collision / 不可访问条目（三者同级） |
| 2 | 输入无法解析（非 ZIP / 无 EOCD / 读不了） |
| 3 | 口径或平台表缺失 / 判定模块未落地——**绝不静默退化为 0** |
| 4 | 用法错误 |

口径唯一真相源：`data/README.md` §4.1。

## 已知限制（诚实清单）

- **五模块全部落地**（M5）：`structure.*` 六条 + `collisions` 四条 + `accessibility` 三级 +
  `encoding.*` 推断 + `container.*` 五条 + `budget.*` 两条。不带 `--module` 的 `check` 出完整报告
  （`clean.zip` 退 0，三数组皆空）。
- **Linux/macOS 侧的可访问性只报"创建即失败"**：空名 / NUL / 空组件这类跨平台都成立的；
  保留名、尾随裁剪、冒号截断都是 **Windows 专属**规则，不在别的平台上猜（`plan/05` §五 U2/U19）。
- **上标 ¹²³ 设备名（`COM¹`/`LPT³`）按实测判 `OK`**：`CreateFileW` 能创建、应用层也读得到；
  MS Learn 里 `echo test > COM¹` 失败是 CMD 走设备命名空间，而提取器走文件 API（`plan/05` §五 U17）。
- **macOS 侧不报大小写折叠**：折叠与否是卷格式属性（libfsapfs 的观察只说"大小写不敏感卷"），
  而我们没有 macOS 折叠表——用 `lower()` 近似会误判，所以只报 `NFC`。这是**收窄不是猜测**。
- **Windows 折叠的强度标 `table_simulated` 而非 `measured`**：判据是"表 + 目标平台"，
  不是"我们恰好在 Windows 上跑"——两条纪律不能混。
- **编码推断的 `source` 随预测一起输出**：`unzip` 的 `cp850` 与 `7zip`/`libarchive` 的 `gbk`
  是**本机环境事实**（换宿主要重测并重写 `encoding.ANSI_CODEC` / `UNZIP_CODEC`），不是规范条文；
  APPNOTE 只规定"历史 CP437"与"bit 11 置位则 MUST UTF-8"（`docs/rules.md` §八）。
- **`budget.PATH_OVER_260` 不是"必然截断"**：见上文（U12）；本机 `LongPathsEnabled=1` 时超 260 的
  路径照常创建，所以这条是**可移植性告警**。
- **macOS / Linux 落盘行为未实测**（本机只有 Windows）：这些判定输出标 `table_simulated` / `medium`，不是 `measured`。
- **APFS 归一化依据为中硬**：来自逆向文档与实操观察，**非 Apple 官方规范**，输出标 `evidence_strength: medium`。
- **不做**：解压、zip slip / zip bomb / 恶意检测、安全打分、"该用哪个工具"的建议、GUI/Web 界面。
- **单文件可执行**：`dist/extract-oracle.exe`（PyInstaller onefile，M6 产出）。**平台语义表随包分发**
  ——在仓库外的中立目录里 `--version` / `capabilities` / `inspect` / `check` 四条命令都可直接跑
  （`platforms --verify` 也退 0），不需要仓库里的 `data/`。PyInstaller 产物含构建期时间戳，
  **不承诺跨机构建逐字节一致**（`plan/05` §五 U5）。
- **stdout 与 `--out` 的字节一致**：两者的换行都是 `\n`（M6 修：Windows 上 `sys.stdout` 默认会把
  `\n` 翻成 `\r\n`，会让 `check x --format json > a.json` 与 `--out a.json` 给出不同字节）。

## 仓库结构

```
src/extract_oracle/   解析（zip_reader）/ 判定（rules/）/ 平台表访问（platforms.py）/ 报告（report）/ CLI
tools/                gen_fixtures.py（程序化 fixture）+ 布局门 + 脱敏门
tests/                契约 / 确定性 / fixture 对账 / 判定验收 / 三工具行为 / 门自身变异
data/                 依据台账（README.md）+ fixtures + truth + tool-matrix（四工具实测）+ platforms（$UpCase 表）
docs/                 rules.md（规范原句台账，M4 定稿）/ divergence.md（四工具实测 22×4 格，M6 定稿）
plan/                 00–06 计划套件 + HANDOFF + RELEASE
scripts/              build.py（PyInstaller onefile）/ entry.py（冻结态入口）
```

## 开发

```bash
py -3.12 tools/check_sprint_layout.py     # 布局门（新对话第一件事）
py -3.12 tools/check_desensitized.py      # 脱敏门（发布前必跑，CI 同 job）
py -3.12 tools/check_publish_ready.py     # 发布就绪门：这个仓库现在能不能推上 GitHub
py -3.12 tools/gen_fixtures.py --check    # fixture 重生成逐字节一致
py -3.12 -m pytest
```

造单文件可执行（需要 `[build]` 额外依赖）：

```bash
py -3.12 -m pip install -e ".[build]"
py -3.12 scripts/build.py                 # → dist/extract-oracle.exe（含平台表随包分发自检）
```

要建仓并首推（**默认 dry-run**，加 `--apply` 才真推）：

```bash
py -3.12 tools/bootstrap_remote.py --repo <owner>/<repo>            # 只打印计划
py -3.12 tools/bootstrap_remote.py --repo <owner>/<repo> --apply    # 建 public 仓 + push + sha 对账
```

## License

MIT（见 `LICENSE`）。
