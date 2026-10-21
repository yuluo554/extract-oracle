# divergence · 四工具提取行为实测对照（M6 定稿）

> **本文是什么**：`plan/01` §1.2 从竞品"明写不做"清单里读出的**三处阵地**——① 双头差分与重叠检测、
> ② 编码推断与 Unicode path extra field、③ 真实文件系统折叠表——的**实测对照面**。
> 原料是 `data/tool-matrix/` 的 **22 份 fixture × 4 个提取器 = 88 格**；本文是它的定稿叙述，
> **每格都带实测命令 + 退出码 + 实际落盘名 + 输出节选**（§六 的索引矩阵逐格标出该格在哪一节）。
>
> **复跑**：`py -3.12 tools/probe_tools.py`（重跑并写盘）／
> `py -3.12 tools/probe_tools.py --check`（只比对，逐字节比 22 份 `<fixture>.zip.json` + `_summary.json`）。
> **手抄表不能回归**——原料一律由脚本落盘，本文只负责读它、不负责生成它。
> 工具缺失时该脚本退 **3**（不静默跳过，否则矩阵看起来"全绿"）。
>
> **实测环境**（与 `data/README.md` 首页同一份，原样记录）：Windows 10.0.26200.8246 / NTFS
> （`LongPathsEnabled=1`）；Python 3.12.10（`unicodedata` 15.0.0）；7-Zip 25.01；
> Info-ZIP UnZip 6.00（Cygwin 构建，`UNICODE_SUPPORT`）；libarchive 3.8.4（Windows 自带 `tar.exe`，即 bsdtar）。
>
> **节选纪律**：节选只做两处替换——临时目录 → `<workdir>`、盘符路径 → `<path>`
> （`tools/probe_tools.py::_sanitize`）。其余是**原文**，不改写、不转述、不补全。
> 本文**不含**本机绝对路径、用户名、时间戳（`data/README.md` §4.8 的同一条纪律）。
>
> **本文与判定面的关系**：这里只记**观察到的行为**。把行为变成 `ruleId` / `collision` /
> `accessibility` 的判定在 `data/README.md` §4、`docs/rules.md` 与 `src/extract_oracle/rules/`。
> 两条纪律分开：**"谁做了什么"在本文，"我们据此判什么"在口径文档。**

---

## 一、怎么读这张表（三个前置事实）

### 1.1 四个提取器的身份与命令模板

| 工具 | 自报版本首行（`_summary.json.tool_versions` 原样） | 实测命令模板 |
|---|---|---|
| `python-zipfile` | `Python 3.12.10 (stdlib zipfile)` | `python -m zipfile -e <fixture> <workdir>/out` |
| `info-zip-unzip` | `UnZip 6.00 of 20 April 2009, by Info-ZIP.  Maintained by C. Spieler.  Send` | `unzip -o <fixture> -d <workdir>/out` |
| `7zip` | `7-Zip 25.01 (x64) : Copyright (c) 1999-2025 Igor Pavlov : 2025-08-03` | `7z x -y -o<workdir>/out <fixture>` |
| `libarchive` | `bsdtar 3.8.4 - libarchive 3.8.4 zlib/1.2.13.1-motley liblzma/5.8.1 bz2lib/1.0.8 libzstd/1.5.7 cng/2.0 libb2/bundled` | `bsdtar -x -f <fixture> -C <workdir>/out` |

命令里的 `<fixture>` 是 `data/fixtures/<name>` 的绝对路径（子进程的 `cwd` 是临时目录，相对路径会找不到），
`<workdir>` 是每次探测新建、`finally` 里删掉的临时目录。**解压只发生在这两个临时目录里**
（`data/README.md` §3.1 的"不解压到磁盘"红线指**产物形态**；本文的复跑脚本是测量工具，其临时产物不入库、不进产物）。

### 1.2 三条读表纪律

1. **`rc` 是工具自己返回的退出码，不是本工具的判定**。四家的码制互不相同（`unzip` 用 50 = 写盘失败、
   3 = 致命结构错；`7z` 用 2 = 致命错；`bsdtar` 用 1 = "有错但继续"），所以**跨工具比 `rc` 的数值没有意义**，
   要比的是"它认为成不成功"这一列（本文用 `0` / `非 0` / `拒绝` 三态读）。
2. **`python-zipfile` 那一格是库调用，不是子进程**——脚本在进程内 `ZipFile(...)` + `extractall()`，
   捕获任何异常记 `status = refused`（此时**没有**退出码）。所以该格的 `written` 是
   **异常抛出前已经落盘的那部分**（`mismatch_name.zip` / `long_comp.zip` 是空、`filedir.zip` 留下了一个 `a`），
   而 `error` 列是**库抛出的原话**。这与 `data/README.md` §1.3.1 / `plan/05` §五 U13 记的那件事是同一个：
   Python 在双头不一致时 `namelist()` 取 CD 名、`read()` 才拒绝——本文按"它到底有没有拒绝"记。
3. **"实际落盘名"来自解压后目录的枚举**（`os.walk`），不是工具自报、不是从归档里读出来的。
   名字超过 64 字符时按 `<前 52 字>…<后 8 字>（共 N 字符）` 截断显示；**完整值在
   `data/tool-matrix/<fixture>.json`**。另外：`CON.txt` 这类名字**能被目录枚举列出**、
   却不能被应用层按字面路径打开——那是 MOD-4 的领域，实测三证据在 `data/README.md` §1.3.2，
   本文只记"目录里有没有这个名字"。

### 1.3 三处阵地与 22 份样本的对应（本文的组织方式）

| 节 | 阵地（`plan/01` §1.2） | 覆盖的 fixture | 格数 |
|---|---|---|---|
| §二 | ① 双头差分与重叠检测 | `mismatch_name` / `alias_lfh` / `overlap` / `wrong_count` / `crc_diverge` / `size_diverge` | 6 × 4 = 24 |
| §三 | ② 编码推断与 Unicode path extra field | `zh_gbk` / `upath` / `upath_badcrc` | 3 × 4 = 12 |
| §四 | ③ 真实文件系统折叠表 | `case` / `norm` / `trim` / `filedir` / `reserved` / `trailing` | 6 × 4 = 24 |
| §五 | 非三处阵地的其余样本（容器 / 预算 / 零误报基线） | 4 份 `.epub` / `long_path` / `long_comp` / `clean` | 7 × 4 = 28 |
| — | 合计 | **22** | **88** |

`norm.zip` 只出现在 §四（它是 MOD-3 的核心样本）；它在 §三 的**编码层读法**（同一份字节被四家解成
两套名字）由 §三.3 交叉引用，不重复列表——**同一份实测只写一次**。

---

## 二、第一处阵地：双头差分与重叠检测（MOD-1）

`plan/01` §1.2 引竞品 `Hhhxsss/zip-preflight` 的 `docs/rules.md` 原话："local-header comparison,
**overlapping-entry detection**… **the tool does not guess encodings** is performed."
这一节就是那两件事的实测面。

**这一节最重要的一句结论**：分歧不在"名字合不合规"——`allowed.txt` 与 `evil.txt` 两个名字都完全合规——
而在**读哪个头**。这是**实现选择**，不是规范条文（`docs/rules.md` §一 #8：逐字检索 APPNOTE 6.3.10，
"must be identical" / "SHOULD match" **均无命中**）。

### 2.1 `mismatch_name.zip`（LFH 名 `allowed.txt` / CD 名 `evil.txt`）

**四工具三种结果，一个直接拒绝**：Python 拒绝、`unzip` 取 **CD** 名写 `evil.txt`、
`7zip` 与 `libarchive` 取 **LFH** 名写 `allowed.txt`。unzip 的输出把"它明知不一致还继续"写得最清楚。

