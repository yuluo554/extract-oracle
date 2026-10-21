# rules · 规则原句台账（M4 定稿，M5 补 §八）

> **本文件回答一个问题：每条判定到底引的是谁的原话？**
> 纪律：**没有原句就不写确定语气**。原句已核对 → 直引；只有要点转述 → 标 `⬜ 原句待回填`。
> **M4 已把 M1 留下的 5 行全部回填**（见 §五 的收口记录）；现在本文件**没有** `⬜ 原句待回填` 行。
> 数值口径不写在这里（唯一真相源是 `data/README.md` §4）；这里只管**依据与出处**。
>
> 列口径：`ruleId` = 输出里的规则标识（`plan/03`）；`原句` = 可逐字回到来源的引文（节选）；
> `强度` = `硬`（官方规范原文）/ `中硬`（实现观察或逆向文档）/ `推断`（从其他约束推出）。
>
> **逐条对应 `data/README.md` §1.4 的原表**（该表 12 行，`plan/HANDOFF-M1.md` §3 记作「11 条」——
> 差异在于本文件把「APPNOTE 未要求 LFH/CD 一致」单列一行、而把 ODF 尾随换行并入 ODF 行。
> 这里按 §1.4 逐行落地，**宁可多一行，不漏一条**）。M4 另加一行（#15 POSIX `Filename` 定义），
> 因为原表把"/ 不可出现在文件名"挂在 `pathname(7)` 上——**实测那句不在那篇 man page 里**（见 §五）。
> M5 的编码推断另立一行（#16 four-tool name model），因为那三条是**本机实测的实现选择**，
> 不是规范条文——同 §二 #9/#10 的性质（见 §八）。

## 一、总表

