# data — 依据查证、数据计划与数值口径

**基准日**：2026-10-21。
**代理实际检索窗口**：**2026-10-19T18:35Z–19:10Z**（与基准日相差约 1 天；星数与 `total_count` 均为该窗口快照，复跑请先记录当次时间）。
**实测环境（原样记录，不省略）**：Windows 10.0.26200.8246 / NTFS（`LongPathsEnabled=1`）、Python 3.12.10（`unicodedata` 15.0.0）、7-Zip 25.01、Info-ZIP UnZip 6.00（Cygwin 构建，`UNICODE_SUPPORT`）、zipinfo 3.00、Perl `zipdetails`。
**三态语义**：✅ 已核对（可直连 / 快照已存 / 可复现）；⬜ 未验证或软论据（登记路径与阻断原因，**不得写成承诺**）。

---

## 1. 依据查证记录

### 1.1 竞品与同题仓库（⬜ 软论据，快照）

**窗口 2026-10-19T18:35Z–19:10Z**，`gh api search/repositories`（`in:name,description`）：

| 检索式 | `total_count` | 头部项目 | 状态 |
|---|---|---|---|
| `cross-platform filename validation` | 3 | pathologize 78★、namefix 10★ | ✅ 快照 |
| `filename sanitizer` | 163 | node-sanitize-filename 371★、pathvalidate 296★、zaru 230★ | ✅ 快照 |
| `filename sanitizer windows` | 15 | 最高 11★ | ✅ 快照 |
| `unicode normalization filename` | 20 | jaso 44★ | ✅ 快照 |
| `case insensitive filename collision` | **3** | perl-File-Find-CaseCollide **0★** | ✅ 快照 |
| `zip filename encoding` | 19 | sjisunzip 165★、ZipUnicode 54★ | ✅ 快照 |
| `zip preflight` | **18** | archive-preflight 1★、zip-preflight 0★×2 | ✅ 快照 |
| `zip local header central directory` | 9 | **ronomon/zip 258★（2020-07 后停更）**、zipwalk 13★ | ✅ 快照 |
| `zip parser differential` | 1 | 0★ | ✅ 快照 |
| `zip audit` | 147 | 全部无关 | ✅ 快照 |
| `archive integrity checker` | 6 | 全部 ≤6★ | ✅ 快照 |
| `epubcheck` | 138 | w3c/epubcheck 1978★ | ✅ 快照 |
| `odf validator` | 10 | 11★ | ✅ 快照 |

**同期 4 个同题仓库（红海证据，必须随题记录）**：

| 仓库 | 星数 | 备注 |
|---|---|---|
| `cloudwallker/archive-preflight` | 1★ | `Policies` 表自认 "casefold is an **approximation**"、"Native NTFS/APFS comparison tables… **require host testing**" |
| `Hhhxsss/zip-preflight` | 0★ | `docs/rules.md` 明写不做 "local-header comparison"、"overlapping-entry detection"，"**the tool does not guess encodings**" |
| `mehul82099/zip-preflight` | 0★ | — |
| `mytestapp20261001-collab/zip-member-preflight` | 0★ | — |

> 判读（软论据，禁止写"空白/首创"）：**功能不空白**——两周内 4 个同题仓库，其中 2 个功能相当完整（含 CI、pre-commit hook、Windows 右键菜单、HTML 报告）。本题只押它们**明写不做**的三处：双头差分与重叠、编码推断与 Unicode path extra field、真实文件系统折叠表。

### 1.2 需求证据（原话，✅ 已核对）

| 编号 | 原话（节选） | 出处 | 状态 |
|---|---|---|---|
| D1 | "I watched a coworker's head explode when he tried to extract an archive (from a 'Nix environment) on his Windows machine and was **indignant about getting duplicate filename errors**." | HN · `https://news.ycombinator.com/item?id=29194559` | ✅ |
| D2 | "APFS is normalization-insensitive yet normalization-preserving… if you create a Korean-named file yourself in Finder the file name is normalized in **NFD**, but if you create it in a zsh shell it's **NFC**… **a lot of programs gets subtly crazy when `fopen(A/B)` succeeds but `listdir(A)` doesn't list B**." | HN · `https://news.ycombinator.com/item?id=35336510` | ✅ |
| D3 | "I have a file `grössen.md`; when I try to open it, it isn't shown when I type `grö`… I suspect this is due to zed using **Unicode NFC** internally, while the macOS file system is using **NFD**." | `https://github.com/zed-industries/zed/issues/30503`（open） | ✅ |
| D4 | "zip file created from Mac OS, with Chinese characters filename, then unzip on Windows → filename encoding is UTF-8, but Windows use GBK to decode… **It seems there is no good way to detect which scene is**" | `https://github.com/gtreshchev/RuntimeArchiver/issues/1` | ✅ |
| D5 | "The seeking reader reads **BOTH** the central directory and the local file header… in case of a mismatch… it **always prefers the data in the local file header**" | `https://github.com/libarchive/libarchive/issues/2695`（libarchive 作者 kientzle 本人） | ✅ |
| D6 | "Info-ZIP's `unzip`, libzip, and Python's stdlib `zipfile` all read the Central Directory's filename. libarchive is the one that diverges here, which means archives can **round-trip differently… depending on which tool opens them** — the exact kind of inconsistency that makes ZIP parsing differentials a known source of confusion (and, in adversarial contexts, **smuggling**)" | 同上 issue，fdegros（2026-09-24） | ✅ |