| 工具 | 实测命令 | 退出码 | 实际落盘名 | 输出节选（原文） |
|---|---|---|---|---|
| `python-zipfile` | `python -m zipfile -e <fixture> <workdir>/out` | 拒绝<br>（`refused`） | **（无）** | `BadZipFile: File name in directory 'evil.txt' and header b'allowed.txt' differ.` |
| `info-zip-unzip` | `unzip -o <fixture> -d <workdir>/out` | 1 | `evil.txt` | Archive:  <path><br> extracting: <workdir>\out/evil.txt<br>evil.txt:  mismatching "local" filename (allowed.txt),<br>         continuing with "central" filename version |
| `7zip` | `7z x -y -o<workdir>/out <fixture>` | 2 | `allowed.txt` | 7-Zip 25.01 (x64) : Copyright (c) 1999-2025 Igor Pavlov : 2025-08-03<br>Scanning the drive for archives:<br>1 file, 127 bytes (1 KiB)<br>Extracting archive: <path><br>--<br>Path = <path> |
| `libarchive` | `bsdtar -x -f <fixture> -C <workdir>/out` | 0 | `allowed.txt` | （无 stdout/stderr） |

`distinct_written_sets = 3` ／ `tools_agree = false`

### 2.2 `alias_lfh.zip`（名字一致，LFH flag `0x0000` / CD flag `0x0800`）

**四家落盘名一致，只有一家出声**：名字相同 → 四个工具都写 `same.txt`；但 `unzip` 的
bit 11 不一致检查让它退 `1` 并打印警告。这条样本证明"落盘名一致"**不等于**"无分歧"——
分歧在**标志位层**，只看文件名会漏掉它（这正是 `structure.FLAG_DIVERGES` 存在的理由）。

| 工具 | 实测命令 | 退出码 | 实际落盘名 | 输出节选（原文） |
|---|---|---|---|---|
| `python-zipfile` | `python -m zipfile -e <fixture> <workdir>/out` | 0 | `same.txt` | （无 stdout/stderr） |
| `info-zip-unzip` | `unzip -o <fixture> -d <workdir>/out` | 1 | `same.txt` | Archive:  <path><br> extracting: <workdir>\out/same.txt<br>file #1 (same.txt):<br>         mismatch between local and central GPF bit 11 ("UTF-8"),<br>         continuing with central flag (IsUTF8 = 1) |
| `7zip` | `7z x -y -o<workdir>/out <fixture>` | 0 | `same.txt` | 7-Zip 25.01 (x64) : Copyright (c) 1999-2025 Igor Pavlov : 2025-08-03<br>Scanning the drive for archives:<br>1 file, 124 bytes (1 KiB)<br>Extracting archive: <path><br>--<br>Path = <path> |
| `libarchive` | `bsdtar -x -f <fixture> -C <workdir>/out` | 0 | `same.txt` | （无 stdout/stderr） |

`distinct_written_sets = 1` ／ `tools_agree = true`（**但 unzip 退 1**）

### 2.3 `overlap.zip`（两个 LFH 记录区间物理相交）

**只有 Python 认得出这是重叠**：`BadZipFile: Overlapped entries: 'a.txt' (possible zip bomb)`；
另外三家 `rc = 0` 照解出两个文件。这是"重叠检测"这个能力名词最直白的一格：
**归档里根本看不出异常，只有一个实现拒绝**。

| 工具 | 实测命令 | 退出码 | 实际落盘名 | 输出节选（原文） |
|---|---|---|---|---|
| `python-zipfile` | `python -m zipfile -e <fixture> <workdir>/out` | 拒绝<br>（`refused`） | **（无）** | `BadZipFile: Overlapped entries: 'a.txt' (possible zip bomb)` |
| `info-zip-unzip` | `unzip -o <fixture> -d <workdir>/out` | 0 | `a.txt`<br>`b.txt` | Archive:  <path><br> extracting: <workdir>\out/a.txt<br> extracting: <workdir>\out/b.txt |
| `7zip` | `7z x -y -o<workdir>/out <fixture>` | 0 | `a.txt`<br>`b.txt` | 7-Zip 25.01 (x64) : Copyright (c) 1999-2025 Igor Pavlov : 2025-08-03<br>Scanning the drive for archives:<br>1 file, 204 bytes (1 KiB)<br>Extracting archive: <path><br>--<br>Path = <path> |
| `libarchive` | `bsdtar -x -f <fixture> -C <workdir>/out` | 0 | `a.txt`<br>`b.txt` | （无 stdout/stderr） |

`distinct_written_sets = 2` ／ `tools_agree = false`

### 2.4 `wrong_count.zip`（EOCD 声明 5 条，实际 CD 2 条）

**计数不一致时四家的"成功"定义四分五裂**：两个文件**都**被写出来了，但 `unzip` 退 `3`（致命）、
`7z` 退 `2`（致命）、`bsdtar` 退 `0`、Python 退 `0`。**"落盘名一致 + 退出码从 0 到 3 都有"**——
这条样本是"退出码撒谎"的最好例证：CI 只看文件在不在，会以为一切正常。