| # | `ruleId` | 依据 | URL | 原句（节选） | 强度 | 状态 |
|---|---|---|---|---|---|---|
| 1 | `structure.*`（自证边界）、`accessibility.*`（Windows 侧）、`budget.*`（Windows 侧） | MS Learn · 文件命名约定 | `https://learn.microsoft.com/en-us/windows/win32/fileio/naming-a-file` | "the file system treats path and file names as an **opaque sequence of WCHARs**"；"The following reserved characters: \< \> : \" / \\ \| ? \*"；"Integer value zero, sometimes referred to as the ASCII *NUL* character."；"Do not use the following reserved names for the name of a file: CON, PRN, AUX, NUL, COM1…COM9, LPT1…LPT9… Also avoid these names followed immediately by an extension; for example, **NUL.txt** and NUL.tar.gz are both equivalent to NUL."；"Do not end a file or directory name with a space or a period."；"the maximum length for a path is **MAX_PATH**, which is defined as 260 characters" | 硬 | ✅ 原句已核对（M4 补留名/尾随/260 三句） |
| 2 | `collision.NFC`（macOS 侧） | UAX #15 · Unicode Normalization Forms | `https://www.unicode.org/reports/tr15/` | 表 1："Normalization Form D (NFD) — Canonical Decomposition"；"Normalization Form C (NFC) — Canonical Decomposition, followed by Canonical Composition"；§1.1："Canonical equivalence is a fundamental equivalency between characters or sequences of characters which represent the same abstract character"。**UAX #15 全文零命中 "file system" / "filename"**——FS 侧必须另引 TN1150 与实现观察 | 硬 | ✅ 原句已回填（M4） |
| 3 | `collision.NFC`（macOS 侧） | TN1150 · HFS Plus Volume Format | `https://developer.apple.com/library/archive/technotes/tn/tn1150.html` | "HFS Plus stores strings fully decomposed and in canonical order" | 硬 | ✅ 原句已核对 |
| 4 | `collision.NFC`（macOS 侧） | libfsapfs（逆向文档） | `https://github.com/libyal/libfsapfs/blob/main/documentation/Apple%20File%20System%20(APFS).asciidoc` | 卷不兼容标志表："`0x0000000000000008` \| `APFS_INCOMPAT_NORMALIZATION_INSENSITIVE` \| Filenames are normalization insensitive"；name hash 一节："If the file system is case-insensitive represent the name in **lower-case**"、"Represent the name as an Unicode string in **Normalization Form Canonical Decomposition (NFD)**"。**这是实现观察，非 Apple 官方规范**（`developer.apple.com` 与 APFS Reference PDF 均 ECONNRESET，未取到官方原文） | 中硬 | ✅ 原句已回填（M4）；**引用时必须写明"实现观察，非 Apple 官方规范"** |
| 5 | `accessibility.*`（Linux 侧）、`budget.*`（Linux 侧） | Linux `pathname_resolution(7)` | `https://man7.org/linux/man-pages/man7/path_resolution.7.html` | "There is a maximum length for pathnames.  If the pathname (or some intermediate pathname obtained while resolving symbolic links) is too long, an `ENAMETOOLONG` error is returned ("Filename too long")." | 硬 | ✅ 原句已回填（M4）；**本篇不谈 `/` 与 `NAME_MAX`**，那两条改引 #15（见 §五 更正①） |
| 6 | `encoding.*`（候选顺序与解码） | APPNOTE 6.3.10 D.1 / D.2（**镜像来源** `bearcove/rc-zip` `static/appnote.txt`，版本串 "Version: 6.3.10  Status: FINAL - replaces version 6.3.9"） | `https://github.com/bearcove/rc-zip/blob/main/static/appnote.txt` | D.1："The ZIP format has historically supported only the original IBM PC character encoding set, commonly referred to as **IBM Code Page 437**."；D.2："If general purpose bit 11 is unset, the file name and comment **SHOULD** conform to the original ZIP character encoding.  If general purpose bit 11 is set, the filename and comment **MUST** support The Unicode Standard, Version 4.1.0 or greater using the character encoding form defined by the **UTF-8** storage specification." | 中硬（来源替代） | ✅ 原句已回填（M4）；引用须写明**镜像来源与版本 v6.3.10** |
| 7 | `encoding.UPATH_CRC_MISMATCH`、`upath` 字段 | APPNOTE 6.3.10 §4.6.9 / D.6–D.7（同上镜像） | 同上 | §4.6.9 字段表："(UPath) 0x7075 \| Short \| tag for this extra block type ("up")"、"Version 1 byte version of this extra field, currently 1"、"NameCRC32 4 bytes File Name Field CRC32 Checksum"、"UnicodeName Variable UTF-8 version of the entry File Name"；D.7："records are identified by Header ID's **0x6375** (Info-ZIP Unicode Comment Extra Field) and **0x7075** (Info-ZIP Unicode Path Extra Field)" | 中硬（来源替代） | ✅ 原句已回填（M4） |
| 8 | `structure.NAME_DIVERGES` 的**依据边界** | APPNOTE 6.3.10（逐字检索「must be identical」/「SHOULD match」**均无命中**） | 同上镜像 | **规范没有要求 LFH 与 CD 的名字一致** | — | ✅ 反向核对已做；此条是**禁令**：不得写成"规范要求一致" |
| 9 | `structure.NAME_DIVERGES` 的**实现选择** | libarchive issue #2695（作者 kientzle 本人） | `https://github.com/libarchive/libarchive/issues/2695` | "The seeking reader reads **BOTH** the central directory and the local file header… in case of a mismatch… it **always prefers the data in the local file header**" | 硬 | ✅ 原句已核对 |
| 10 | 同上（其他三个工具取 CD） | 同上 issue，fdegros（2026-09-24） | 同上 | "Info-ZIP's `unzip`, libzip, and Python's stdlib `zipfile` all read the Central Directory's filename. libarchive is the one that diverges here…" | 硬 | ✅ 原句已核对 |
| 11 | `container.MIMETYPE_NOT_FIRST` / `MIMETYPE_COMPRESSED` / `MIMETYPE_EXTRA` / `MIMETYPE_PADDING` | EPUB 3.3 §4.3.3 · OCF ZIP Container | `https://www.w3.org/TR/epub-33/#sec-zip-container-zipreqs` | "MUST include the `mimetype` file as the **first** file"；"MUST NOT contain any leading or trailing padding or whitespace"；"MUST NOT compress or encrypt"；"MUST NOT include an extra field" | 硬 | ✅ 原句已核对 |
| 12 | `container.UTF8_REQUIRED` | EPUB 3.3 §4.3.2 · OCF ZIP Container | `https://www.w3.org/TR/epub-33/#sec-zip-container-mime` | "OCF ZIP containers MUST encode file system names using **UTF-8**" | 硬 | ✅ 原句已核对 |
| 13 | `container.*`（ODF 上下文） | ODF 1.2 part 3 §3.3 · Packages | `https://docs.oasis-open.org/office/v1.2/os/OpenDocument-v1.2-os-part3.html` | "shall be the first file"；"shall not be compressed… shall not use an 'extra field'" | 硬 | ✅ 原句已核对 |
| 14 | `container.MIMETYPE_PADDING`（ODF 上下文，带 `inferred: true`） | 从 media-type 相等约束推出 | 同上 | **ODF 原文未明文禁止尾随换行** | 推断 | ✅ 已标注 `inferred`；**不得**写成 ODF 明文要求 |
| 15 | `accessibility.BLOCKED`（Linux 侧的 `/` 与空名）、`budget.*`（`NAME_MAX`/`PATH_MAX` 的**字节**口径） | POSIX · Base Definitions §3.170 `Filename` / `{NAME_MAX}` / `{PATH_MAX}` | `https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/V1_chap03.html` | §3.170："A sequence of bytes consisting of 1 to {NAME_MAX} bytes used to name a file.  The bytes composing the name **shall not contain the \<NUL\> or \<slash\> characters**."；`{NAME_MAX}`："Maximum number of **bytes** in a filename (not including the terminating null of a filename string)."；`{PATH_MAX}`："Maximum number of bytes the implementation will store as a pathname in a user-supplied buffer of unspecified size, including the terminating null character." | 硬 | ✅ 原句已回填（M4）；**M4 新增行**——原表把这条挂在 `pathname(7)` 上，实测那篇没有（§五 更正①） |
| 16 | `encoding.predictedNames`（四个提取器各自的落盘名模型） | **本机四工具实测**（`data/tool-matrix/`）+ UnZip 6.00 编译选项 | —（**不是规范条文**：APPNOTE 只说"历史 CP437"，没说现代实现用哪个码页） | 见 §八；`unzip` 的 128 个高位字节逐字节对照表在 `data/README.md` §4.12 | 硬（本机实测） | ✅ M5 落地；**这是实现选择，不得写成"规范要求"** |