> 引用纪律：以上为**原话节选**，只用于证明需求真实与"读哪个头是**实现选择**"，不用于推导任何数值阈值。

### 1.3 本机实测（✅ 硬证据：三工具分歧 / 不可见性 / NTFS ≠ casefold）

#### 1.3.1 四工具对同一归档的行为分歧

| fixture | 构造 | Python `zipfile` | Info-ZIP `unzip` | 7-Zip 25.01 | `zipdetails` |
|---|---|---|---|---|---|
| `mismatch_name.zip` | LFH `allowed.txt` / CD `evil.txt` | **`BadZipFile` 硬失败** | 写 `evil.txt`，stderr 警告 | 写 `allowed.txt`，报 `Errors: 1` 仍算成功 | 打 `ERROR`，但 **exit code = 0** |
| NFC `café` + NFD `café` | 同名不同归一形 | 落盘 2 个（NTFS 不折叠） | 落 2 个乱码名 | 落 2 个（NFD 那条改名 `cafe_.txt`） | — |
| `Readme.txt` + `README.TXT` | 仅大小写不同 | 只剩 1 个，内容 `LOWER` | 只剩 1 个，内容 `LOWER` | 只剩 1 个，内容 `LOWER` | — |
| `CON.txt` / `aux.tar.gz` / `trailing. ` / `trailingdot.` / `colon:name.txt` | 保留名、尾随点空格、冒号 | 全写出（`trailing` 被截断） | `:`→`_`，尾随点保留 | 全部加 `_` 前缀 | — |

**核心结论**：同一归档 **3 个工具写出 2 个不同文件名，1 个拒绝打开**；`zipdetails` 报了错却返回 0，即"报错但退出码撒谎"。

#### 1.3.2 应用层不可见性（`CON.txt`）

| 观测 | 结果 |
|---|---|
| PowerShell `Test-Path -LiteralPath CON.txt` | **False** |
| PowerShell `Get-Content CON.txt` | 报 *path does not exist* |
| Python `open('CON.txt','rb').read()` | **读到内容** |

→ "文件存在但应用层拿不到"的最小可信证据；本题 MOD-4 的第三级 `WRITTEN_UNREADABLE` 由此而来。

#### 1.3.3 NTFS 折叠 ≠ casefold / upper（8 组字符对，M1 已按机器实测复核）

| 字符对 | `upper()` 预测 | `casefold()` 预测 | 实测 NTFS（M0 记录） | 实测 NTFS（**M1 复核**） |
|---|---|---|---|---|
| `ı` / `I` | 冲突 | 不冲突 | 不冲突 | **不冲突** ✓ |
| `ſ` / `S` | 冲突 | 不冲突 | 不冲突 | **不冲突** ✓ |
| `ß` / `SS` | 冲突 | 不冲突 | 不冲突 | **不冲突** ✓ |
| `ß` / `ss` | 冲突 | 冲突 | 不冲突 | **不冲突** ✓ |
| `İ` / `i` | 不冲突 | 不冲突 | ~~冲突~~ | **不冲突** ✗（M0 记错，见下） |
| `ǅ` / `Ǆ` | 冲突 | 冲突 | 不冲突 | **不冲突** ✓ |
| `ω` / `Ω` | 冲突 | 冲突 | 冲突 | **冲突** ✓ |
| `é` / `É`（对照组） | 冲突 | 冲突 | ~~不冲突~~ | **冲突** ✗（M0 对照组的取值不成立） |

**M1 复核方法**（`tools/fetch_upcase.py --source host-probe`）：在 NTFS 卷上先写 A、再以
`CREATE_NEW` 建 B，`ERROR_ALREADY_EXISTS(183)`/`ERROR_FILE_EXISTS(80)` 即折叠。
三种独立手段（`CreateFileW` / Python `open(...,'xb')` / bash `touch`）结论一致；
机器可读结果在 `data/platforms/meta.json` 的 `ntfs_upcase.verification.pairs`。