| 工具 | 实测命令 | 退出码 | 实际落盘名 | 输出节选（原文） |
|---|---|---|---|---|
| `python-zipfile` | `python -m zipfile -e <fixture> <workdir>/out` | 0 | `alpha.txt`<br>`beta.txt` | （无 stdout/stderr） |
| `info-zip-unzip` | `unzip -o <fixture> -d <workdir>/out` | 3 | `alpha.txt`<br>`beta.txt` | Archive:  <path><br> extracting: <workdir>\out/alpha.txt<br> extracting: <workdir>\out/beta.txt<br>error:  expected central file header signature not found (file #3).<br>  (please check that you have transferred or created the zipfile in the<br>  appropriate BINARY mode and that you have compiled UnZip properly) |
| `7zip` | `7z x -y -o<workdir>/out <fixture>` | 2 | `alpha.txt`<br>`beta.txt` | 7-Zip 25.01 (x64) : Copyright (c) 1999-2025 Igor Pavlov : 2025-08-03<br>Scanning the drive for archives:<br>1 file, 228 bytes (1 KiB)<br>Extracting archive: <path><br>--<br>Path = <path> |
| `libarchive` | `bsdtar -x -f <fixture> -C <workdir>/out` | 0 | `alpha.txt`<br>`beta.txt` | （无 stdout/stderr） |

`distinct_written_sets = 1` ／ `tools_agree = true`（**但退出码是 0/0/2/3 四种**）

### 2.5 `crc_diverge.zip`（CD 的 CRC32 = LFH 的 CRC 翻转最低位）

**三家报错、一家照收**：Python 拒绝、`bsdtar` 退 `1` 并明说 `Inconsistent CRC32 values`、
`7z` 退 `2`，而 **`unzip` 退 0 什么也没说**。同一份归档，"校验严不严"完全取决于用谁。

| 工具 | 实测命令 | 退出码 | 实际落盘名 | 输出节选（原文） |
|---|---|---|---|---|
| `python-zipfile` | `python -m zipfile -e <fixture> <workdir>/out` | 拒绝<br>（`refused`） | `crc.txt` | `BadZipFile: Bad CRC-32 for file 'crc.txt'` |
| `info-zip-unzip` | `unzip -o <fixture> -d <workdir>/out` | 0 | `crc.txt` | Archive:  <path><br> extracting: <workdir>\out/crc.txt |
| `7zip` | `7z x -y -o<workdir>/out <fixture>` | 2 | `crc.txt` | 7-Zip 25.01 (x64) : Copyright (c) 1999-2025 Igor Pavlov : 2025-08-03<br>Scanning the drive for archives:<br>1 file, 122 bytes (1 KiB)<br>Extracting archive: <path><br>--<br>Path = <path> |
| `libarchive` | `bsdtar -x -f <fixture> -C <workdir>/out` | 1 | `crc.txt` | tar.exe: Inconsistent CRC32 values<br>tar.exe: Error exit delayed from previous errors. |

`distinct_written_sets = 1` ／ `tools_agree = true`

### 2.6 `size_diverge.zip`（CD 的 uncompressed size 比 LFH 多 7）

与 CRC 那一份**方向不同**：这次 `bsdtar` 明说两个头声明的大小不一致（`17 in central directory,
10 in local header`）、`7z` 退 `2`，而 **Python 照收退 `0`**（只有 `read()` 时 CRC 才会拦它，
size 不拦）。同一族样本、不同的工具组合——**"分歧方向"本身是这条能力的产物**。

| 工具 | 实测命令 | 退出码 | 实际落盘名 | 输出节选（原文） |
|---|---|---|---|---|
| `python-zipfile` | `python -m zipfile -e <fixture> <workdir>/out` | 0 | `size.txt` | （无 stdout/stderr） |
| `info-zip-unzip` | `unzip -o <fixture> -d <workdir>/out` | 0 | `size.txt` | Archive:  <path><br> extracting: <workdir>\out/size.txt |
| `7zip` | `7z x -y -o<workdir>/out <fixture>` | 2 | `size.txt` | 7-Zip 25.01 (x64) : Copyright (c) 1999-2025 Igor Pavlov : 2025-08-03<br>Scanning the drive for archives:<br>1 file, 124 bytes (1 KiB)<br>Extracting archive: <path><br>--<br>Path = <path> |
| `libarchive` | `bsdtar -x -f <fixture> -C <workdir>/out` | 1 | `size.txt` | tar.exe: Inconsistent uncompressed size: 17 in central directory, 10 in local header<br>tar.exe: Error exit delayed from previous errors. |

`distinct_written_sets = 1` ／ `tools_agree = true`

---

## 三、第二处阵地：编码推断与 Unicode path extra field（MOD-2）

`plan/01` §1.2 引竞品原话："alternate Unicode-path extra-field interpretation… **the tool does not
guess encodings**."这一节是文件名解码与 `0x7075` 的两面。

**这一节最重要的两句结论**（都是本机实测推翻初版表述的地方，见 §三.4）：
**① 四家都不"猜"**——`7zip` / `libarchive` 在 bit 11 未置位时按**宿主 ANSI 代码页**解（本机中文 Windows → GBK），
**有效的 UTF-8 字节照样解成乱码**；**② `unzip` 的落盘名与 bit 11 无关**——同一份字节，flag 置位与否给出**同一**结果。

### 3.1 `zh_gbk.zip`（无 bit 11，名字是 GBK 字节 `中文名.txt`）

**三种落盘名，两份相同**：`7zip` 与 `libarchive` 都出 `中文名.txt`（按 GBK 解对了），
Python 出 CP437 回退的 `╓╨╬─├√.txt`，`unzip` 出 CP850 + OEM→ANSI best-fit 的 `Íð+-+¹.txt`。
**注意 unzip 的 stdout 里那串 `��+-+�` 是控制台转写**，真实落盘名是表中那一列（这正是
"读控制台不如读目录"的例证）。

| 工具 | 实测命令 | 退出码 | 实际落盘名 | 输出节选（原文） |
|---|---|---|---|---|
| `python-zipfile` | `python -m zipfile -e <fixture> <workdir>/out` | 0 | `╓╨╬─├√.txt` | （无 stdout/stderr） |
| `info-zip-unzip` | `unzip -o <fixture> -d <workdir>/out` | 0 | `Íð+-+¹.txt` | Archive:  <path><br> extracting: <workdir>\out/��+-+�.txt |
| `7zip` | `7z x -y -o<workdir>/out <fixture>` | 0 | `中文名.txt` | 7-Zip 25.01 (x64) : Copyright (c) 1999-2025 Igor Pavlov : 2025-08-03<br>Scanning the drive for archives:<br>1 file, 129 bytes (1 KiB)<br>Extracting archive: <path><br>--<br>Path = <path> |
| `libarchive` | `bsdtar -x -f <fixture> -C <workdir>/out` | 0 | `中文名.txt` | （无 stdout/stderr） |

`distinct_written_sets = 3` ／ `tools_agree = false`

### 3.2 `upath.zip`（无 bit 11，带 `0x7075`，CRC **有效**，指向 `café.txt`）

**四家一致**：`0x7075` 的 CRC 通过 → 覆盖生效 → 四个工具都写 `café.txt`，全部退 `0`。
这条样本的意义是**否定性的**：它证明"有 `0x7075` 就会分歧"不成立——**CRC 有效时四家都听它的**。
（`docs/rules.md` §六 的更正 #2 就是这条：`plan/03` §MOD-2 原验收句"7-Zip 出 `café.txt` 而
Python/unzip 出 `caf茅.txt`"**不成立**，要展示编码分歧得用 §3.3 那份。）

| 工具 | 实测命令 | 退出码 | 实际落盘名 | 输出节选（原文） |
|---|---|---|---|---|
| `python-zipfile` | `python -m zipfile -e <fixture> <workdir>/out` | 0 | `café.txt` | （无 stdout/stderr） |
| `info-zip-unzip` | `unzip -o <fixture> -d <workdir>/out` | 0 | `café.txt` | Archive:  <path><br> extracting: <workdir>\out/café.txt |
| `7zip` | `7z x -y -o<workdir>/out <fixture>` | 0 | `café.txt` | 7-Zip 25.01 (x64) : Copyright (c) 1999-2025 Igor Pavlov : 2025-08-03<br>Scanning the drive for archives:<br>1 file, 165 bytes (1 KiB)<br>Extracting archive: <path><br>--<br>Path = <path> |
| `libarchive` | `bsdtar -x -f <fixture> -C <workdir>/out` | 0 | `café.txt` | （无 stdout/stderr） |

`distinct_written_sets = 1` ／ `tools_agree = true`

### 3.3 `upath_badcrc.zip`（同上，但 `0x7075` 的 CRC 取反 → 覆盖失效）

**四方分歧**（与 §3.1 同名的三套结果 + 一条新证据）：CRC 失配 → `unzip` 照样**只有一句警告**
（`warning:  Unicode Path checksum invalid`，退 `0`）然后落盘它自己的 best-fit 名；
`7zip` / `libarchive` 转而按 ANSI 码页解出 `中文名.txt`；Python 回退 CP437。
**同一个字节流，"CRC 对不对"这一个比特把四家分成三组。**

| 工具 | 实测命令 | 退出码 | 实际落盘名 | 输出节选（原文） |
|---|---|---|---|---|
| `python-zipfile` | `python -m zipfile -e <fixture> <workdir>/out` | 0 | `╓╨╬─├√.txt` | （无 stdout/stderr） |
| `info-zip-unzip` | `unzip -o <fixture> -d <workdir>/out` | 0 | `Íð+-+¹.txt` | Archive:  <path><br> extracting: <workdir>\out/��+-+�.txt<br>warning:  Unicode Path checksum invalid<br>warning:  Unicode Path checksum invalid |
| `7zip` | `7z x -y -o<workdir>/out <fixture>` | 0 | `中文名.txt` | 7-Zip 25.01 (x64) : Copyright (c) 1999-2025 Igor Pavlov : 2025-08-03<br>Scanning the drive for archives:<br>1 file, 166 bytes (1 KiB)<br>Extracting archive: <path><br>--<br>Path = <path> |
| `libarchive` | `bsdtar -x -f <fixture> -C <workdir>/out` | 0 | `中文名.txt` | （无 stdout/stderr） |

`distinct_written_sets = 3` ／ `tools_agree = false`

### 3.4 本节的两处实测收窄（对 `plan/03` §MOD-2 初版表述的更正）

这两条是 M5 实测**推翻**初版写法的结果，M6 定稿**不得照抄旧表述**：

| 初版表述（`plan/03` §MOD-2） | 本机实测 | 现在的写法 |
|---|---|---|
| "`7z` → 多编码猜测" | **`7zip` / `libarchive` 不做字符集探测**：它们按**宿主 ANSI 代码页**解释字节。`norm.zip` 里**有效的 UTF-8 字节**（`café`，bit 11 未置位）被解成 `cafe茅.txt` ——**有效的 UTF-8 都没被认出来**，可见没有"探测"这一步 | 模型写"**按声明的码页解**"，`encoding.ANSI_CODEC = "gbk"` 是**环境事实**（换宿主要重测并重写它），不写"它会猜" |
| "`unzip` 按 locale / bit 11 解码" | **`info-zip-unzip` 的落盘名与 bit 11 无关**：同一份 UTF-8 字节，flag 置位与未置位给出**同一**结果；且它走 **CP850 解码 + OEM→ANSI best-fit**（128 个高位字节逐字节对照：CP850 命中 **95/128**，CP437 只命中 **50**） | `predictedNames["info-zip-unzip"]` 不按 bit 11 分叉；`source` 字段显式标 `cp850`（`data/README.md` §4.12、`docs/rules.md` §八） |

> **为什么不能用"它应该会猜"来写**：APPNOTE 只说"历史上是 CP437"（D.1）与"bit 11 置位则 **MUST** 为
> UTF-8"（D.2），**没有**规定实现该用哪个码页、或该不该探测字符集。所以这三条是**实现选择**
> （与 #9/#10 的读头选择同一性质），只能按实测写——**拿到"逐格对得上"不等于拿到"规范背书"**。

---

## 四、第三处阵地：真实文件系统折叠表（MOD-3）

`plan/01` §1.2 引竞品 `cloudwallker/archive-preflight` 的 `Policies` 自认："casefold is an
**approximation**"；"Native NTFS/APFS comparison tables… **require host testing**."
这一节是"落盘后谁覆盖谁"的实测面——**注意：本节四家的差异有相当一部分来自 §三 的解码差异，
所以读每一格时先看名字是不是同一套字节解出来的**（`norm.zip` 尤其明显）。

### 4.1 `case.zip`（`Readme.txt` + `README.TXT`，payload 分别为 `UPPER` / `LOWER`）

**落盘名分歧 + 存活者一致**：`unzip` / `7zip` / `libarchive` 都只剩 `README.TXT`（后写者覆盖，
与 `plan/01` §1.1 实测的"内容为 `LOWER`"一致），而 **Python 落 `Readme.txt`**——
注意它写的是**先写者**的名字：`extractall` 在 NTFS 上的覆盖行为让目录里只剩一个名字，
但留下来的**那一个是 Python 自己最后写的拼写**。这一格就是"**不只说会冲突，还说最后剩谁**"的原料。

| 工具 | 实测命令 | 退出码 | 实际落盘名 | 输出节选（原文） |
|---|---|---|---|---|
| `python-zipfile` | `python -m zipfile -e <fixture> <workdir>/out` | 0 | `Readme.txt` | （无 stdout/stderr） |
| `info-zip-unzip` | `unzip -o <fixture> -d <workdir>/out` | 0 | `README.TXT` | Archive:  <path><br> extracting: <workdir>\out/Readme.txt<br> extracting: <workdir>\out/README.TXT |
| `7zip` | `7z x -y -o<workdir>/out <fixture>` | 0 | `README.TXT` | 7-Zip 25.01 (x64) : Copyright (c) 1999-2025 Igor Pavlov : 2025-08-03<br>Scanning the drive for archives:<br>1 file, 226 bytes (1 KiB)<br>Extracting archive: <path><br>--<br>Path = <path> |
| `libarchive` | `bsdtar -x -f <fixture> -C <workdir>/out` | 0 | `README.TXT` | （无 stdout/stderr） |

`distinct_written_sets = 2` ／ `tools_agree = false`

### 4.2 `norm.zip`（NFC `café.txt` + NFD `café.txt`）

**四家落盘名两套、六个不同名字**：`7zip` 与 `libarchive` 落 `cafe茅.txt` + `cafe虂.txt`
（**这正是 §三.4 那条收窄的现场**——两条**有效的 UTF-8 名字**被按 GBK 解成乱码，
所以"两条名字互相折叠"这件事在它们那儿根本没发生，它们拿到的是两个不相干的乱码名）；
`unzip` 落 `caf+®.txt` + `cafe¦ü.txt`；Python 落 CP437 形的 `caf├⌐.txt` + `cafe╠ü.txt`。
**没有一个工具落出 `café.txt`**。这一格同时说明两件事：**编码分歧会先于折叠分歧发生**，
而且"NTFS 不做归一化"这条只在名字正确解出来之后才谈得上
（判定口径见 `data/README.md` §4.3：`norm.zip --target windows` 不报、`--target macos` 必报 `collision.NFC`）。

| 工具 | 实测命令 | 退出码 | 实际落盘名 | 输出节选（原文） |
|---|---|---|---|---|
| `python-zipfile` | `python -m zipfile -e <fixture> <workdir>/out` | 0 | `cafe╠ü.txt`<br>`caf├⌐.txt` | （无 stdout/stderr） |
| `info-zip-unzip` | `unzip -o <fixture> -d <workdir>/out` | 0 | `caf+®.txt`<br>`cafe¦ü.txt` | Archive:  <path><br> extracting: <workdir>\out/caf+�.txt<br> extracting: <workdir>\out/cafe��.txt |
| `7zip` | `7z x -y -o<workdir>/out <fixture>` | 0 | `cafe虂.txt`<br>`caf茅.txt` | 7-Zip 25.01 (x64) : Copyright (c) 1999-2025 Igor Pavlov : 2025-08-03<br>Scanning the drive for archives:<br>1 file, 236 bytes (1 KiB)<br>Extracting archive: <path><br>--<br>Path = <path> |
| `libarchive` | `bsdtar -x -f <fixture> -C <workdir>/out` | 0 | `cafe虂.txt`<br>`caf茅.txt` | （无 stdout/stderr） |

`distinct_written_sets = 3` ／ `tools_agree = false`

### 4.3 `trim.zip`（`readme.` + `readme`）

**"尾随点"的处理四分五裂**：Python 落 `readme`（一个，尾随点被 NTFS 裁掉后与另一条重合）；
`unzip` / `libarchive` 落 `readme` **和** `readme.` **两个**（尾随点原样保留，NTFS 层再裁）；
`7zip` 落 `readme` + `readme_`（它自己给尾随点改名加 `_`，**没有**让两者相撞）。
表里的 `readme.` 那一行是"目录里真的能列出这个拼写"的直接证据。

| 工具 | 实测命令 | 退出码 | 实际落盘名 | 输出节选（原文） |
|---|---|---|---|---|
| `python-zipfile` | `python -m zipfile -e <fixture> <workdir>/out` | 0 | `readme` | （无 stdout/stderr） |
| `info-zip-unzip` | `unzip -o <fixture> -d <workdir>/out` | 0 | `readme`<br>`readme.` | Archive:  <path><br> extracting: <workdir>\out/readme.<br> extracting: <workdir>\out/readme |
| `7zip` | `7z x -y -o<workdir>/out <fixture>` | 0 | `readme`<br>`readme_` | 7-Zip 25.01 (x64) : Copyright (c) 1999-2025 Igor Pavlov : 2025-08-03<br>Scanning the drive for archives:<br>1 file, 226 bytes (1 KiB)<br>Extracting archive: <path><br>--<br>Path = <path> |
| `libarchive` | `bsdtar -x -f <fixture> -C <workdir>/out` | 0 | `readme`<br>`readme.` | （无 stdout/stderr） |

`distinct_written_sets = 3` ／ `tools_agree = false`

### 4.4 `filedir.zip`（同时有 `a`（文件）与 `a/b`（路径））

**三平台都报的那条规则，在提取器层面也是最尖锐的一格**：`unzip` 与 `7zip` 都**退 2**并只留一个 `a`
（`unzip` 明说 `checkdir error:  <workdir>\out/a exists but is not directory / unable to process a/b.`）；
Python **拒绝**（它先创建文件 `a`，随后写 `a/b` 时抛 `FileNotFoundError`——注意它把临时目录**清洗成了
`<path>`**，这是节选纪律在异常消息上的落地）；只有 `libarchive` **完整**落出 `a/` 与 `a/b`。
**"文件挡住了目录"这件事，四个工具有四种处置。**

| 工具 | 实测命令 | 退出码 | 实际落盘名 | 输出节选（原文） |
|---|---|---|---|---|
| `python-zipfile` | `python -m zipfile -e <fixture> <workdir>/out` | 拒绝<br>（`refused`） | `a` | `FileNotFoundError: [Errno 2] No such file or directory: '<path>'` |
| `info-zip-unzip` | `unzip -o <fixture> -d <workdir>/out` | 2 | `a` | Archive:  <path><br> extracting: <workdir>\out/a<br>checkdir error:  <workdir>\out/a exists but is not directory<br>                 unable to process a/b. |
| `7zip` | `7z x -y -o<workdir>/out <fixture>` | 2 | `a` | 7-Zip 25.01 (x64) : Copyright (c) 1999-2025 Igor Pavlov : 2025-08-03<br>Scanning the drive for archives:<br>1 file, 208 bytes (1 KiB)<br>Extracting archive: <path><br>--<br>Path = <path> |
| `libarchive` | `bsdtar -x -f <fixture> -C <workdir>/out` | 0 | `a/`<br>`a/b` | （无 stdout/stderr） |

`distinct_written_sets = 2` ／ `tools_agree = false`

### 4.5 `reserved.zip`（`CON.txt` / `NUL.txt` / `aux.tar.gz`）

**唯一因为"名字本身是设备名"而改名的只有 7-Zip**：它给三条都加 `_` 前缀
（`_CON.txt` / `_NUL.txt` / `_aux.tar.gz`）；另外三家**照原样落盘**，退 `0`、无任何警告。
**于是"这个归档在 Windows 上打开会出问题"这件事，只有先把文件写进去之后由应用层暴露出来**——
`CON.txt` / `NUL.txt` 在目录里能被枚举，却打不开（三证据在 `data/README.md` §1.3.2）；
`aux.tar.gz` 是**可读对照组**（M1 实测推翻"含扩展名即保留名"）。7-Zip 的 `_` 前缀是
**平台改写**，不属于 §三 的解码层（作用域边界见 `data/README.md` §4.12 末段）。

| 工具 | 实测命令 | 退出码 | 实际落盘名 | 输出节选（原文） |
|---|---|---|---|---|
| `python-zipfile` | `python -m zipfile -e <fixture> <workdir>/out` | 0 | `CON.txt`<br>`NUL.txt`<br>`aux.tar.gz` | （无 stdout/stderr） |
| `info-zip-unzip` | `unzip -o <fixture> -d <workdir>/out` | 0 | `CON.txt`<br>`NUL.txt`<br>`aux.tar.gz` | Archive:  <path><br> extracting: <workdir>\out/CON.txt<br> extracting: <workdir>\out/NUL.txt<br> extracting: <workdir>\out/aux.tar.gz |
| `7zip` | `7z x -y -o<workdir>/out <fixture>` | 0 | `_CON.txt`<br>`_NUL.txt`<br>`_aux.tar.gz` | 7-Zip 25.01 (x64) : Copyright (c) 1999-2025 Igor Pavlov : 2025-08-03<br>Scanning the drive for archives:<br>1 file, 334 bytes (1 KiB)<br>Extracting archive: <path><br>--<br>Path = <path> |
| `libarchive` | `bsdtar -x -f <fixture> -C <workdir>/out` | 0 | `CON.txt`<br>`NUL.txt`<br>`aux.tar.gz` | （无 stdout/stderr） |

`distinct_written_sets = 2` ／ `tools_agree = false`

### 4.6 `trailing.zip`（`trailing. ` / `trailingdot.` / `colon:name.txt`）

**三种结果、同一条规律**：`unzip` 与 `libarchive` **原样保留**尾随空格与尾随点
（目录里真的列出 `trailing. ` 与 `trailingdot.`，NTFS 层再静默裁剪）；`7zip` 把它们改成
`trailing__` / `trailingdot_`（尾随的 `.` 变 `_`，且原尾随空格也保留成 `_`，**两个下划线**）；
Python 落 `trailing` / `trailingdot`（裁剪后）。
**三条样本的 `colon:name.txt` 四家都落成 `colon_name.txt`** ——`:` 的 ADS 截断
在**落盘名**上表现一致，但 unzip 的输出里能看见它自己的替换（`colon_name.txt`）。
`aux.tar.gz` 式的"名字变了但没失败"正是 `WRITTEN_TRUNCATED` 这一档的实测来源。

| 工具 | 实测命令 | 退出码 | 实际落盘名 | 输出节选（原文） |
|---|---|---|---|---|
| `python-zipfile` | `python -m zipfile -e <fixture> <workdir>/out` | 0 | `colon_name.txt`<br>`trailing`<br>`trailingdot` | （无 stdout/stderr） |
| `info-zip-unzip` | `unzip -o <fixture> -d <workdir>/out` | 0 | `colon_name.txt`<br>`trailing. `<br>`trailingdot.` | Archive:  <path><br> extracting: <workdir>\out/trailing.<br> extracting: <workdir>\out/trailingdot.<br> extracting: <workdir>\out/colon_name.txt |
| `7zip` | `7z x -y -o<workdir>/out <fixture>` | 0 | `colon_name.txt`<br>`trailing__`<br>`trailingdot_` | 7-Zip 25.01 (x64) : Copyright (c) 1999-2025 Igor Pavlov : 2025-08-03<br>Scanning the drive for archives:<br>1 file, 355 bytes (1 KiB)<br>Extracting archive: <path><br>--<br>Path = <path> |
| `libarchive` | `bsdtar -x -f <fixture> -C <workdir>/out` | 0 | `colon_name.txt`<br>`trailing. `<br>`trailingdot.` | （无 stdout/stderr） |

`distinct_written_sets = 3` ／ `tools_agree = false`

### 4.7 为什么"用真实 `$UpCase` 表"不能被 casefold 替代（本机的 8 组字符对）

本节四家的差异讲的是**提取器**；这条讲的是**目标文件系统**。8 组字符对在本机 NTFS 上实测
（先写 A 再 `CREATE_NEW` 建 B，`ERROR_ALREADY_EXISTS(183)` / `ERROR_FILE_EXISTS(80)` 即折叠；
三种独立手段结论一致）：

| 字符对 | `str.upper()` 预测 | `str.casefold()` 预测 | **实测 NTFS** |
|---|---|---|---|
| `ı` / `I` | 冲突 | 不冲突 | **不冲突** |
| `ſ` / `S` | 冲突 | 不冲突 | **不冲突** |
| `ß` / `SS` | 冲突 | 不冲突 | **不冲突** |
| `ß` / `ss` | 冲突 | 冲突 | **不冲突** |
| `İ` / `i` | 不冲突 | 不冲突 | **不冲突** |
| `ǅ` / `Ǆ` | 冲突 | 冲突 | **不冲突** |
| `ω` / `Ω` | 冲突 | 冲突 | **冲突** |
| `é` / `É`（对照组） | 冲突 | 冲突 | **冲突** |

**判读**：`ǅ/Ǆ` 上 `casefold` 判冲突而 NTFS 不冲突 —— 近似法会产出**假阳性**
（把不冲突的判成冲突）。所以 MOD-3 的 Windows 侧走真实 `$UpCase` 表
（`data/platforms/ntfs-upcase.bin`，`source = host_probe`，带真实卷写入碰撞校验），
**不用也不近似** `str.lower()`/`casefold()`（`plan/00` 决策 ③；
逐字符完整表与这 8 组的机器可读结果在 `data/platforms/meta.json`）。
**这条不是本文的"四工具对照"，是"四工具之下那一层"的对照**——放在本节是为了让读者看清
"提取器分歧"与"文件系统折叠"是两层，中间的接口是**名字**。

---

## 五、非三处阵地的其余样本（容器 / 预算 / 零误报基线）

这 7 份样本不属于 `plan/01` §1.2 的三处阵地，但它们同样在 22×4 格里。它们的价值是**反向证据**：
**四工具在这 28 格上全部一致**（7 份样本全部 `tools_agree = true`——`long_comp.zip` 的"一致"
是"四家都失败"，同样是一致），所以"分歧"不是本工具凭空造出来的——基线是干净的。

### 5.1 四份 EPUB 容器样本（`not_first` / `compressed` / `extra` / `padding`）

**四家全部一致：落盘名与退出码都没有差别**。这四份的分歧发生在**容器约定层**
（`mimetype` 是不是首文件、有没有被压缩、带不带 extra field、内容有没有尾随空白），
**不在提取器层**——`plan/01` §2 模块⑤ 的"交叉验证纪律"就是这个意思：`epubcheck` / ODF validator
做的是包文档语义，提取器做的是字节搬运，**两者都不看"mimetype 是不是第一个"**。

#### `not_first.epub`

`distinct_written_sets = 1` ／ `tools_agree = true`

| 工具 | 实测命令 | 退出码 | 实际落盘名 | 输出节选（原文） |
|---|---|---|---|---|
| `python-zipfile` | `python -m zipfile -e <fixture> <workdir>/out` | 0 | `META-INF/`<br>`META-INF/container.xml`<br>`mimetype` | （无 stdout/stderr） |
| `info-zip-unzip` | `unzip -o <fixture> -d <workdir>/out` | 0 | `META-INF/`<br>`META-INF/container.xml`<br>`mimetype` | Archive:  <path><br> extracting: <workdir>\out/META-INF/container.xml<br> extracting: <workdir>\out/mimetype |
| `7zip` | `7z x -y -o<workdir>/out <fixture>` | 0 | `META-INF/`<br>`META-INF/container.xml`<br>`mimetype` | 7-Zip 25.01 (x64) : Copyright (c) 1999-2025 Igor Pavlov : 2025-08-03<br>Scanning the drive for archives:<br>1 file, 302 bytes (1 KiB)<br>Extracting archive: <path><br>--<br>Path = <path> |
| `libarchive` | `bsdtar -x -f <fixture> -C <workdir>/out` | 0 | `META-INF/`<br>`META-INF/container.xml`<br>`mimetype` | （无 stdout/stderr） |

#### `compressed.epub`

`distinct_written_sets = 1` ／ `tools_agree = true`

| 工具 | 实测命令 | 退出码 | 实际落盘名 | 输出节选（原文） |
|---|---|---|---|---|
| `python-zipfile` | `python -m zipfile -e <fixture> <workdir>/out` | 0 | `META-INF/`<br>`META-INF/container.xml`<br>`OEBPS/`<br>`OEBPS/content.xhtml`<br>`mimetype` | （无 stdout/stderr） |
| `info-zip-unzip` | `unzip -o <fixture> -d <workdir>/out` | 0 | `META-INF/`<br>`META-INF/container.xml`<br>`OEBPS/`<br>`OEBPS/content.xhtml`<br>`mimetype` | Archive:  <path><br>  inflating: <workdir>\out/mimetype<br> extracting: <workdir>\out/META-INF/container.xml<br> extracting: <workdir>\out/OEBPS/content.xhtml |
| `7zip` | `7z x -y -o<workdir>/out <fixture>` | 0 | `META-INF/`<br>`META-INF/container.xml`<br>`OEBPS/`<br>`OEBPS/content.xhtml`<br>`mimetype` | 7-Zip 25.01 (x64) : Copyright (c) 1999-2025 Igor Pavlov : 2025-08-03<br>Scanning the drive for archives:<br>1 file, 452 bytes (1 KiB)<br>Extracting archive: <path><br>--<br>Path = <path> |
| `libarchive` | `bsdtar -x -f <fixture> -C <workdir>/out` | 0 | `META-INF/`<br>`META-INF/container.xml`<br>`OEBPS/`<br>`OEBPS/content.xhtml`<br>`mimetype` | （无 stdout/stderr） |

> `unzip` 那一格的 ` inflating:`（而不是 ` extracting:`）就是"这个条目被压缩了"的**可见证据**——
> 同样五条名字、同样的退出码，**只有这一列能看出 `mimetype` 被 deflate 过**。

#### `extra.epub`

`distinct_written_sets = 1` ／ `tools_agree = true`

| 工具 | 实测命令 | 退出码 | 实际落盘名 | 输出节选（原文） |
|---|---|---|---|---|
| `python-zipfile` | `python -m zipfile -e <fixture> <workdir>/out` | 0 | `META-INF/`<br>`META-INF/container.xml`<br>`OEBPS/`<br>`OEBPS/content.xhtml`<br>`mimetype` | （无 stdout/stderr） |
| `info-zip-unzip` | `unzip -o <fixture> -d <workdir>/out` | 0 | `META-INF/`<br>`META-INF/container.xml`<br>`OEBPS/`<br>`OEBPS/content.xhtml`<br>`mimetype` | Archive:  <path><br> extracting: <workdir>\out/mimetype<br> extracting: <workdir>\out/META-INF/container.xml<br> extracting: <workdir>\out/OEBPS/content.xhtml |
| `7zip` | `7z x -y -o<workdir>/out <fixture>` | 0 | `META-INF/`<br>`META-INF/container.xml`<br>`OEBPS/`<br>`OEBPS/content.xhtml`<br>`mimetype` | 7-Zip 25.01 (x64) : Copyright (c) 1999-2025 Igor Pavlov : 2025-08-03<br>Scanning the drive for archives:<br>1 file, 466 bytes (1 KiB)<br>Extracting archive: <path><br>--<br>Path = <path> |
| `libarchive` | `bsdtar -x -f <fixture> -C <workdir>/out` | 0 | `META-INF/`<br>`META-INF/container.xml`<br>`OEBPS/`<br>`OEBPS/content.xhtml`<br>`mimetype` | （无 stdout/stderr） |

> `mimetype` 带 0xCAFE extra field 这件事，四家的输出里**一个字都没有**——extra field 对提取器
> 完全透明。所以"容器约定"这一整类判定，**提取器层不可能给出**，只能靠读字节
> （`data/README.md` §4.13、`plan/01` §2 模块⑤ 的"与它们是互补关系"）。

#### `padding.epub`

`distinct_written_sets = 1` ／ `tools_agree = true`

| 工具 | 实测命令 | 退出码 | 实际落盘名 | 输出节选（原文） |
|---|---|---|---|---|
| `python-zipfile` | `python -m zipfile -e <fixture> <workdir>/out` | 0 | `META-INF/`<br>`META-INF/container.xml`<br>`OEBPS/`<br>`OEBPS/content.xhtml`<br>`mimetype` | （无 stdout/stderr） |
| `info-zip-unzip` | `unzip -o <fixture> -d <workdir>/out` | 0 | `META-INF/`<br>`META-INF/container.xml`<br>`OEBPS/`<br>`OEBPS/content.xhtml`<br>`mimetype` | Archive:  <path><br> extracting: <workdir>\out/mimetype<br> extracting: <workdir>\out/META-INF/container.xml<br> extracting: <workdir>\out/OEBPS/content.xhtml |
| `7zip` | `7z x -y -o<workdir>/out <fixture>` | 0 | `META-INF/`<br>`META-INF/container.xml`<br>`OEBPS/`<br>`OEBPS/content.xhtml`<br>`mimetype` | 7-Zip 25.01 (x64) : Copyright (c) 1999-2025 Igor Pavlov : 2025-08-03<br>Scanning the drive for archives:<br>1 file, 451 bytes (1 KiB)<br>Extracting archive: <path><br>--<br>Path = <path> |
| `libarchive` | `bsdtar -x -f <fixture> -C <workdir>/out` | 0 | `META-INF/`<br>`META-INF/container.xml`<br>`OEBPS/`<br>`OEBPS/content.xhtml`<br>`mimetype` | （无 stdout/stderr） |

### 5.2 `long_path.zip`（7 段 × 44 字节 = **314** 字节整路径）

**四家全部落盘成功**（`rc = 0/0/0/0`，各 7 个目录条目）。这就是"超 260 **不是**截断"的实测依据：
本机 `LongPathsEnabled=1` 时 314 字节路径可直接创建，所以 `budget.PATH_OVER_260` 只能写成
**可移植性预算告警**（`evidence.kind = portability_budget`），不能断言"必然截断/创建失败"
（`plan/05` §五 U12；靶子 `tests/test_budget.py::test_path_over_260_is_a_budget_warning_not_a_local_truncation`）。
名字按 §1.2 第 3 条截断显示，完整值在 `data/tool-matrix/long_path.zip.json`。

| 工具 | 实测命令 | 退出码 | 实际落盘名 | 输出节选（原文） |
|---|---|---|---|---|
| `python-zipfile` | `python -m zipfile -e <fixture> <workdir>/out` | 0 | `dddddddddddddddddddddddddddddddddddddddddddd/`<br>`…/dddddddddddddddddddddddddddddddddddddddddddd/`（共 90 字符）<br>`…`（共 135 / 180 / 225 / 270 字符各一条）<br>`…`（共 314 字符） | （无 stdout/stderr） |
| `info-zip-unzip` | `unzip -o <fixture> -d <workdir>/out` | 0 | 同上 7 条 | Archive:  <path><br> extracting: <workdir>\out/dddddddddddddddddddddddddddddddddddddddddddd/dddddddddddddddddddddddddddddddddddddddddddd/dddddddddddddddddddddddddddddddddddddddddddd/dddddddddddddddddddddddddddddddddddddddddddd/dddddddddddddddddddddddddddddddddddddddddddd/dddddddddddddddddddddddddddddddddddddddddddd/dddddddddddddddddddddddddddddddddddddddddddd |
| `7zip` | `7z x -y -o<workdir>/out <fixture>` | 0 | 同上 7 条 | 7-Zip 25.01 (x64) : Copyright (c) 1999-2025 Igor Pavlov : 2025-08-03<br>Scanning the drive for archives:<br>1 file, 739 bytes (1 KiB)<br>Extracting archive: <path><br>--<br>Path = <path> |
| `libarchive` | `bsdtar -x -f <fixture> -C <workdir>/out` | 0 | 同上 7 条 | （无 stdout/stderr） |

`distinct_written_sets = 1` ／ `tools_agree = true`

### 5.3 `long_comp.zip`（单组件 **256** 码元）

**四家全部失败、四种退出码、没有任何名字落地**——这是"组件超限是平台**硬限**"的实测依据
（与 §5.2 的预算告警形成对照，`budget.COMPONENT_OVER_255` 的 `evidence.kind = platform_limit`）。
四家的报错形态各不相同：Python 抛 `OSError: [Errno 22] Invalid argument`、`unzip` 退 `50` 并明说
`File name too long`、`bsdtar` 退 `1`（`Can't create '\\?\<path>': Invalid argument`——它**试过**
加长路径前缀也不行）、`7z` 退 `2`（stdout 里只有横幅，节选里看不到原因）。
**"两家说得出为什么、两家说不出"本身也是观测结果**，所以这里照记不补。

| 工具 | 实测命令 | 退出码 | 实际落盘名 | 输出节选（原文） |
|---|---|---|---|---|
| `python-zipfile` | `python -m zipfile -e <fixture> <workdir>/out` | 拒绝<br>（`refused`） | **（无）** | `OSError: [Errno 22] Invalid argument: '<path>'` |
| `info-zip-unzip` | `unzip -o <fixture> -d <workdir>/out` | 50 | **（无）** | Archive:  <path><br>error:  cannot create <workdir>\out/xxxxxxxx…（256 个 x）<br>        File name too long |
| `7zip` | `7z x -y -o<workdir>/out <fixture>` | 2 | **（无）** | 7-Zip 25.01 (x64) : Copyright (c) 1999-2025 Igor Pavlov : 2025-08-03<br>Scanning the drive for archives:<br>1 file, 623 bytes (1 KiB)<br>Extracting archive: <path><br>--<br>Path = <path> |
| `libarchive` | `bsdtar -x -f <fixture> -C <workdir>/out` | 1 | **（无）** | xxxxxxxx…（256 个 x）: Can't create '\\?\<path>': Invalid argument<br>tar.exe: Error exit delayed from previous errors. |

`distinct_written_sets = 1` ／ `tools_agree = true`（**"一致"的是"都失败"**）

### 5.4 `clean.zip`（零误报基线）

**四家完全一致、全部退 `0`**：两个条目、两个名字、无警告。这份样本的双重作用：
① 证明"分歧"是可归因的——干净输入上四家没有分歧；② 它是**判定面**的零误报基线
（五模块齐备的 `check data/fixtures/clean.zip --target windows` 必须退 `0` 且三数组皆空，
`data/README.md` §4.1）。

| 工具 | 实测命令 | 退出码 | 实际落盘名 | 输出节选（原文） |
|---|---|---|---|---|
| `python-zipfile` | `python -m zipfile -e <fixture> <workdir>/out` | 0 | `alpha.txt`<br>`beta.txt` | （无 stdout/stderr） |
| `info-zip-unzip` | `unzip -o <fixture> -d <workdir>/out` | 0 | `alpha.txt`<br>`beta.txt` | Archive:  <path><br> extracting: <workdir>\out/alpha.txt<br> extracting: <workdir>\out/beta.txt |
| `7zip` | `7z x -y -o<workdir>/out <fixture>` | 0 | `alpha.txt`<br>`beta.txt` | 7-Zip 25.01 (x64) : Copyright (c) 1999-2025 Igor Pavlov : 2025-08-03<br>Scanning the drive for archives:<br>1 file, 228 bytes (1 KiB)<br>Extracting archive: <path><br>--<br>Path = <path> |
| `libarchive` | `bsdtar -x -f <fixture> -C <workdir>/out` | 0 | `alpha.txt`<br>`beta.txt` | （无 stdout/stderr） |

`distinct_written_sets = 1` ／ `tools_agree = true`

---

## 六、22 × 4 格索引矩阵（逐格对照的完备性清单）

**读法**：每行的"节"列指出该 fixture 的 88 格中那 4 格**在本文哪一节展开**（含实测命令与输出节选，
即 §二–§五 的逐格表）。本表的 `rc` / `落盘名` 是紧凑复述，**以该节的原文表与
`data/tool-matrix/<fixture>.json` 为准**；两者不一致就是缺陷。

`rc` 列的写法：`0` / 数字 = 该工具返回的退出码；`R` = 该格 `status = refused`（Python 库调用拒绝，
无退出码）；`—` = 无。

| fixture | 节 | `python-zipfile` | `info-zip-unzip` | `7zip` | `libarchive` | 落盘名集合数 |
|---|---|---|---|---|---|---|
| `mismatch_name.zip` | §2.1 | R | 1 | 2 | 0 | 3 |
| `alias_lfh.zip` | §2.2 | 0 | 1 | 0 | 0 | 1 |
| `overlap.zip` | §2.3 | R | 0 | 0 | 0 | 2 |
| `wrong_count.zip` | §2.4 | 0 | 3 | 2 | 0 | 1 |
| `crc_diverge.zip` | §2.5 | R | 0 | 2 | 1 | 1 |
| `size_diverge.zip` | §2.6 | 0 | 0 | 2 | 1 | 1 |
| `zh_gbk.zip` | §3.1 | 0 | 0 | 0 | 0 | 3 |
| `upath.zip` | §3.2 | 0 | 0 | 0 | 0 | 1 |
| `upath_badcrc.zip` | §3.3 | 0 | 0 | 0 | 0 | 3 |
| `case.zip` | §4.1 | 0 | 0 | 0 | 0 | 2 |
| `norm.zip` | §4.2 | 0 | 0 | 0 | 0 | 3 |
| `trim.zip` | §4.3 | 0 | 0 | 0 | 0 | 3 |
| `filedir.zip` | §4.4 | R | 2 | 2 | 0 | 2 |
| `reserved.zip` | §4.5 | 0 | 0 | 0 | 0 | 2 |
| `trailing.zip` | §4.6 | 0 | 0 | 0 | 0 | 3 |
| `not_first.epub` | §5.1 | 0 | 0 | 0 | 0 | 1 |
| `compressed.epub` | §5.1 | 0 | 0 | 0 | 0 | 1 |
| `extra.epub` | §5.1 | 0 | 0 | 0 | 0 | 1 |
| `padding.epub` | §5.1 | 0 | 0 | 0 | 0 | 1 |
| `long_path.zip` | §5.2 | 0 | 0 | 0 | 0 | 1 |
| `long_comp.zip` | §5.3 | R | 50 | 2 | 1 | 1 |
| `clean.zip` | §5.4 | 0 | 0 | 0 | 0 | 1 |

**这轮扫到**：22 份 fixture / 88 格 / 10 份 `tools_agree = false`
（`case`、`filedir`、`mismatch_name`、`norm`、`overlap`、`reserved`、`trailing`、`trim`、`upath_badcrc`、`zh_gbk`）。

---

## 七、与判定面的对应（每格 → 谁负责）

本文只记行为；把行为变成结论的是判定面。逐样本的对应关系如下
（`ruleId` 与口径：`data/README.md` §4；依据与出处的逐条核对：`docs/rules.md`）：

| fixture | 判定面的期望产出 | 在哪一层 | 依据形态 |
|---|---|---|---|
| `mismatch_name.zip` | `structure.NAME_DIVERGES` | 结构（读头选择） | **实现选择**（`docs/rules.md` #9/#10），不引规范 |
| `alias_lfh.zip` | `structure.FLAG_DIVERGES` | 结构（标志位） | 结构自证（#8） |
| `overlap.zip` | `structure.LFH_OVERLAP` | 结构（物理区间） | 结构自证（#8） |
| `wrong_count.zip` | `structure.CD_COUNT_MISMATCH` | 结构（EOCD vs 实际） | 结构自证（#8） |
| `crc_diverge.zip` | `structure.CRC_DIVERGES` | 结构（字段自证） | 结构自证（#8） |
| `size_diverge.zip` | `structure.SIZE_DIVERGES` | 结构（字段自证） | 结构自证（#8） |
| `zh_gbk.zip` | `encoding.candidates[]` + `predictedNames`（三套名） | 编码（解码层） | 本机实测 + APPNOTE D.1（#6/#16） |
| `upath.zip` | `upath` 覆盖生效，无 finding | 编码（0x7075） | APPNOTE §4.6.9（#7） |
| `upath_badcrc.zip` | `encoding.UPATH_CRC_MISMATCH` + 降级 `low` | 编码（0x7075） | APPNOTE §4.6.9（#7） |
| `case.zip` | `collision.CASEFOLD`（`survivor` = 后写者） | 折叠（Windows 表） | 真实 `$UpCase` 表（§4.7） |
| `norm.zip` | Windows 不报 / macOS 报 `collision.NFC` | 折叠（归一化） | UAX #15 + TN1150 + 逆向观察（#2/#3/#4，`medium`） |
| `trim.zip` | `collision.TRIM` + `WRITTEN_TRUNCATED` | 折叠 + 可访问性 | MS Learn 尾随点空格（#1） |
| `filedir.zip` | `collision.FILEDIR`（三平台都报） | 折叠（路径等价形） | 结构自证 + 本机实测（#8） |
| `reserved.zip` | `WRITTEN_UNREADABLE` ×2（`aux.tar.gz` → `OK`） | 可访问性 | MS Learn 保留名（#1）+ 三证据实测 |
| `trailing.zip` | `WRITTEN_TRUNCATED` ×3（含 `:` 的 ADS 截断） | 可访问性 | MS Learn（#1）+ 本机实测（U11） |
| `not_first.epub` | `container.MIMETYPE_NOT_FIRST` | 容器 | EPUB 3.3 §4.3.3 / ODF §3.3（#11/#13） |
| `compressed.epub` | `container.MIMETYPE_COMPRESSED` | 容器 | 同上 |
| `extra.epub` | `container.MIMETYPE_EXTRA` | 容器 | 同上 |
| `padding.epub` | `container.MIMETYPE_PADDING` | 容器 | EPUB 原文（#11）；ODF 侧标 `inferred`（#14） |
| `long_path.zip` | `budget.PATH_OVER_260`（**预算告警**） | 预算 | MS Learn 260 + `{PATH_MAX}`（#1/#15），`portability_budget` |
| `long_comp.zip` | `budget.COMPONENT_OVER_255` + `BLOCKED` | 预算 + 可访问性 | 同上，`platform_limit`（U12 的另一侧） |
| `clean.zip` | **零 finding / 零 collision / 零可访问性异常**（退 0） | 全部 | 零误报基线 |

**作用域边界（诚实标注）**：`encoding.predictedNames` **只预言解码层**，"这条原始名字节会被解成
哪个字符串"。本文 §4.3 / §4.5 / §4.6 里那些 `7zip` 的 `_` 前缀与 `readme_`、四家的 ADS 截断、
尾随裁剪，**都不属于解码层**——它们分别归 `accessibility` / `collision`。逐格对账时因此要按样本
分类挑（`data/README.md` §4.12 末段列了分类）。

---

## 八、本文不承诺什么

- **不裁决"该用哪个工具"**。本文只并排陈述四家的实测行为；`plan/01` §6 的边界里写了
  "不做'该用哪个工具'的建议"——预言机只预言，不裁决。
- **不代表 macOS / Linux 的落盘行为**。本文全部实测都在**本机 Windows** 上完成；
  macOS / Linux 的落盘判定只能用平台表模拟，输出标 `table_simulated` / `medium`，**不得写成实测**
  （`plan/05` §五 U2/U3；`data/README.md` §5）。
- **不锁定工具版本之外的未来行为**。表里的版本串是身份；工具升级后行为漂移时，
  `tools/probe_tools.py --check` 会先红——**这是设计如此**（`plan/05` §七 R4：断言只锁"分歧方向"，
  不锁 stderr 文案；本文里的输出节选是**快照**，不是断言面）。
- **`python-zipfile` 那一格是库调用，不是 CLI**。要复现 CLI 形态请跑
  `python -m zipfile -e`；本文按"库有没有拒绝"记（§1.2 第 2 条）。
- **`data/README.md` §1.3.1 与 §5 的分工**：那里是**判定口径**的依据面（含 `CON.txt` 的三证据
  与 8 组字符对的判定用法），本文是**四工具实测**的对照面。两处对同一事实的表述若冲突，
  以**各自的作用域**为准，并同提交改齐（`plan/00` 决策 ⑧）。

---

## 九、复跑记录（M6 定稿时点）

| 命令 | 结果 |
|---|---|
| `py -3.12 tools/probe_tools.py --check` | 退出码 `0`：`对照组：22 份 fixture × 4 工具`；四工具自报版本与 §1.1 一致；`tools_agree = false` 的样本 10 份；`OK  全部格实测完成，记录与盘上一致` |
| `py -3.12 tools/gen_fixtures.py --check` | 退出码 `0`（22/22 逐字节一致；样本未改，本文只是读它） |

> 复跑纪律：本文的每一格都可由上面两条命令重新产出。**改 `data/fixtures/` 或换宿主工具版本后，
> 先复跑再改本文**——不允许"改了样本但本文照旧"（那也是 `data/README.md` §3.1
> "样本与真值同提交"在文档面上的同一条纪律）。