> 强度纪律（`data/README.md` §5）：任何 `中硬`/`推断` 项，输出必须带对应标记
> （`evidence_strength: medium` / `inferred: true`），且文档不得用确定语气。

## 二、`ruleId` → 依据 反查表（M4 补齐到逐规则粒度）

> **一行一个规则、一个 `#` 行号**（M1 留下的 6 行"集合引用"已全部拆开）。
> 集合写法的坏处是实测过的：`accessibility.*` 写着"1, 5"时，读者以为 #5 支持"/ 不可出现在文件名"，
> 而那篇 man page 里根本没有这句（§五 更正①）。

| `ruleId` | 主依据（上表 #） | 备注 |
|---|---|---|
| `structure.NAME_DIVERGES` | 9,10（+ 8 的禁区） | 只引实现选择；**不得**引"规范要求一致" |
| `structure.CRC_DIVERGES` | 8,6 | 结构自证（LFH/CD 各自声明的 CRC 不等）+ APPNOTE 的 CRC-32 字段定义；bit 3 置位且 LFH 为 0 时豁免 |
| `structure.SIZE_DIVERGES` | 8,6 | 同上（uncompressed size 字段） |
| `structure.FLAG_DIVERGES` | 8,6 | 结构自证 + APPNOTE 4.4.4 的 general purpose bit flag 字段；全 16 位比较 |
| `structure.LFH_OVERLAP` | 8 | 纯结构自证：物理区间相交，不需要外部依据 |
| `structure.CD_COUNT_MISMATCH` | 8,6 | EOCD 的 "total number of entries" 字段 vs 实际按签名遍历；ZIP64 路径单独处理 |
| `encoding.candidates[]`（顺序与解码） | 6 | 候选顺序见 `data/README.md` §4.4；D.1 的 CP437 是候选之一 |
| `encoding.bit11`（`high` 置信度的来源） | 6 | D.2 的 **MUST**（bit 11 set → UTF-8） |
| `encoding.UPATH_CRC_MISMATCH` | 7 | §4.6.9 的 `NameCRC32`；校验失配 → 降级 `low` |
| `encoding.upath`（0x7075 覆盖生效） | 7 | 同一条字段定义；`version=1` + `UnicodeName` UTF-8 |
| `collision.CASEFOLD`（Windows 侧） | —（**本机 `$UpCase` 表**，不是规范条文） | 依据是数据表 `data/platforms/ntfs-upcase.bin` + 8 组真机碰撞实测（`data/README.md` §1.3.3）；**不引任何规范** |
| `collision.NFC`（macOS 侧） | 2,3,4 | UAX #15 定形、TN1150 定 HFS+ 存储形、libfsapfs 定 APFS（**实现观察，非 Apple 官方规范**） |
| `collision.TRIM` | 1 | MS Learn "Do not end a file or directory name with a space or a period."；仅 Windows |
| `collision.FILEDIR` | 8 | 结构自证（同一路径既是文件又要求作目录）+ M1 四工具实测（§三），三平台都报 |
| `accessibility.BLOCKED`（空名/NUL/空组件/`.`/`..`） | 15,1 | POSIX §3.170（Linux 侧 NUL/slash 与 `1 to {NAME_MAX} bytes`）+ MS Learn（Windows 侧 NUL 与 260） |
| `accessibility.BLOCKED`（Windows 非法字符） | 1 | MS Learn 的 "The following reserved characters" 清单 |
| `accessibility.BLOCKED`（Windows 组件超长） | 1 | MS Learn `MAX_PATH=260` + M1 实测（单组件 256 码元 `ERROR_INVALID_NAME`） |
| `accessibility.WRITTEN_UNREADABLE` | 1 + **本机实测三证据** | MS Learn 保留名清单；"不可读"这一层靠 `data/README.md` §1.3.2 的三条实测（`Test-Path` False / `Get-Content` error / `open()` readable）——**规范只说不该用，没说不读不到** |
| `accessibility.WRITTEN_TRUNCATED` | 1 | MS Learn 尾随空格/点 + 本机实测的 ADS 冒号截断（§三） |
| `accessibility.OK` | — | 无三情形；不是"合规认证"，只表示本工具不预言任何异常 |
| `container.MIMETYPE_NOT_FIRST` | 11,13 | EPUB "first file"；ODF "shall be the first file" |
| `container.MIMETYPE_COMPRESSED` | 11,13 | EPUB "MUST NOT compress or encrypt"；ODF "shall not be compressed" |
| `container.MIMETYPE_EXTRA` | 11,13 | EPUB "MUST NOT include an extra field"；ODF "shall not use an 'extra field'" |
| `container.MIMETYPE_PADDING`（EPUB） | 11 | "MUST NOT contain any leading or trailing padding or whitespace" |
| `container.MIMETYPE_PADDING`（ODF） | 14 | **原文未禁止** → `inferred: true` |
| `container.UTF8_REQUIRED` | 12 | "OCF ZIP containers MUST encode file system names using UTF-8" |
| `budget.PATH_OVER_260` | 1,15 | Windows 侧 MS Learn `MAX_PATH=260`；本机 `LongPathsEnabled=1` 时**创建仍成功** → 只作可移植性告警（`plan/05` §五 U12）。Linux 侧另引 #15 的 `{PATH_MAX}` **字节**口径 |
| `budget.COMPONENT_OVER_255` | 1,15 | Windows 侧按 UTF-16 码元；Linux 侧按 POSIX `{NAME_MAX}` 的**字节**口径 |
| `encoding.predictedNames.<tool>` | 16 | **本机四工具实测**（`data/tool-matrix/`）：实现选择，不是规范条文（§八） |
| `encoding.candidates[]` / `preferred`（K02 顺序与强弱结构） | 6 | D.1 的 CP437 是候选之一；**候选顺序是本项目口径**（§4.4），不是 APPNOTE 规定 |
| `encoding.UPATH_CRC_MISMATCH` / `upath` | 7 | §4.6.9 的 `NameCRC32`；校验失配 → 降级 `low` |