> **M0 那两格是错的，按实测改**（`plan/05` §五 U11）。但**结论方向不变、且更强**：
> `ǅ/Ǆ` 上 `casefold` 判冲突而 NTFS 不冲突 → `str.lower()`/`casefold()` 近似会产出假阳性。
> 这条仍是 MOD-3 必须用真实 `$UpCase` 表的直接理由（`plan/00` 决策 ③）。

### 1.4 规范原文（✅ 已核对；逐条对应关系见 `docs/rules.md`）

| 依据 | 位置 | 原文要点 | 状态 |
|---|---|---|---|
| Windows 文件名规则 | MS Learn 命名规范 | 非法字符 `< > : " / \ | ? *` 与 0x00–0x1F；保留设备名 CON/PRN/AUX/NUL/COM1-9/LPT1-9 **及带扩展名**（`NUL.txt` 等价于 `NUL`）与上标 ¹²³；尾随空格/点；`MAX_PATH=260`（含终止 NUL）；`\\?\` 前缀下 32767；**"the file system treats path and file names as an opaque sequence of WCHARs"（Windows 不做归一化）** | ✅ |
| UAX #15 | Unicode Standard Annex #15 | NFD/NFC 的定义与规范分解/组合。**UAX #15 本身不谈文件系统**，FS 侧必须另引 TN1150 与实现观察 | ✅ |
| HFS Plus 归一化存储 | TN1150 | "HFS Plus stores strings fully decomposed and in canonical order" | ✅ |
| APFS 归一化不敏感 | libfsapfs（逆向文档） | 卷不兼容标志 `0x08 APFS_INCOMPAT_NORMALIZATION_INSENSITIVE`；name hash 用 NFD；大小写不敏感卷先 lower-case | ⬜ **中硬：实现观察，非 Apple 官方规范** |
| Linux 文件名约束 | `pathname(7)` | `/` 不可出现在文件名；`PATH_MAX` 为**字节**口径；`NAME_MAX` 由 fstype 决定 | ✅ |
| ZIP 文件名编码 | APPNOTE 6.3.10 D.1 / D.2 | bit 11 set → **MUST** 为 UTF-8；unset → 历史 CP437 | ✅（镜像来源见下） |
| ZIP Unicode path extra field | APPNOTE 6.3.10 D.6 | Info-ZIP 0x7075（Unicode Path）/ 0x6375（Unicode Comment）结构 | ✅（镜像来源见下） |
| APPNOTE **未**要求 LFH 与 CD 名一致 | 逐字检索 | "must be identical" / "SHOULD match" **均无命中** → 判定只能引**实现选择**，不得编造条文 | ✅ |
| EPUB 容器约定 | EPUB 3.3 §4.3.3 | "MUST include the mimetype file as the first file"；"MUST NOT contain any leading or trailing padding or whitespace"；"MUST NOT compress or encrypt"；"MUST NOT include an extra field" | ✅ |
| EPUB 文件名编码 | EPUB 3.3 §4.3.2 | "OCF ZIP containers MUST encode file system names using UTF-8" | ✅ |
| ODF 容器约定 | ODF 1.2 part 3 §3.3 | "shall be the first file"；"shall not be compressed… shall not use an 'extra field'" | ✅ |
| ODF 尾随换行 | — | **未明文禁止**；从 media-type 相等约束推出 → 输出须标 `inferred` | ✅（推断已标注） |

### 1.5 取源失败与替代（必须随题记录）

| 目标 | 结果 | 替代方案 |
|---|---|---|
| PKWARE 官方 APPNOTE 原址 | **不可达**（http 000 / DNS 失败） | 改用 GitHub 镜像 `bearcove/rc-zip` 的 `static/appnote.txt`（v6.3.10）；引用时须写明镜像来源 |
| Apple 官方 APFS 规范 | **未取到**：`developer.apple.com` 与 APFS Reference PDF 均 **ECONNRESET** | 改用 libfsapfs 逆向文档 + HN 实操；**证据强度降为中硬，文档必须标注"非 Apple 官方规范"** |

---

## 2. 数据源可获取性记录

| 数据源 | 可获取性 | 说明 / 阻断原因 |
|---|---|---|
| 真实归档样本（网上下载） | **不可获取，且不使用** | 零网络是硬约束；真实归档可能含未公开内容，隐私红线。 |
| Windows / macOS / Linux 的实际行为 | ✅ 可获取（本机 Windows 已实测；macOS/Linux 需目标机或表模拟） | Windows 侧已实测（§1.3）；**macOS/Linux 的实测在非对应平台上不可得**，只能用平台表模拟，报告须标 `table_simulated` 而非 `measured` |
| 真实 NTFS `$UpCase` 表 | ✅ 可获取（卷读取或真机探测） | 必须记录卷标识与探测环境；**禁止用 `str.lower()`/`casefold()` 替代** |
| APFS 折叠语义 | ⬜ 中硬 | 逆向文档 + 实操；未取到 Apple 官方原文（§1.5）。 |
| 规范原文 | ✅ 可获取（Windows / UAX #15 / TN1150 / pathname(7) / EPUB / ODF 直连；APPNOTE 用镜像） | 见 §1.4 / §1.5。 |
| 自建 fixture | ✅ 完全可获取 | 全部由 `struct.pack` 程序化合成，零网络、可重复、逐字节一致（见 §3）。 |

**结论**：本题**不需要任何外部归档数据**；唯一的真实数据依赖是"目标平台语义"，其中 Windows 可实测、Linux 可从规范推导、macOS 依赖中硬依据（必须标注）。

**阻断纪律**：任何 ⬜ 项不得以确定语气写入判定；macOS 折叠判定在输出中带 `evidence_strength: medium`。

---

## 3. 合成数据纪律

### 3.1 构造纪律（硬约束）

- **全部 fixture 由 `tools/gen_fixtures.py` 用 `struct.pack` 直接拼接字节**，不调用任何压缩库写出归档（避免"用别人的实现生成样本、再用别人的实现校验"的循环论证）；需要 deflate 时用 `zlib.compressobj(level=..., raw)` 只取压缩流字节。
- **不含任何真实用户文件内容**：payload 一律为固定 ASCII 短语（如 `PAYLOAD-A`），名字才承载判定信息。
- **逐字节可复现**：不使用随机、不写入当前时间（DOS 时间字段固定为常量 `1980-01-01 00:00`）；同一命令重复运行产物**逐字节一致**，由 `gen_fixtures.py --check` 校验。
- **每条 fixture 附真值**：`data/truth/<fixture>.json` 记录期望的 `ruleId` 集合、期望的落盘名、期望的 `survivor`、期望的 `accessibility` 级别。
- **样本与真值同提交**：任何 fixture 改动必须同步改真值；`tests/` 里的对账测试校验"fixture ↔ 真值一一对应、无孤儿"。

### 3.2 fixture 清单与判定项映射

| fixture | 构造要点 | 覆盖判定项 |
|---|---|---|
| `mismatch_name.zip` | LFH 名 `allowed.txt`，CD 名 `evil.txt`（长度相同便于构造） | `structure.NAME_DIVERGES` |
| `alias_lfh.zip` | 名字一致，LFH flag=`0x0000` / CD flag=`0x0800`（bit 11） | `structure.FLAG_DIVERGES` |
| `overlap.zip` | `a.txt` 的 payload **恰为** `b.txt` 的整条 `LFH+name+payload`，CD 里 `b.txt` 的 offset 落在 `a.txt` 数据区内；两侧 CRC/size 各自自洽 | `structure.LFH_OVERLAP` |
| `wrong_count.zip` | EOCD 声明 5 条，实际 CD 2 条 | `structure.CD_COUNT_MISMATCH` |
| `crc_diverge.zip` | CD 的 CRC32 为 LFH 的 CRC 翻转最低位 | `structure.CRC_DIVERGES` |
| `size_diverge.zip` | CD 的 uncompressed size 比 LFH 多 7 | `structure.SIZE_DIVERGES` |
| `zh_gbk.zip` | 无 bit11，名字为 GBK 编码的 `中文名.txt` | `encoding.candidates[]` 三提取器分歧 |
| `upath.zip` | 无 bit11，原名字节是 GBK 的 `中文名.txt`，带 0x7075（CRC 按原名字节算，**有效**）指向 `café.txt` | 四工具一致写出 `café.txt`；`upath` 覆盖生效 |
| `upath_badcrc.zip` | 同上但 0x7075 的 CRC 取反 → 覆盖失效 | `encoding.UPATH_CRC_MISMATCH` + 降级 `low` + **四方分歧** |
| `case.zip` | `Readme.txt` + `README.TXT`，payload 分别为 `UPPER` / `LOWER` | `collision.CASEFOLD` + `survivor=README.TXT` |
| `norm.zip` | NFC `café.txt` + NFD `café.txt` | `collision.NFC`（分平台结论相反） |
| `trim.zip` | `readme.` + `readme` | `collision.TRIM` + `WRITTEN_TRUNCATED` |
| `filedir.zip` | 同时有 `a`（文件）与 `a/b`（路径） | `collision.FILEDIR`（**三平台都报**，M1 实测） |
| `reserved.zip` | `CON.txt`、`NUL.txt`、`aux.tar.gz` | `WRITTEN_UNREADABLE` ×2；`aux.tar.gz` 是**可读对照组** |
| `trailing.zip` | `trailing. `、`trailingdot.`、`colon:name.txt` | 三条都是 `WRITTEN_TRUNCATED`（含 `:` 的 ADS 截断） |
| `not_first.epub` | `mimetype` 不是首个条目 | `container.MIMETYPE_NOT_FIRST` |
| `compressed.epub` | `mimetype` 被 deflate（CRC 按**未压缩**内容算） | `container.MIMETYPE_COMPRESSED` |
| `extra.epub` | `mimetype` 带 0xCAFE extra field | `container.MIMETYPE_EXTRA` |
| `padding.epub` | `mimetype` 内容带尾随换行 | `container.MIMETYPE_PADDING`（`inferred`） |
| `long_path.zip` | 7 段 × 44 字节 = **314** 字节整路径（>260），各组件未超 255 | `budget.PATH_OVER_260`（**预算告警**，非本机截断：`LongPathsEnabled=1` 时可直接创建） |
| `long_comp.zip` | 单组件 **256** 码元 | `budget.COMPONENT_OVER_255` + `BLOCKED`（本机实测创建即失败） |
| `clean.zip` | 完全正常的两条目 | **零误报基线**（不得产生任何 finding） |

> **真值键**（`data/fixtures/truth/<fixture>.json`）按 `tests/test_fixtures.py::ALLOWED_TRUTH_KEYS` 约束：
> `expected_findings` 必填；`expected_collisions` / `expected_accessibility` / `expected_names` /
> `expected_encoding` / `note` 按需出现。**"空"与"没写"是两件事**（§2 第 3 条）。

---

## 4. 数值与口径的单一真相源（全项目只此一处）

> **修改本节必须先改这里，再同提交同步代码与文档；其他任何文档只可引用口径键，不得写第二份数值表述。**

### 4.1 退出码

| 退出码 | 语义 | 判据 |
|---|---|---|
| `0` | 检查完成，**无** finding 且**无** collision | 至少一个条目被检查且 `findings` 与 `collisions` 都为空 |
| `1` | 检查完成，**有** finding **或** 有 collision | 两者都是判定产出，任一非空即 `1`（`case.zip --target windows --module fold` 只产 collision，照样退 `1`） |
| `2` | **输入无法解析**（不是 ZIP / EOCD 找不到 / CD 或 LFH 解析不了 / 文件读不了） | 不得退化为 `0`（"依赖/输入缺失不得静默变成合法空结果"） |
| `3` | **口径/平台表缺失**（如 `$UpCase` 表未提供而目标含 windows）**或判定模块未落地**（含 `--module` 点名未落地模块、ZIP64 哨兵值读不到 ZIP64 EOCD） | 不得静默跳过该判定后返回 `0`；不得把"没点名"当成"没问题" |
| `4` | 用法错误 | 参数非法 |

> 纪律：任何"我做不了"的分支都必须是 `2`/`3`，**绝不允许静默返回 `0`**。这一条进 CI 断言。
>
> **M2 补充的两条 reason → 码**（映射只在 `errors.EXIT_FOR_REASON`）：
> `cd_unreadable` / `lfh_unreadable` → `2`（CD 或 LFH 结构读不懂 = 输入的问题）；
> `zip64_unsupported` → `3`（EOCD 是 0xFFFF/0xFFFFFFFF 哨兵值但读不到 ZIP64 EOCD = 能力边界，
> 不是输入坏）。后者**不猜**：把哨兵值当真实条目数读会把 65535 当成条目数。
>
> **`check --module` 的口径**：不给 `--module` = 要求五模块齐备（缺一个即 `3`）；
> 给了 = 只对**明确点名的模块**负责，报告里 `modules` 字段写明本次范围。
> 点名一个未落地的模块照样退 `3`——**收窄范围不等于豁免**。
>
> **M3 补充：`collisions` 也是判定产出**（MOD-3）。退码 `1` 的判据是
> "`findings` **或** `collisions` 非空"——否则 `case.zip` 只产 collision 时会退 `0`，
> 报告里有冲突却告诉 CI"没问题"（最坏的一种假绿，与 D10 同一条纪律）。
> `summary` 里因此同时给 `finding_count` 与 `collision_count`。

### 4.2 三级可访问性（`accessibility`）

| 级别 | 定义（唯一表述） |
|---|---|
| `BLOCKED` | 目标平台在创建时即失败：Linux 名含 `/`；Windows 名含 `< > " / \ | ? *` 或 0x00–0x1F、或单个组件超 255 个 UTF-16 码元；名字为空或仅为 `.`/`..` |
| `WRITTEN_UNREADABLE` | 创建成功但**应用层不可达**：Windows 保留设备名（CON/PRN/AUX/NUL/COM1-9/LPT1-9，含 `CLOCK$`）出现在**最后一个点之前**（`CON.txt`、`COM1.log`、`AUX.tar`，也含上标 ¹²³ 变体） |
| `WRITTEN_TRUNCATED` | 创建成功但**名字已变**：尾随空格/点被裁剪（Windows）、`:` 被按 ADS 截断为冒号前的部分 |

