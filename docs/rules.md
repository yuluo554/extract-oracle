# rules · 规则原句台账（骨架；M4 定稿）

> **本文件回答一个问题：每条判定到底引的是谁的原话？**
> 纪律：**没有原句就不写确定语气**。原句已核对 → 直引；只有要点转述 → 标 `⬜ 原句待回填`，M4 补齐。
> 数值口径不写在这里（唯一真相源是 `data/README.md` §4）；这里只管**依据与出处**。
>
> 列口径：`ruleId` = 输出里的规则标识（`plan/03`）；`原句` = 可逐字回到来源的引文（节选）；
> `强度` = `硬`（官方规范原文）/ `中硬`（实现观察或逆向文档）/ `推断`（从其他约束推出）。
>
> **逐条对应 `data/README.md` §1.4 的原表**（该表 12 行，`plan/HANDOFF-M1.md` §3 记作「11 条」——
> 差异在于本文件把「APPNOTE 未要求 LFH/CD 一致」单列一行、而把 ODF 尾随换行并入 ODF 行。
> 这里按 §1.4 逐行落地，**宁可多一行，不漏一条**）。

## 一、总表

| # | `ruleId` | 依据 | URL | 原句（节选） | 强度 | 状态 |
|---|---|---|---|---|---|---|
| 1 | `structure.*`（自证边界）、`budget.*` | MS Learn · 文件命名约定 | `https://learn.microsoft.com/en-us/windows/win32/fileio/naming-a-file` | "the file system treats path and file names as an **opaque sequence of WCHARs**" | 硬 | ✅ 原句已核对 |
| 2 | `collision.NFC`（macOS 侧） | UAX #15 · Unicode Normalization Forms | `https://www.unicode.org/reports/tr15/` | 定义 NFD/NFC 的规范分解与组合；**UAX #15 本身不谈文件系统**，FS 侧必须另引 TN1150 与实现观察 | 硬 | ⬜ 原句待回填（M4） |
| 3 | `collision.NFC`（macOS 侧） | TN1150 · HFS Plus Volume Format | `https://developer.apple.com/library/archive/technotes/tn/tn1150.html` | "HFS Plus stores strings fully decomposed and in canonical order" | 硬 | ✅ 原句已核对 |
| 4 | `collision.NFC`（macOS 侧）、`collision.CASEFOLD`（macOS 侧） | libfsapfs（逆向文档，**非 Apple 官方规范**） | `https://github.com/libyal/libfsapfs/blob/main/documentation/Apple%20File%20System%20(APFS).asciidoc` | 卷不兼容标志 `0x08 APFS_INCOMPAT_NORMALIZATION_INSENSITIVE`；name hash 用 NFD；大小写不敏感卷先 lower-case | 中硬 | ⬜ 原句待回填（M4）；**引用时必须写明"实现观察，非 Apple 官方规范"** |
| 5 | `accessibility`（Linux 侧）、`budget`（Linux 侧） | Linux `pathname(7)` | `https://man7.org/linux/man-pages/man7/pathname_resolution.7.html` | `/` 不可出现在文件名；`PATH_MAX` 为**字节**口径；`NAME_MAX` 由 fstype 决定 | 硬 | ⬜ 原句待回填（M4） |
| 6 | `encoding.*`（候选顺序与解码） | APPNOTE 6.3.10 D.1 / D.2（**镜像来源** `bearcove/rc-zip` `static/appnote.txt`） | `https://github.com/bearcove/rc-zip/blob/main/static/appnote.txt` | bit 11 set → **MUST** 为 UTF-8；unset → 历史 CP437 | 中硬（来源替代） | ⬜ 原句待回填（M4）；引用须写明**镜像来源与版本 v6.3.10** |
| 7 | `encoding.UPATH_CRC_MISMATCH`、`upath` 字段 | APPNOTE 6.3.10 D.6（同上镜像） | 同上 | Info-ZIP 0x7075（Unicode Path）/ 0x6375（Unicode Comment）的字段结构：`version(1) / name_crc32(4) / utf8_name` | 中硬（来源替代） | ⬜ 原句待回填（M4） |
| 8 | `structure.NAME_DIVERGES` 的**依据边界** | APPNOTE 6.3.10（逐字检索「must be identical」/「SHOULD match」**均无命中**） | 同上镜像 | **规范没有要求 LFH 与 CD 的名字一致** | — | ✅ 反向核对已做；此条是**禁令**：不得写成"规范要求一致" |
| 9 | `structure.NAME_DIVERGES` 的**实现选择** | libarchive issue #2695（作者 kientzle 本人） | `https://github.com/libarchive/libarchive/issues/2695` | "The seeking reader reads **BOTH** the central directory and the local file header… in case of a mismatch… it **always prefers the data in the local file header**" | 硬 | ✅ 原句已核对 |
| 10 | 同上（其他三个工具取 CD） | 同上 issue，fdegros（2026-09-24） | 同上 | "Info-ZIP's `unzip`, libzip, and Python's stdlib `zipfile` all read the Central Directory's filename. libarchive is the one that diverges here…" | 硬 | ✅ 原句已核对 |
| 11 | `container.MIMETYPE_NOT_FIRST` / `MIMETYPE_COMPRESSED` / `MIMETYPE_EXTRA` / `MIMETYPE_PADDING` | EPUB 3.3 §4.3.3 · OCF ZIP Container | `https://www.w3.org/TR/epub-33/#sec-zip-container-zipreqs` | "MUST include the `mimetype` file as the **first** file"；"MUST NOT contain any leading or trailing padding or whitespace"；"MUST NOT compress or encrypt"；"MUST NOT include an extra field" | 硬 | ✅ 原句已核对 |
| 12 | `container.UTF8_REQUIRED` | EPUB 3.3 §4.3.2 · OCF ZIP Container | `https://www.w3.org/TR/epub-33/#sec-zip-container-mime` | "OCF ZIP containers MUST encode file system names using **UTF-8**" | 硬 | ✅ 原句已核对 |
| 13 | `container.*`（ODF 上下文） | ODF 1.2 part 3 §3.3 · Packages | `https://docs.oasis-open.org/office/v1.2/os/OpenDocument-v1.2-os-part3.html` | "shall be the first file"；"shall not be compressed… shall not use an 'extra field'" | 硬 | ✅ 原句已核对 |
| 14 | `container.MIMETYPE_PADDING`（ODF 上下文，带 `inferred: true`） | 从 media-type 相等约束推出 | 同上 | **ODF 原文未明文禁止尾随换行** | 推断 | ✅ 已标注 `inferred`；**不得**写成 ODF 明文要求 |