## 三、M1 实测对既有表述的修正（必须先看这里再动 M2/M3/M4）

M1 的本机实测（`plan/05` §五 U11）推翻了 `data/README.md` 与 `plan/03` 的三处初版表述。
**以实测为准**，四处文档已同步改：

| 初版表述 | 实测结果 | 影响 |
|---|---|---|
| `:` 属 Windows 非法字符 → `BLOCKED` | `CreateFileW('colon:name.txt')` **成功**，NTFS 按 ADS 语义只存 `colon` | `trailing.zip` 的 `colon:name.txt` 改判 `WRITTEN_TRUNCATED`（名字变了），**不是** `BLOCKED` |
| 保留名「含扩展名形式」即不可读 | 只按**最后一个点之前**整体匹配：`AUX.txt`/`AUX.tar` 不可读，`aux.tar.gz` **真可读**（`Test-Path`=True） | `reserved.zip` 的 `aux.tar.gz` 改判 `OK` |
| 组件超长 → 截断（`WRITTEN_TRUNCATED`） | 单组件 256 码元 `CreateFileW` **直接失败**（`ERROR_INVALID_NAME` 123），加 `\\?\` 前缀也一样 | `long_comp.zip` 改判 `BLOCKED`；`budget.COMPONENT_OVER_255` 仍是告警，但可访问性级别不是截断 |
| （新增）`İ/i` 折叠 | **不冲突**（`ı/I`、`ſ/S`、`ß/SS`、`ß/ss`、`ǅ/Ǆ` 同样不冲突；`ω/Ω`、`é/É` 冲突） | 见 §四；`data/README.md` §1.3.3 的 `İ/i` 一行在 M1 已按实测改正为"**不冲突**"（M4 复核：真表仍是 8/8 与 §四 一致） |

## 四、8 组字符对：本机复核结果（M1，2026-10-21）

实测方法：在 NTFS 卷上先写 A 再 `CREATE_NEW` 建 B，`ERROR_ALREADY_EXISTS`/`ERROR_FILE_EXISTS` 即折叠。
三种独立手段（`CreateFileW` / Python `open(...,'xb')` / bash `touch`）结论一致。

| 字符对 | `str.upper()` 预测 | `str.casefold()` 预测 | **本机 NTFS 实测** | `data/README.md` §1.3.3 原表 |
|---|---|---|---|---|
| `ı` / `I` | 冲突 | 不冲突 | **不冲突** | 不冲突 ✓ |
| `ſ` / `S` | 冲突 | 不冲突 | **不冲突** | 不冲突 ✓ |
| `ß` / `SS` | 冲突（`ß`.upper() = `SS`） | 不冲突 | **不冲突** | 不冲突 ✓ |
| `ß` / `ss` | 冲突（`ß`.upper() = `SS` ≠ `ss`，但 `ß`.lower() 同形） | 冲突 | **不冲突** | 不冲突 ✓ |
| `İ` / `i` | 不冲突（`İ`.upper() = `İ`） | 不冲突（`İ`.casefold() = `i̇`） | **不冲突** | 冲突 ✗（M0 记错；M1 已改正，M4 复核真表仍不冲突） |
| `ǅ` / `Ǆ` | 冲突 | 冲突 | **不冲突** | 不冲突 ✓ |
| `ω` / `Ω` | 冲突 | 冲突 | **冲突** | 冲突 ✓ |
| `é` / `É`（对照组） | 冲突 | 冲突 | **冲突** | 不冲突 ✗（M0 对照组的取值不成立；M1 已改正，M4 复核真表仍冲突） |

**结论不变、且更强**：`str.lower()`/`str.casefold()` 与真实 NTFS 折叠**不等价** ——
`ǅ/Ǆ` 上 `casefold` 判冲突而 NTFS 不冲突；`İ/i` 上两边都判不冲突而原表记的是冲突。
**所以 MOD-3 必须用真实 `$UpCase` 表**（`data/platforms/ntfs-upcase.bin`，来源 `host_probe`，
带真实卷实测校验），这条决策（`plan/00` 决策 ③）不受本表任何一行取值影响。

> 逐字符的完整表（65536 项）与那 8 组的机器可读结果在 `data/platforms/meta.json` 的
> `ntfs_upcase.verification.pairs` 里；本表只是人读摘要。

## 五、M4 收口记录：5 行原句回填 + 两处依据出处更正（2026-10-21）

M1 留下的五条 `⬜ 原句待回填`（#2 / #4 / #5 / #6 / #7）已在 §一 全部回填。回填时**逐条重取原文**，
其中两处发现原表把依据挂错了出处——这两处不是"补字"，是**改依据**，所以单独记：

| 更正 | 原表述 | 实测/原文 | 影响 |
|---|---|---|---|
| ① `/` 与 `NAME_MAX` 的依据出处 | 挂在 Linux `pathname(7)`（`man7.org/.../pathname_resolution.7.html`）上 | 该篇**逐字检索零命中**：没有 `/`、没有 `NAME_MAX`、没有 `PATH_MAX`（只有一句 "There is a maximum length for pathnames." + `ENAMETOOLONG`）。真正的原句在 **POSIX Base Definitions §3.170 `Filename`**："The bytes composing the name shall not contain the `<NUL>` or `<slash>` characters."；`{NAME_MAX}` / `{PATH_MAX}` 同在那一章，且都是**字节**口径 | 新增 #15 承载这条；#5 只保留 `ENAMETOOLONG` 那一句。`accessibility.BLOCKED` 的 Linux 侧依据改引 #15 |
| ② APPNOTE 镜像的版本串 | "APPNOTE 6.3.10" 只说版本号 | 镜像正文首行可核对："Version: 6.3.10" / "Status: FINAL - replaces version 6.3.9" / "Revised: Nov 01, 2022" | #6 / #7 / #8 的 URL 列都写明镜像与版本串，读者可直接对版 |

**为什么 #4 不升级强度**：libfsapfs 的原文确实逐字拿到了（"`APFS_INCOMPAT_NORMALIZATION_INSENSITIVE` \| Filenames are normalization insensitive"、
"If the file system is case-insensitive represent the name in lower-case"、"Represent the name as an Unicode string in
Normalization Form Canonical Decomposition (NFD)"），但**它仍是逆向文档**：`developer.apple.com` 与 APFS Reference PDF
本轮再试仍 ECONNRESET。所以强度保持 `中硬`，输出保持 `evidence_strength: medium`，正文继续保持
**"实现观察，非 Apple 官方规范"** 的逐字标注（决策 ④）。**拿到原句不等于拿到官方背书**——这条不能因为
"文字变具体了"就被读成"依据变硬了"。

**M4 的两处实测收窄**（与 M1 的 §三 同一性质，都是"文档写了但机器不同意"）：

| 文档表述 | 本机实测（2026-10-21） | 处理 |
|---|---|---|
| 上标 ¹²³ 变体（`COM¹`、`LPT³`）是保留设备名（MS Learn 原文 + `plan/01` §2 模块④） | `CreateFileW('COM¹.txt')` / `'COM².txt'` / `'LPT³.log'` **创建成功**，`Test-Path=True`，`Get-Content` 读得到。CMD 里 `echo test > COM¹` 确实失败（走了设备命名空间），但**提取器走的是 Win32 文件 API** | `accessibility` 按实测判 `OK`；收窄理由写进 `data/README.md` §4.2 的修订段。**不猜规范语气** |
| `COM1`–`COM9` / `LPT1`–`LPT9` | `COM0.txt` / `LPT0.txt` **同样不可读**（`Test-Path=False`）；`COM10.txt` 起可读 | 保留名集合扩到 `COM0`–`COM9` / `LPT0`–`LPT9`（并集，不多报也不漏报） |
| 保留名与尾随裁剪的先后 | `con.txt.` 落盘为 `con.txt`，而 `con.txt` 的 `Get-Content` 报错 | 保留名按**裁剪后**的组件匹配；两者同时成立时级别取 `WRITTEN_UNREADABLE`（更严重的那档），`reasons` 两条都留 |

## 六、M2 落地时的依据核对（2026-10-21）
MOD-1 的六条规则已全部落地，每条 finding 都带 `precedent`。这里记下**落地时逐条核对的结果**，
因为"有 `precedent` 字段"和"`precedent` 写对了"是两件事：

| `ruleId` | 落地用的依据 | 核对结果 |
|---|---|---|
| `structure.NAME_DIVERGES` | 上表 #9 + #10（实现选择） | ✅ 枚举取值 `libarchive_reads_lfh`（libarchive/7-Zip 取 LFH）。**7-Zip 也取 LFH**——上表 #10 的原话只点名了 libarchive 是"diverges"，而本机实测 7-Zip 同样取 LFH。枚举里**没有** `7zip_reads_lfh`，所以 7-Zip 的读头选择只进 `evidence.readers`，不进 `precedent`（不就地扩枚举） |
| `structure.CRC_DIVERGES` | 上表 #8（结构自证）+ APPNOTE 字段定义 | ✅ bit 3 置位且 LFH 值为 0 → 豁免；**bit 3 置位但值非 0 仍报**（有专门的反向对照测试）。本机实测：Python 抛 `BadZipFile: Bad CRC-32`、libarchive rc=1、7-Zip rc=2、unzip rc=0 |
| `structure.SIZE_DIVERGES` | 同上 | ✅ 同上豁免。本机实测：libarchive 直接报 `Inconsistent uncompressed size: 17 in central directory, 10 in local header`；**Python 照收（rc=0）**——与 CRC 那一份不同，这条区别本身是"分歧方向"的一部分 |
| `structure.FLAG_DIVERGES` | 上表 #8（结构自证） | ✅ 全 16 位比较，`differingBits` 给出差异位。本机实测：四工具都写出同名文件，只有 unzip rc=1 |
| `structure.LFH_OVERLAP` | 结构自证 | ✅ 区间用 **LFH 自己声明的 `comp_size`** 算，不是 CD 的（否则 CD 大小被篡改时判不出来）。`precedent` = `structural_self_evidence`（**不是**某个工具的读头选择）。本机实测：Python 抛 `BadZipFile: Overlapped entries`，unzip/7-Zip/bsdtar 全部 rc=0 解出两个文件 |
| `structure.CD_COUNT_MISMATCH` | APPNOTE EOCD 字段定义 | ✅ 按**签名**遍历 CD，不按 EOCD 声明数遍历（否则永远相等）。`precedent` = `structural_self_evidence`。ZIP64 哨兵值读不到 ZIP64 EOCD → `zip64_unsupported`（退出码 3），不猜 |

**禁令复核**：六条规则的 `message` / `precedent` / `evidence` 里逐字检索过
「规范要求」「spec requires」「must be identical」「SHOULD match」，**零命中**。
判据落在 `tests/test_structure_diff.py::test_no_finding_claims_the_spec_requires_lfh_cd_agreement`。

**两条口径更正**（M2 实测，`plan/05` §五 U13/U14）：

1. `data/README.md` §1.3.1 把 Python 在 `mismatch_name.zip` 上记成"`BadZipFile` 硬失败"。精确说法是：
   `namelist()` **返回 CD 名** `evil.txt`，拒绝发生在 `read()`。所以它属于"取 CD 名但校验时拒绝"，
   与 unzip 的"取 CD 名并照解"是**同一读头选择下的两种严格度**。
2. `plan/03` §MOD-2 原验收句"`upath.zip` 7-Zip 出 `café.txt` 而 Python/unzip 出 `caf茅.txt`"**不成立**——
   0x7075 CRC 有效时四工具一致写出 `café.txt`。要展示编码分歧得用 `upath_badcrc.zip`。

---

## 七、M3 落地时的依据核对（2026-10-21）

MOD-3 的四条规则已全部落地（`rules/fold.py`）。**"有 `evidence_strength` 字段"与"强度标对了"
是两件事**，所以逐条记下落地时用的是哪一种依据、以及哪一条**不能**升级成更强语气：

| `ruleId` | 落地用的依据 | 核对结果 |
|---|---|---|
| `collision.CASEFOLD`（Windows 侧） | **本机 `$UpCase` 表**（`data/platforms/ntfs-upcase.bin`，`source=host_probe`）+ 8 组真实卷写入碰撞校验 | ✅ 表对 `/`（U+002F）与 BMP 外码点是恒等映射 → 整串折叠不会串组件（`tests/test_m3_platforms.py` 与 `test_fold.py` 钉住）。输出 `evidence_strength: table_simulated`——判据是**表 + 目标平台**，不是"我们恰好在 Windows 上跑"（R6：不得把表模拟写成实测） |
| `collision.CASEFOLD`（macOS 侧） | **不落地**（返回空） | ⚠️ 这是一处**收窄**：上表 #4 的 libfsapfs 观察只说"**大小写不敏感卷**先 lower-case"——大小写是否折叠是**卷格式属性**；而 `meta.json` 里没有 macOS 折叠表。用 `lower()` 近似违反决策 ③，所以**不猜**。理由与绑定位置写在 `data/README.md` §4.3 与 `plan/05` §五 U15 |
| `collision.NFC`（macOS 侧） | 上表 #2（UAX #15）+ #3（TN1150 "fully decomposed and in canonical order"）+ #4（libfsapfs，**实现观察，非 Apple 官方规范**） | ✅ 输出 `evidence_strength: medium`，`evidence.note` 逐字写"实现观察，非 Apple 官方规范"（决策 ④）。**依据强度不因落地而升级** |
| `collision.NFC`（Windows/Linux 侧） | 上表 #1 的反向（"the file system treats path and file names as an opaque sequence of WCHARs"） | ✅ **不做归一化**：`norm.zip --target windows` 必须报 0 条（`plan/03` §MOD-3 验收行） |
| `collision.TRIM` | 上表 #1（MS Learn：尾随空格与尾随点） | ✅ 仅 Windows。判据是"**裁剪后逐字节相等**"，与 CASEFOLD 构成划分（见下） |
| `collision.FILEDIR` | 结构自证（同一路径既是文件又要求作目录）+ M1 四工具实测 | ✅ 三平台都报（`data/README.md` §3.2 的 `filedir.zip` 行）；**不是**"大小写不敏感卷"的推论——那是 `plan` 初版表述，M1 实测否掉 |

**两条落地时定死的分工纪律**（数值/口径在 `data/README.md` §4.3，这里只记依据）：

1. **CASEFOLD 与 TRIM 是划分不是两次计数**：两者都以 `trim` 后的名字为比较基准，但
   "裁剪后逐字节相同"的对子**只归 TRIM**、CASEFOLD 跳过。这样一对名字不会被两条规则重复计数，
   而"全部输出"（跨规则不短路）依然成立——`a`+`A`+`a/b` 在 Windows 上同时给出
   `CASEFOLD(a,A)` 与两条 `FILEDIR`。
2. **FILEDIR 的路径比较走平台等价形**（`fold(trim())` / NFD / 逐字节）：否则
   `A`（文件）挡住 `a/b`（目录）这条在 Windows 上会漏报。

**禁令复核**：四条规则的 `message` / `evidence` 里逐字检索「规范要求」「spec requires」
「Apple 官方规范」，只在 macOS 的 `note` 里出现**否定形**（"非 Apple 官方规范"）。
判据在 `tests/test_fold.py::test_norm_zip_macos_reports_nfc`（断言该串必须出现）
与 `data/README.md` §4.3（断言收窄理由留痕）。

---

## 八、M5 落地时的依据核对（2026-10-21）

MOD-2 的编码推断与 MOD-5 的容器/预算已全部落地（`rules/encoding.py` / `rules/container.py` /
`rules/budget.py`）。**"有 `source` / `precedent` 字段"与"依据挂对了"是两件事**，所以逐条记下
用的是哪一种依据、以及哪一条**不能**升级成规范语气：

| `ruleId` / 字段 | 落地用的依据 | 核对结果 |
|---|---|---|
| `encoding.candidates[]` / `preferred` | 上表 #6（APPNOTE D.1/D.2 的 CP437 与 UTF-8） | ⚠️ **候选顺序（K02）与"强弱结构"是本项目口径**，不是 APPNOTE 规定——APPNOTE 只说"历史上是 CP437"、"bit 11 置位则 MUST 为 UTF-8"。所以 `preferred` 的判据写在 `data/README.md` §4.4（本项目），不引条文 |
| `encoding.predictedNames["python-zipfile"]` | 上表 #6 + 本机实测 | ✅ Python 3.12 `zipfile`：读 0x7075（CRC 通过时用 `utf8_name`）→ bit 11 严格 UTF-8 → 回退 CP437。实测 `zh_gbk.zip` → `╓╨╬─├√.txt` |
| `encoding.predictedNames["info-zip-unzip"]` | 上表 #16 + 本机 128 字节逐字节实测 | ✅ Info-ZIP UnZip 6.00（Cygwin，`UNICODE_SUPPORT`）：**CP850 解码 + OEM→ANSI best-fit**（33 个码点的实测表 `CP850_TRANSLITERATION`）。**bit 11 置位与否不改变本机落盘形**（同一份 UTF-8 字节两种 flag 结果相同）——所以这条路径不按 bit 11 分叉。这不是"规范要求"，是**本机实现选择**（同 #9/#10 的性质） |
| `encoding.predictedNames["7zip"]` / `["libarchive"]` | 上表 #16 + 本机实测 | ✅ 两者在 bit 11 未置位时按**宿主 ANSI 代码页**（本机中文 Windows → GBK）解释字节，**不做字符集探测**：有效的 UTF-8 字节（`norm.zip` 的 `café`）照样被解成 `cafe茅.txt`。所以模型写"按声明的码页解"（可解释、可复现），`ANSI_CODEC` 是**环境事实**（换宿主要跟着换），不写"它会猜" |
| `encoding.UPATH_CRC_MISMATCH` | 上表 #7（§4.6.9 的 `NameCRC32`） | ✅ CRC 按**条目原名字节**校验（不是 utf8_name）；失配 → 覆盖失效 + 降级 `low` + 输出 finding。靶子 `tests/test_encoding.py::test_upath_crc_is_computed_over_raw_name_bytes` |
| `encoding.candidates[]`（`commonZone` 判据） | 本项目口径（§4.4） | ✅ 只用 `unicodedata.category`（`L*`/`M*`/`N*` + ASCII 可打印），**不做任何大小写/规范化变换**（K10 的实质靶子：`is_common_zone` 若用 `.lower()` 蒙混会在这里露出来） |
| `container.*` 五条 | 上表 #11/#12/#13/#14 | ✅ 逐条对上 EPUB 3.3 §4.3.3 / §4.3.2 与 ODF 1.2 p3 §3.3；`MIMETYPE_PADDING` 在 **ODF 上下文**标 `inferred: true`（#14），EPUB 上下文 `false`（#11 原文明文）。判据在 `tests/test_container.py::test_odf_padding_is_inferred_while_epub_padding_is_not` |
| `container.UTF8_REQUIRED` | 上表 #12（EPUB 3.3 §4.3.2） | ✅ 只对 **bit 11 未置位且名字非纯 ASCII** 的条目报：纯 ASCII 在 UTF-8 与 CP437 下同形，报它是假阳性。**ODF 上下文不套用**（那条依据属 OCF，不属 ODF） |
| `budget.PATH_OVER_260` | 上表 #1（MS Learn `MAX_PATH=260`）+ #15（Linux `{PATH_MAX}`） | ✅ Windows 按 **UTF-16 码元**（含终止 NUL）、Linux 按 **字节**；`evidence.platform` 必带（两个上限不是同一口径）。`evidence.kind = portability_budget` 且 `message` 不含"截断/创建失败"——U12 要求把"超预算"与"本机创建失败"分成两件事，靶子 `tests/test_budget.py::test_path_over_260_is_a_budget_warning_not_a_local_truncation` |
| `budget.COMPONENT_OVER_255` | 上表 #1 + #15 | ✅ Windows 按 UTF-16 码元、Linux 按**字节**（`{NAME_MAX}`）；按组件切（U19），`/` 是分隔符。`kind = platform_limit`（与 `PATH_OVER_260` 的预算告警区分） |

**禁令复核**：M5 三个模块的 `message` / `precedent` / `evidence` 里逐字检索过
「规范要求」「spec requires」「must be identical」「SHOULD match」，**零命中**；
`encoding.predictedNames` 的 `rule` 词表里也没有任何"规范"字样。判据 =
`tests/test_encoding.py::test_predictions_match_the_documented_truth` 与
`tests/test_container.py::test_mimetype_findings_carry_a_documented_precedent`
（后者断言 `precedent` 必须落在 `container.PRECEDENTS` 枚举里）。

**一处依据的诚实边界（不升级强度）**：`info-zip-unzip` 与 `7zip`/`libarchive` 的名字模型
**完全来自本机实测**（UnZip 6.00 Cygwin / 7-Zip 25.01 / bsdtar 3.8.4，2026-10-21）。APPNOTE 只
规定"历史 CP437"与"bit 11 置位则 MUST UTF-8"，**没有**规定实现该用哪个码页、或该不该探测字符集。
所以这三条在 `data/README.md` §4.12 里显式记为**实现选择**（与 #9/#10 的读头选择同一性质），
`source` 字段随每条预测一起输出（`cp850` / `gbk`），换宿主时要重测并重写那两个常量。
**拿到"逐格对得上"不等于拿到"规范背书"**——这条不能因为"实测全绿"被读成"依据变硬了"。