> `OK` 是第四种取值（无上述三情形的条目），但**不是"级别"**，不参与分级评分。
>
> **口径修订（2026-10-21，M1 本机实测，`plan/05` §五 U11）**：`data/README.md` 初版把
> 「非法字符 `:`」与「组件超长」都归入 `BLOCKED`/`WRITTEN_TRUNCATED`，实测不成立：
> - `colon:name.txt` **创建成功**，NTFS 按 ADS 语义把它存成 `colon`（名字变了，不是失败）；
> - 单组件 256 字符 **`CreateFileW` 直接失败**（`ERROR_INVALID_NAME` 123），**加 `\\?\` 前缀也一样**；
> - 保留名只按"最后一个点之前"整体匹配：`AUX.txt` 不可读，而 `AUX.tar.gz` **真可读**（区别于"含扩展名即保留"的初版表述）。

### 4.3 折叠规则来源与判据

| 目标 | 大小写折叠来源 | 归一化折叠 | 裁剪折叠 |
|---|---|---|---|
| `windows` | **真实 NTFS `$UpCase` 表**（卷读取或真机探测，记录卷标识与探测环境）；**禁止 `str.lower()`/`casefold()`** | **不做**（Windows 把名字当不透明 WCHAR 序列） | 尾随空格与尾随点被裁剪 |
| `macos` | **不做**（见下"macOS 侧为什么不报 CASEFOLD"） | **做**（NFD 归一化后比较；APFS 归一化不敏感） | 不做 |
| `linux` | 不做折叠 | 不做 | 不做 |

- `collision.CASEFOLD` / `collision.NFC` / `collision.TRIM` / `collision.FILEDIR` 的**判定顺序固定**为 FILEDIR → CASEFOLD → NFC → TRIM（同一对名字可命中多条，全部输出）。
- `survivor` = 按 CD 顺序**最后写入**者；`verdict` ∈ {`overwritten`, `renamed`, `skipped`}。

**M3 落地时固定的四条判据**（落地形态见 `plan/03` §MOD-3 的 M3 落地记）：

1. **CASEFOLD 与 TRIM 是一个划分，不是两次计数**：Windows 侧"是不是同一个文件"= 先裁尾随空格/点、
   再做大小写无关比较，所以比较键取 `fold(trim(name))`；但**裁剪后逐字节相同**的对子归 `TRIM`，
   `CASEFOLD` 跳过它。两者并集覆盖、交集为空（`trim.zip` 只报 TRIM，`case.zip` 只报 CASEFOLD）。
2. **FILEDIR 走平台的"路径等价形"**：`windows` = `fold(trim(path))`、`macos` = NFD、`linux` = 逐字节。
   因此 `a` + `A` + `a/b` 在 Windows 上会同时给出 `CASEFOLD(a,A)` 与**两条** `FILEDIR`
   （跨规则不短路、同规则逐对穷举）。
3. **FILEDIR 的存活者是先写者**（`verdict: skipped`），其余三条是后写者（`overwritten`）——
   文件与目录不可能"互相覆盖"：后写者根本没落盘。
4. **`onDiskNames` 是落盘形、`names` 是归档名**：Windows 上落盘形 = 裁剪后（NTFS 保留大小写），
   macOS 上是 NFD 形；`names` 一律保留归档里的原名（`case.zip` 落盘只有 `README.TXT`，
   内容是后写者的 `LOWER`，但报告里两个名字都要能看见）。

**macOS 侧为什么不报 `CASEFOLD`**（这是对 `plan/03` 原表述的一处收窄，理由如下）：
libfsapfs 的实现观察是"**大小写不敏感卷**先 lower-case"——即大小写是否折叠取决于**卷格式**，
而 `data/platforms/meta.json` 里**没有** macOS 的折叠表；用 Python `lower()` 近似会违反决策 ③
（`ǅ/Ǆ` 上 `casefold` 判冲突而 NTFS 不冲突——同样的近似风险在 APFS 上无法排除）。
所以这里**不猜**：macOS 侧只报由 UAX #15 + TN1150 支持、且实现观察一致的 `collision.NFC`
（`evidence_strength: medium`）。绑定位置：`rules/fold.py::casefold_pairs`（`platform != "windows"` 即返回空）
与 `case.zip` 的真值 `macos: []`；真机 macOS 折叠表可取时按 §4 流程放开（`plan/05` §五 U2/U3）。

### 4.4 编码候选与可信度

- 候选顺序固定：`UTF-8`, `CP437`, `GBK`, `CP932`, `CP949`, `CP1251`。
- 可信度：
  - `high`：bit 11 set（UTF-8 MUST）或 0x7075 存在且 CRC 校验通过；
  - `medium`：字节序列在候选编码下可完整解码且全部落在该编码的"常用字区"；
  - `low`：其余（含可解码但含控制字符/未分配码点）。
- `upath_crc_mismatch` 时，0x7075 的覆盖判定**失效并降级为 `low`**，同时输出 finding。

### 4.5 容器约定检查项（固定五条）

`container.MIMETYPE_NOT_FIRST` / `MIMETYPE_COMPRESSED` / `MIMETYPE_EXTRA` / `MIMETYPE_PADDING` / `UTF8_REQUIRED`。
其中 `MIMETYPE_PADDING` 对 ODF 上下文标 `inferred: true`（ODF 原文未明文禁止尾随换行，从 media-type 相等约束推出）。

### 4.6 长度预算

| 口径键 | 值 | 说明 |
|---|---|---|
| `win_max_path` | 260 | 含终止 NUL；`\\?\` 前缀下 32767 |
| `linux_path_max` | 4096 | 字节口径，不含终止 NUL |
| `name_max_default` | 255 | **字节**口径（Linux）；Windows 侧为 UTF-16 码元计数的组件长度，按平台分别判定 |

> 以上数值均来自规范原文（§1.4），不是本项目自定；如规范改版，先改本节。

### 4.7 证据强度标记（输出字段 `evidence_strength`）

| 值 | 含义 |
|---|---|
| `measured` | 本机实测（附环境） |
| `table_simulated` | 用平台表模拟（非本机实测，如非 Windows 机器上的 Windows 判定） |
| `medium` | 依据为中硬（APFS：逆向文档 + 实操，非官方规范） |
| `inferred` | 从其他约束推出（ODF 尾随换行） |

### 4.8 输出序列化契约（确定性的唯一表述）

> 全部写盘只经 `extract_oracle.report.write_atomic`；本节的参数是**冻结契约**（K03/K09），
> 改任何一项都必须同提交改本表并跑 `tests/test_report_determinism.py`。

| 项 | 冻结值 | 为什么 |
|---|---|---|
| JSON 序列化 | `json.dumps(..., ensure_ascii=False, sort_keys=True, indent=2)` | 中文不转义（否则 diff 不可读）；键序稳定 |
| 文本导出 | 行序由 payload 的固定键顺序决定，不遍历 dict | 防插入序漂移 |
| 换行 | 恒 `\n`；文件结尾恒有换行 | 跨平台逐字节一致 |
| 编码 | UTF-8（无 BOM） | 同上 |
| 时间戳 | **不输出** | 同输入双跑必须逐字节一致 |
| 随机 ID | **不输出** | 同上 |
| 本机绝对路径 | **不输出** | 隐私红线 + 跨机可比 |
| 数组排序 | `findings` 按 `(cd_offset, ruleId)` 升序；`collisions` 按 `(min(cd_offset), code)` 升序 | 规范序单点定义 |
| 数值格式 | 整数；不出现浮点；不定点舍入 | 避免跨语言格式化差异 |
| 原子写 | 写临时文件 + `os.replace` | 中断不留半个产物 |

### 4.9 `collisions` 输出形状（MOD-3 的唯一表述）

> 与 `findings` 并列的第二个判定数组。字段集**新增即改本节**（同提交改 `findings.Collision.to_dict()`
> 与 `tests/test_fold.py`），"新增键"与"漏写键"是两件事。

| 字段 | 类型 | 口径 |
|---|---|---|
| `code` | string | `collision.FILEDIR` / `CASEFOLD` / `NFC` / `TRIM`（四值封闭） |
| `platform` | string | `windows` / `macos` / `linux` |
| `names` | string[] | **归档里的名字**（原名，含 NFD/NFC 原样），顺序 = CD 顺序 |
| `onDiskNames` | string[] | 该平台上的**落盘形**（Windows：裁剪后；macOS：NFD 形） |
| `writeOrder` | int[] | 写序 = `entry_index`（CD 顺序），与 `names` 同长同序 |
| `cdOffsets` | int[] | 各条目的 CD 偏移，与 `names` 同长同序（也是排序键的来源） |
| `survivor` | string | 存活者（`names` 里的一个）；`FILEDIR` 取**先写者**，其余取**后写者** |
| `survivorEntryIndex` | int | 存活者的 `entry_index` |
| `verdict` | string | 非存活者的遭遇：`overwritten` / `renamed` / `skipped`（`skipped` = 根本没落盘） |
| `evidenceStrength` | string | §4.7 的四枚举之一；**按 (`platform`, `code`) 固定**，不看本机是什么系统 |
| `evidence` | object | 每条规则的机读依据（含 `source`）：`ntfs_upcase_table` / `structural_self_evidence` / `TN1150 + UAX #15 + libfsapfs` / `MS Learn naming conventions` |