> 强度纪律（`data/README.md` §5）：任何 `中硬`/`推断` 项，输出必须带对应标记
> （`evidence_strength: medium` / `inferred: true`），且文档不得用确定语气。

## 二、`ruleId` → 依据 反查表（M4 补齐到逐规则粒度）

| `ruleId` | 主依据（上表 #） | 备注 |
|---|---|---|
| `structure.NAME_DIVERGES` | 9, 10（+ 8 的禁区） | 只引实现选择；**不得**引"规范要求一致" |
| `structure.CRC_DIVERGES` | 8（结构自证）+ APPNOTE 字段定义 | bit 3（data descriptor）置位且 LFH 为 0 时豁免 |
| `structure.SIZE_DIVERGES` | 同上 | 同上 |
| `structure.FLAG_DIVERGES` | 同上 | 全 16 位比较 |
| `structure.LFH_OVERLAP` | 结构自证 | 物理区间相交，不需要外部依据 |
| `structure.CD_COUNT_MISMATCH` | APPNOTE EOCD 字段定义 | ZIP64 路径单独处理 |
| `encoding.*` | 6, 7 | 候选顺序见 `data/README.md` §4.4 |
| `encoding.UPATH_CRC_MISMATCH` | 7 | 校验失配 → 降级 `low` |
| `collision.CASEFOLD` | 4（macOS）+ 本机 `$UpCase` 实测（Windows） | Windows 侧依据是**数据表**，不是规范条文 |
| `collision.NFC` | 2, 3, 4 | macOS 必报、Windows/Linux 不报 |
| `collision.TRIM` | 1 | 仅 Windows |
| `collision.FILEDIR` | 结构自证 | 三平台都报（M1 实测，见下 §三） |
| `accessibility.*` | 1, 5 | 三级定义在 `data/README.md` §4.2 |
| `container.*` | 11, 12, 13 | ODF 尾随换行标 `inferred` |
| `budget.*` | 1, 5 | 数值见 `data/README.md` §4.6 |

## 三、M1 实测对既有表述的修正（必须先看这里再动 M2/M3/M4）

M1 的本机实测（`plan/05` §五 U11）推翻了 `data/README.md` 与 `plan/03` 的三处初版表述。
**以实测为准**，四处文档已同步改：