四个数组**同长同序**是硬约束（测试钉住）：它们描述的是同一个"两条目 → 一个落盘名"的事件，
不允许某个数组按别的顺序排（否则报告里的对应关系要读者自己猜）。

**`(platform, code)` → `evidenceStrength` 的固定映射**（`rules/fold.py::EVIDENCE`）：

| `code` | windows | macos | linux |
|---|---|---|---|
| `collision.FILEDIR` | `measured` | `measured` | `measured` |
| `collision.CASEFOLD` | `table_simulated` | —（不报） | —（不报） |
| `collision.NFC` | —（不报） | `medium` | —（不报） |
| `collision.TRIM` | `measured` | —（不报） | —（不报） |

**为什么不按"本机是什么系统"给强度**：那会让同一份输入在 Windows 与 Linux 上给出不同的
`evidenceStrength`，直接违反"同输入 + 同平台表 → 同一输出"（`plan/02` §六）。
Windows 侧一律 `table_simulated` 而不是 `measured`——判据是**表 + 目标平台**，
不是"我们恰好在 Windows 上跑"（R6：不得把表模拟写成实测）。

### 4.10 `check` 报告的 `platforms` 块

判定报告里带一个 `platforms` 块（表身份，跨机可比），**刻意不含两项**：

| 含 | 不含 | 为什么不含 |
|---|---|---|
| `ntfs_upcase.{entries, sha256, source}`、两张副表的 `evidence_strength` + `source` | `probed_at_utc`（探测时点）、`volume`（卷序列号/卷标） | `plan/02` §四 第 3 条：探测时点是**环境事实**不是判定输入；卷标识是本机指纹。带上它们 → 跨机复跑的报告必红 |