| 初版表述 | 实测结果 | 影响 |
|---|---|---|
| `:` 属 Windows 非法字符 → `BLOCKED` | `CreateFileW('colon:name.txt')` **成功**，NTFS 按 ADS 语义只存 `colon` | `trailing.zip` 的 `colon:name.txt` 改判 `WRITTEN_TRUNCATED`（名字变了），**不是** `BLOCKED` |
| 保留名「含扩展名形式」即不可读 | 只按**最后一个点之前**整体匹配：`AUX.txt`/`AUX.tar` 不可读，`aux.tar.gz` **真可读**（`Test-Path`=True） | `reserved.zip` 的 `aux.tar.gz` 改判 `OK` |
| 组件超长 → 截断（`WRITTEN_TRUNCATED`） | 单组件 256 码元 `CreateFileW` **直接失败**（`ERROR_INVALID_NAME` 123），加 `\\?\` 前缀也一样 | `long_comp.zip` 改判 `BLOCKED`；`budget.COMPONENT_OVER_255` 仍是告警，但可访问性级别不是截断 |
| （新增）`İ/i` 折叠 | **不冲突**（`ı/I`、`ſ/S`、`ß/SS`、`ß/ss`、`ǅ/Ǆ` 同样不冲突；`ω/Ω`、`é/É` 冲突） | 见 §四；`data/README.md` §1.3.3 的 `İ/i` 一行标 ⬜ 待复核 |

## 四、8 组字符对：本机复核结果（M1，2026-10-21）

实测方法：在 NTFS 卷上先写 A 再 `CREATE_NEW` 建 B，`ERROR_ALREADY_EXISTS`/`ERROR_FILE_EXISTS` 即折叠。
三种独立手段（`CreateFileW` / Python `open(...,'xb')` / bash `touch`）结论一致。

| 字符对 | `str.upper()` 预测 | `str.casefold()` 预测 | **本机 NTFS 实测** | `data/README.md` §1.3.3 原表 |
|---|---|---|---|---|
| `ı` / `I` | 冲突 | 不冲突 | **不冲突** | 不冲突 ✓ |
| `ſ` / `S` | 冲突 | 不冲突 | **不冲突** | 不冲突 ✓ |
| `ß` / `SS` | 冲突（`ß`.upper() = `SS`） | 不冲突 | **不冲突** | 不冲突 ✓ |
| `ß` / `ss` | 冲突（`ß`.upper() = `SS` ≠ `ss`，但 `ß`.lower() 同形） | 冲突 | **不冲突** | 不冲突 ✓ |
| `İ` / `i` | 不冲突（`İ`.upper() = `İ`） | 不冲突（`İ`.casefold() = `i̇`） | **不冲突** | **冲突 ✗（原表待复核）** |
| `ǅ` / `Ǆ` | 冲突 | 冲突 | **不冲突** | 不冲突 ✓ |
| `ω` / `Ω` | 冲突 | 冲突 | **冲突** | 冲突 ✓ |
| `é` / `É`（对照组） | 冲突 | 冲突 | **冲突** | 不冲突 ✗（原表对照组的取值待复核） |

**结论不变、且更强**：`str.lower()`/`str.casefold()` 与真实 NTFS 折叠**不等价** ——
`ǅ/Ǆ` 上 `casefold` 判冲突而 NTFS 不冲突；`İ/i` 上两边都判不冲突而原表记的是冲突。
**所以 MOD-3 必须用真实 `$UpCase` 表**（`data/platforms/ntfs-upcase.bin`，来源 `host_probe`，
带真实卷实测校验），这条决策（`plan/00` 决策 ③）不受本表任何一行取值影响。

> 逐字符的完整表（65536 项）与那 8 组的机器可读结果在 `data/platforms/meta.json` 的
> `ntfs_upcase.verification.pairs` 里；本表只是人读摘要。

## 五、待办（M4 收口清单）

- [ ] #2 / #4 / #5 / #6 / #7 五行的原句回填（当前只有要点转述 → 不得在 M2–M5 的输出里当"直引"用）
- [ ] `ruleId` → 依据 反查表补齐到**每条规则一个 `#` 行号**（现在有 6 条是"集合引用"）
- [ ] `İ/i` 与 `é/É` 两行与 `data/README.md` §1.3.3 的差异裁决（要么改 §1.3.3，要么给出复核条件）
- [ ] APFS 行必须在正文里重复写"实现观察，非 Apple 官方规范"（`plan/00` 决策 ④）

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