`volume` 与 `probed_at_utc` 只出现在 `platforms --verify` 的诊断输出里（那是一次性查表可信度检查，
不进任何 `check` 报告）。表身份用 `sha256` 表达——**这是"表换过没有"的跨机判据**。


---

## 5. 证据强度自评

| 论据 | 强度 | 依据 | 说明 |
|---|---|---|---|
| 四工具对 `mismatch_name.zip` 的分歧 | **硬** | 本机实测 + stderr / exit code | 3 工具 2 名字、1 工具拒绝；可直接复现 |
| `CON.txt` 应用层不可见 | **硬** | 本机实测三观测（Test-Path / Get-Content / open） | 三级分级的直接来源 |
| NTFS 折叠 ≠ casefold | **硬** | 8 组字符对实测 | 近似法的假阳性由此证明 |
| 后写覆盖（`Readme.txt` + `README.TXT`） | **硬** | 三工具实测，最终内容均为 `LOWER` | `survivor` 预测的依据 |
| 折叠四规则的**判定顺序与分工** | **硬** | `case.zip`/`norm.zip`/`trim.zip`/`filedir.zip` 四份真值 + `tests/test_fold.py` | CASEFOLD/TRIM 构成划分、FILEDIR 走平台等价形（§4.3） |
| macOS 侧**不报** `CASEFOLD` | **中硬（诚实边界）** | 无 macOS 折叠表；`lower()` 近似违反决策 ③ | 收窄而非猜测；真机表可取时按 §4 流程放开（`plan/05` §五 U2/U3） |
| 编码分歧（GBK / 0x7075） | **硬** | 三工具实测行为 + APPNOTE 镜像 | 预测规则可回归 |
| ZIP 双头不一致的**实现选择** | **硬** | libarchive#2695 作者原话 + 三工具实测 | 不引规范条文 |
| Windows 命名规则 | **硬** | MS Learn 原句 | 逐条进 `docs/rules.md` |
| EPUB / ODF 容器约定 | **硬** | 规范原句 | ODF 尾随换行标 `inferred` |
| HFS Plus 全分解 | **硬** | TN1150 原句 | — |
| **APFS 归一化不敏感** | **中硬** | libfsapfs 逆向文档 + HN 实操 | **未取到 Apple 官方原文**（ECONNRESET）；输出标 `medium` |
| APPNOTE 原文 | **中硬（来源替代）** | GitHub 镜像 `bearcove/rc-zip` `static/appnote.txt` v6.3.10 | 官方原址 http 000 / DNS 失败；引用须写镜像来源 |
| 开源检索总量与星数 | **软** | 13 条检索式 + 窗口 2026-10-19T18:35Z–19:10Z | 快照，不作"首创"证明 |
| 同期 4 个同题仓库 | **软（但方向性重要）** | 仓库名 + 星数快照 | **红海警告，必须随题记录** |
| macOS / Linux 的实际落盘行为 | **未验证（⬜）** | 本机无对应平台 | 只能用表模拟，输出标 `table_simulated`；不得写成"实测" |

> 纪律：上表中所有"软"与"中硬"项，在题面与 README 中**不得用确定语气**，且必须带来源与强度标记。
