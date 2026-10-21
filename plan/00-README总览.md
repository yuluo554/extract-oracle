# 00 · README 总览 — 10-21-extract-oracle（归档提取预言机）

> 方法论：`ai-tool-project-sprint`（装订 2026-10-21）｜布局门：`py -3.12 tools/check_sprint_layout.py`｜脱敏门：`py -3.12 tools/check_desensitized.py`｜续接对话第一件事 = 跑它们

- 性质：不参赛项目题 · 发布 GitHub **公开仓库** · 署名 yuluo554
- 交付形态（唯一）：**单文件可执行 + 纯本地 CLI**（只读归档、零网络、零解压到磁盘、零运行时依赖）
- 定位宣言："现有工具只做**单条规则检查**或**字段转储**，没有一个输出**谁会写出什么名字、谁覆盖谁、哪个工具会拒绝**。本工具是**提取结果预言机**：输入一个 ZIP/TAR，逐条目预言它在 {Windows 资源管理器, Info-ZIP unzip, 7-Zip, libarchive, Python zipfile, macOS Finder, Linux} 上会变成什么名字、是否被覆盖、是否应用层不可见、是否被拒绝。**提取预言机不是体检器。**"
- 基准日：**2026-10-21**；代理实际检索窗口 **2026-10-19T18:35Z–19:10Z**（`data/README.md` §1 已原样记录）
- 当前状态：**M5 容器与编码完成**（`rules/encoding.py` 推断 + `0x7075` 全量、`rules/container.py` 五条、`rules/budget.py` 两条；**五模块全部翻 True**，不带 `--module` 的 `check` 现在出完整报告；`docs/rules.md` 加 §八）；下一棒 = **M6 发布**（见 `plan/HANDOFF-M6.md`）
- **可上传状态**：发布就绪门（`py -3.12 tools/check_publish_ready.py`）8 条判据全绿，含 `git bundle verify` 推送包自证 → **仓库本身现在就能推**；**远端尚未创建**（建仓是显式对外动作，命令见 `plan/05` §四 第 0 步）
- CI 状态：**未接远端，CI 待首推验证**（`plan/05` §五 U1）

---

## 一、文档索引表

| 文档 | 内容 | 状态 |
|---|---|---|
| `plan/00-README总览.md` | 本文档：索引 / 决策记录 / 弃选项 / 承诺-证据台账 / 招牌动词表 / 提交材料实物表 / 里程碑 | ✅ v1 |
| `plan/01-题目文档.md` | 十段式题目定稿（介绍 / 五模块 / 提交材料 / 评分 / 锚点 / 边界） | ✅ v1 |
| `data/README.md` | 依据查证三态 + 检索窗口 + 数据源可获取性 + 合成数据纪律 + **数值口径单一真相源（§4，含 §4.9 `collisions` 形状 / §4.10 报告的 `platforms` 块）** + **证据强度自评（§5）** | ✅ v1 |
| `plan/02-架构与技术选型.md` | 分层、模块边界、构建链路、平台表数据契约、错误降级、确定性设计 | ✅ M0；M3 补 `platforms.py` 的分层位置与三条契约的落地形态 |
| `plan/03-模块详设.md` | 五模块的输入/输出/算法/误报控制/验收（模块数须与 `plan/01` 一致） | ✅ M0；M3 加 §MOD-3 的落地记（四处修正/收窄） |
| `plan/04-数据计划.md` | fixture 清单、真值结构、真值纪律、数据落库节奏 | ✅ M0 |
| `plan/05-里程碑与发布.md` | 逐里程碑 DoD、发布流程、状态表、已知未验证项、风险登记 | ✅ M0 |
| `plan/06-交付对标与决策.md` | 评分对标、招牌动词兑现、缺口表 | ✅ M0 |
| `AGENTS.md` | 仓库锚点：方法论 / 布局门命令 / 强制布局 / 硬纪律 / 环境事实 | ✅ M0 |
| `src/extract_oracle/` | 解析（`zip_reader` 三层）/ 判定（`rules/structure.py`、`rules/fold.py`、`rules/access.py`、`rules/encoding.py`、`rules/container.py`、`rules/budget.py`）/ 平台表访问（`platforms.py`）/ 报告 / CLI | ✅ M5：**五模块全部落地**（`structure`/`encoding`/`fold`/`accessibility`/`container`） |
| `tools/gen_fixtures.py` | `struct.pack` fixture 生成器（零网络、可重复、逐字节一致） | ✅ 22/22 份 |
| `tools/fetch_upcase.py` | 取 NTFS `$UpCase` 折叠表（`volume-read` / `host-probe` 双通道 + 真实卷校验） | ✅ M1 |
| `tools/probe_tools.py` | 四工具行为对照（可重跑，落 `data/tool-matrix/`） | ✅ M1 |
| `tools/check_sprint_layout.py` | 布局门（方法论装订第②件） | ✅ M0 |
| `tools/check_desensitized.py` | 脱敏门（发布前必跑，CI 同 job） | ✅ M0 |
| `tools/check_publish_ready.py` | 发布就绪门（可上传性 P1–P8；**不判是否已发布**） | ✅ M0 |
| `tools/bootstrap_remote.py` | 建仓 + 首推 + sha 对账 + CI run 回读（默认 dry-run） | ✅ M0 |
| `tests/` | 契约 / 确定性 / fixture 对账 / 门自身变异验证 / M1 数据产物 / 判定验收 | ✅ M0 起；M1 加 `test_m1_data.py`；M2 加六份判定与矩阵断言；M3 加 `test_fold.py` |
| `docs/rules.md` | 规则原句台账（15 行 × URL × 原句 + 逐规则反查表） | ✅ M4 定稿（5 行原句回填 + 两处出处更正 + 新增 POSIX 行） |
| `docs/divergence.md` | 四工具分歧对照定稿（中间产物在 `data/tool-matrix/`） | ⬜ M6 |
| `data/platforms/` | NTFS `$UpCase` 表 + 平台元数据 | ✅ M1 |
| `README.md` / `LICENSE` / `.gitignore` | 产品页 / MIT / Python 标准模板 | ✅ M0 |
| `scripts/build.py` | PyInstaller onefile 构建（版本自报断言） | 🟡 M0 脚本位；产物 M6 |
| `scripts/entry.py` | 冻结态入口（**绝对导入**薄壳；PyInstaller 把入口当顶层脚本，相对导入必崩） | ✅ M0 |
| `plan/RELEASE-M6.md` | 发布留档（tag 时点 / tag 后追加 两栏） | ⬜ M6 |

> 索引状态只在本表维护；`plan/01` 与 `data/README.md` 不重复登记状态。

---

## 二、决策记录表

| 日期 | 决策 | 结论与理由 |
|---|---|---|
| 2026-10-21 | **① 这不是空白市场（先写风险，再写方案）** | 本方向 **2026-10-05 至 10-19 两周内冒出 4 个同题仓库**：`cloudwallker/archive-preflight`（1★）、`Hhhxsss/zip-preflight`（0★）、`mehul82099/zip-preflight`（0★）、`mytestapp20261001-collab/zip-member-preflight`（0★），**其中 2 个功能相当完整**（CI、pre-commit hook、Windows 右键菜单、HTML 报告）。因此：**题面、README、Release 说明一律不得出现"空白/首创/首个"**；差异化只押它们文档里明写"不做"的三件事。 |
| 2026-10-21 | **② MOD-1（双头差分）与 MOD-3（跨平台折叠）是不可让渡的两个模块** | 去掉任一个，本题就退化成**第 5 个 zip-preflight**：只有 MOD-1 才是"读哪个头"的分歧证据，只有 MOD-3 才给出"谁覆盖谁、最后剩谁"。其余三个模块（编码推断、可访问性分级、容器约定）是可增强项，M1/M3 是生存项。**若时间不够，砍模块不砍这两个。** |
| 2026-10-21 | **③ NTFS 折叠表必须用真实 `$UpCase` 或真机探测，禁止 casefold 近似** | 本机 8 组字符对实测（`ı/I`、`ſ/S`、`ß/SS`、`ß/ss`、`İ/i`、`ǅ/Ǆ`、`ω/Ω` + 一组对照）证明 `str.lower()`/`casefold()` 与 NTFS 实际折叠**不等价**，近似会产生**假阳性**（把不冲突的判成冲突）。竞品 `cloudwallker/archive-preflight` 自认"casefold is an approximation"、"Native NTFS/APFS comparison tables… require host testing"——**这恰好是本题可守的位置，也是必须做实的位置**。表来源必须可追溯：卷读取，或真机探测并记录环境与卷标识。 |
| 2026-10-21 | **④ APFS 依据是逆向文档非 Apple 官方规范，文档须标注** | libfsapfs 文档给出卷不兼容标志 `0x08 APFS_INCOMPAT_NORMALIZATION_INSENSITIVE`、name hash 用 NFD、大小写不敏感卷先 lower-case；配合 HN 35336510 的实操描述。但 `developer.apple.com` 与 APFS Reference PDF 均 ECONNRESET，**未取到 Apple 官方原文**。因此 macOS 折叠判定在输出里标 `evidence_strength: medium`，`docs/rules.md` 必须逐字写明"实现观察，非 Apple 官方规范"。 |
| 2026-10-21 | **⑤ LFH 与 CD 不一致的判定只引实现选择，不引规范条文** | 逐字检索 APPNOTE 6.3.10，"must be identical" 与 "SHOULD match" 均无命中——**规范没有要求两者一致**。因此 MOD-1 的每条 finding 附 `precedent` 字段，写清"unzip / libzip / Python 取 CD、libarchive 取 LFH"（libarchive#2695 作者本人确认），不得编造条文。 |
| 2026-10-21 | **⑥ 交付形态收敛为单文件可执行 + 纯本地 CLI（唯一）** | 价值主张是"在 CI 里跑、在发布前跑"。GUI 会拉进打包与信任成本，Web 界面会引入浏览器对文件名的额外干涉变量。**右键菜单属扩展项，且只是同一 CLI 入口的薄壳**，不计为第二形态。 |
| 2026-10-21 | **⑦ 不解压到磁盘（只读）作为形态红线** | 一旦解压，本题就掉进"归档安全审计"领域（zip slip / zip bomb / 恶意检测），而那里已有 `snyk/zip-slip-vulnerability`（856★）、`ZOD`（918★）、`ronomon/zip`（258★）与 Python 标准库内置防护。**只读让安全面收缩到"读字节 + 模拟语义"**，也让"预言机"与"解压器"的定位边界清晰。 |
| 2026-10-21 | **⑧ 数值口径单点定义在 `data/README.md` §4** | 退出码、三级可访问性定义、折叠规则来源与判据、容器约定检查项、长度预算口径**只写一次**；`plan/01` 中的数字是摘要，代码只引用口径键。**修改必须先改 §4 并同提交同步。** |
| 2026-10-21 | **⑨ 检索数据定性为软论据（⬜）** | 13 条检索式与星数是带窗口的快照，不构成"业界首创"的证明；题面统一写"红海中的三处明写不做的缺口"，不写"空白/首创"。 |

### 弃选项（弃选理由写死，后续里程碑不再重复论证）

| 弃选项 | 理由 |
|---|---|
| **弃「归档安全审计」整体方向** | 已被填满：`ronomon/zip`（258★，结构层极严）× `snyk/zip-slip-vulnerability`（856★）× `ZOD`（918★），且 Python 3.12+ `zipfile`/`tarfile` 已内置路径剥离与 `filter='data'`。再做只会是更弱的第四份。**本题只借它的结构知识，不做它的功能。** |
| **弃「文件清单一致性 / archive diff」** | `diff -r` 与 BagIt（272★）已覆盖；且单文件比对即可完成，**无内核**，撑不起五模块。检索 `archive diff` 一类几乎全噪声。 |
| **弃「纯路径冲突检查」单独立项** | 直接撞 4 个同题仓库（其中一个含 Windows 右键菜单）。要立住**必须靠 MOD-1 与 MOD-2 拉开**——只做冲突列表就是第 5 份 zip-preflight。 |
| **弃「纯结构完整性校验」单独立项** | `ronomon/zip` 的校验更严（拒 LFH/CD 不一致、重叠 LFH、越界、非法 DOS 日期、压缩比 >100:1、伪装格式），且被 `epubcheck`（1978★）/ ODF validator 从容器侧夹击。**只能作 MOD-1 / MOD-5 的组成部分，不能作题目主体。** |
| **弃「嵌套归档 / 递归解包预言」进首期** | 需要内层流式解析与递归预算控制，工作量与首期五模块冲突；且容易滑向"解压器"定位。列扩展项。 |
| **弃「安全打分 / 风险总分」** | 单一分数掩盖分歧（§6 边界）；且分数阈值无规范来源，只能编——违反"无出处不用确定语气"。 |
| **弃「真实样本下载」** | 零网络是硬约束；全部 fixture 由 `struct.pack` 合成即可覆盖判定项。 |
| **弃「GUI / 桌面窗口 / Web 界面」** | 会引入第二形态验收负担与打包信任成本，且与本工具的 CI 使用场景不匹配。 |

---

## 三、承诺-证据台账（全项目唯一一份）

> 其他文档只可引用，不得复制本表。状态列随里程碑同提交翻转。

| 承诺项 | 素材来源 | 交付物内可达性 | 核验方式 | 状态 |
|---|---|---|---|---|
| 双头差分（LFH vs CD） | 自建 `mismatch_name.zip` 等；依据 libarchive#2695 实现选择 | `structure.*` 六条规则 | 六 fixture 各命中对应 code + 三工具行为断言进 CI | ✅ M2 落地（`tests/test_structure_diff.py`、`tests/test_tool_behaviour.py`） |
| 重叠与计数检测 | 自建 `overlap.zip` / `wrong_count.zip` | `structure.LFH_OVERLAP` / `CD_COUNT_MISMATCH` | 物理区间相交判定 + EOCD/实际计数比对 | ✅ M2 落地（含 ZIP64 路径退 3 的断言） |
| 编码推断与 0x7075 解析 | 自建 `zh_gbk.zip` / `upath.zip`；APPNOTE 镜像 D.2/D.6 + 本机四工具实测 | `encoding.candidates[]` + `upath` + `predictedNames` + `encoding` 报告块 | 三提取器预测互不相同，且与实测一致 | ✅ M5 落地（`tests/test_encoding.py` 37 条：候选顺序 K02 + 三档置信度 + `0x7075` 两种 CRC 结局 + 与 `data/tool-matrix/` 逐格对账；口径在 `data/README.md` §4.4 / 形状在 §4.12） |
| 真实 NTFS 折叠表 | 真实 `$UpCase`（本机 OS 上折叠表 65536 项 + 真实卷写入碰撞校验）；8 组字符对复核 | 平台表数据文件 + `collision.CASEFOLD` | 表 sha256 与本体一致；8 组字符对「表预测 = 卷实测」；`casefold` 在同样字符对上判错 | ✅ M3 落地（`tests/test_fold.py`：`sha256` 对账 + 篡改即拒 + 8 组双向回归；`platforms --verify` 打表指纹） |
| NFC/NFD 跨平台差异 | UAX #15 + TN1150 + libfsapfs（中硬） | `collision.NFC` + 平台表 | `norm.zip` 在 Windows 不报、macOS 必报 | ✅ M3 落地（`evidence_strength: medium`；macOS 侧不猜 `CASEFOLD`，见 `plan/05` U15） |
| 写序→存活者预测 | 四工具实测（后写覆盖） | `collisions[].writeOrder` / `survivor` | `case.zip` 预测 `README.TXT` 存活且内容为 `LOWER` | ✅ M3 落地（`filedir.zip` 的先写者存活是同一列的另一形态） |
| 三级可访问性分级 | `CON.txt` 实测三证据；Windows 命名规范原文（MS Learn）；Linux 侧 POSIX §3.170 | `entries[].accessibility` + `reasons[]` + `evidence[]` | `CON.txt`→`WRITTEN_UNREADABLE` 且三证据齐；`trailing.`→`WRITTEN_TRUNCATED`；保留名边界全绿 | ✅ M4 落地（`tests/test_accessibility.py` 60 条；口径唯一表述在 `data/README.md` §4.2 / 形状在 §4.11） |
| 容器约定检查 | EPUB 3.3 §4.3.2/4.3.3、ODF 1.2 part 3 §3.3 | `container.*` 五条 | 四 mimetype fixture 各命中一 code，普通 ZIP 零误报 | ✅ M5 落地（`tests/test_container.py` 20 条：四样本各命中一条且互不串报 + `clean.zip` 零误报 + ODF 上下文 `inferred` 现造样本验证；口径在 §4.5 / 形状在 §4.13） |
| 长度预算 | Windows 260/32767、Linux `PATH_MAX`/`NAME_MAX` | `budget.*` | 两 fixture 分别命中 | ✅ M5 落地（`tests/test_budget.py` 16 条：`PATH_OVER_260` 与 `COMPONENT_OVER_255` 各命中 + 260 是**预算告警**非截断（U12）+ 按组件切（U19）+ Linux 按字节 / Windows 按码元） |
| 只读零解压 | 形态本身 | 全部判定基于字节读取 | 测试断言：运行期间不产生解压目录（除测试临时目录） | ✅ M2 落地：判定层纯函数，`zip_reader` 只 `read_bytes`；工具行为测试的产物只在 `tmp_path` |
| 零网络 | 形态本身 | 无 http 客户端依赖 | 静态扫描（无网络库导入）+ 断网 e2e | ✅ M2 落地：`tests/test_rule_boundaries.py::test_no_network_imports_in_any_module`（断网 e2e 仍待首推后补） |
| 确定性导出 | 报告模块 | JSON/文本双导出 | 同输入双跑 byte 级一致（无时间戳/随机 ID/绝对路径） | ✅ M5 落地：M5 三个新面（`encoding[]` / `container` 块 / `budget.*`）已纳入 `tests/test_report_determinism.py` 的双跑比对，另有五模块齐备时的整份报告双跑 |
| 单文件可执行 | `scripts/build.py`（PyInstaller onefile） | `dist/extract-oracle.exe` | 干净环境直跑 + 交付态 e2e | ⬜ 待 M6 实现 |
| 规则原句文档 | 规范原文逐条核对 | `docs/rules.md` | 每条规则带 URL 与原句，可逐条回到来源 | ✅ M4 定稿：15 行全部直引（原 14 行 + 新增 POSIX `Filename` 行）；反查表逐规则一个 `#` 行号；两处依据出处已更正（见该文件 §五） |
| 四工具分歧对照 | 本机实测命令与输出 | `data/tool-matrix/*.json`（中间产物）→ `docs/divergence.md` | 每格附实测命令与输出节选；可重跑脚本重跑一致 | 🟡 已落 22×4 格；M6 定稿 |
| fixture 生成器 | `struct.pack` 程序化构造 | `tools/gen_fixtures.py` | 重跑逐字节一致；不含真实用户文件 | ✅ 22/22 份（M1） |
| 方法论装订 | `AGENTS.md` + 布局门 + 脱敏门 + `plan/00` 顶部一行 | `tools/check_sprint_layout.py` / `tools/check_desensitized.py` | 布局门全绿 + 变异逐组变红（`tests/test_layout_gate.py`） | ✅ |
| **可上传 GitHub** | 仓库结构 + 门 + 建仓脚本 | `tools/check_publish_ready.py`（P1–P8）/ `tools/bootstrap_remote.py` | 发布就绪门全绿（含 `git bundle verify` 推送包自证）+ 11 组变异逐组变红 | ✅（**仓库本身可推**；远端尚未创建，见 `plan/05` U1） |

---

## 四、招牌动词表

> 标题与定位宣言里的每个能力名词，都必须填出"哪条交付态命令产出"与"哪条基准断言"。

| 能力名词 | 哪条交付态命令产出它 | 哪条基准/测试断言它 |
|---|---|---|
| 双头差分（LFH/CD） | `extract-oracle check <zip> --target windows` 的 `structure.*` | `tests/test_structure_diff.py`（六 fixture 命中 + 三工具行为断言进 CI） |
| 重叠检测 | 同上，`structure.LFH_OVERLAP` | `tests/test_structure_diff.py::test_overlap` |
| 计数校验 | 同上，`structure.CD_COUNT_MISMATCH` | `tests/test_structure_diff.py::test_wrong_count`（含 ZIP64 路径） |
| 编码推断 | `extract-oracle check <zip>` 的 `encoding.candidates[]` | `tests/test_encoding.py`（`zh_gbk.zip` 三提取器互不相同） |
| Unicode path extra field | `extract-oracle check <zip>` 的 `upath` 字段 | `tests/test_encoding.py::test_upath_7075`（含 CRC 不匹配降级） |
| 跨平台折叠 | `--target {windows,macos,linux}` 的 `collision.*` | `tests/test_fold.py`（`case.zip`/`norm.zip`/`trim.zip`/`filedir.zip` 分平台结论 + 真值逐条对账） |
| 写序→存活者 | `collisions[].survivor` + `verdict` | `tests/test_fold.py::test_case_zip_windows_reports_exactly_one_casefold`（`survivor=README.TXT`）与 `::test_filedir_is_reported_on_all_three_platforms`（先写者存活） |
| 三级可访问性 | `entries[].accessibility` + `reasons[]` + `evidence[]` | `tests/test_accessibility.py`（`CON.txt` / `trailing.` / 边界保留名 / 五 fixture 真值对账） |
| 容器约定 | `container.*` | `tests/test_container.py`（四 mimetype fixture + 零误报基线） |
| 长度预算 | `budget.*` | `tests/test_budget.py`（260 / 255 边界） |
| 平台表（`$UpCase`） | `extract-oracle platforms --verify` 输出的表指纹 | `tests/test_fold.py::test_eight_pairs_table_matches_real_volume_measurement`（8 组字符对双向回归） |
| 确定性导出 | `--format json` 双跑 | `tests/test_report_determinism.py`（byte 级一致） |
| 单文件可执行 | `dist/extract-oracle.exe check ...` | `tests/test_artifact_e2e.py`（对产物跑，不只对库函数跑） |

> 任一行填不出 → 该词从标题、定位宣言、README 首段、输出 schema 四处同时删除，或降级为 roadmap。

---

## 五、提交材料实物表（一物一证）

| 承诺项（`plan/01` §3） | 应存在的文件路径 | 由哪个里程碑产出 | 用哪条命令核对 |
|---|---|---|---|
| CLI 与源码 | `src/extract_oracle/`、`scripts/build.py` | M2 起 | `git ls-files src scripts` |
| 单文件可执行 | `dist/extract-oracle.exe` | M6（构建自 M2） | `ls dist/` + `tests/artifact_e2e_test.py` |
| fixture 生成器 | `tools/gen_fixtures.py` | M1 | `git ls-files tools/gen_fixtures.py` + `python tools/gen_fixtures.py --check` |
| 规则文档 | `docs/rules.md` | M4 | `git ls-files docs/rules.md` |
| 分歧对照 | `docs/divergence.md` | M6 | `git ls-files docs/divergence.md` |
| 口径文档 | `data/README.md` | M0（本文档同批） | `git ls-files data/README.md` |
| 测试与基准 | `tests/` | M1 起 | `pytest -q` |
| README | `README.md` | M6 | `git ls-files README.md` |
| 发布留档 | `plan/RELEASE-M6.md` | M6（**tag 之前**落盘） | `git cat-file -e <tag>:plan/RELEASE-M6.md` |

---

## 六、里程碑与 DoD

| 里程碑 | 内容 | DoD | 状态 |
|---|---|---|---|
| M0 出题与骨架 | `plan/00` + `plan/01` + `data/README.md` + `.gitignore` + 中文首提交；**方法论装订**（`AGENTS.md` + 布局门 + 脱敏门 + `plan/00` 顶部一行）；`plan/02–06`；可运行骨架（`src/`、`pyproject`、`scripts/build.py`）；生成器骨架；CI 预置 | 十段式齐；三态齐；台账单一真相源；首提交经 `git log` 验证；布局门全绿且变异可红；脱敏门 0 命中；`pytest` 全绿；`check` 未就绪时退出码 3 | ✅ |
| **M1 数据先行** | `tools/gen_fixtures.py`（`struct.pack`）+ 全部 fixture 与真值 + **四工具对照表实测脚本** + `$UpCase` 取表脚本 | fixture 重跑逐字节一致（22/22）；每个判定项至少一个 fixture 与一份真值；四工具对照表每格有实测命令与输出（22×4）；`$UpCase` 表可取且记录卷标识、探测环境、sha256 | ✅ |
| **M2 双头差分** | MOD-1 全部六条规则 + MOD-2 骨架（原始字节 + bit11 + extra 解析） | 六 fixture 各命中对应 code（M0 初版「四」按当时规则数，M1 补齐后加严）；三工具行为断言在 CI 三平台跑；退出码语义落地 | ✅ |
| **M3 折叠** | MOD-3：平台表接入 + `collision.*` 四条 + 写序→存活者 | `case.zip` 存活者正确；`norm.zip` 分平台结论正确；8 组字符对回归全通过 | ✅ |
| **M4 可访问性** | MOD-4 三级分级 + `docs/rules.md` | `CON.txt`→`WRITTEN_UNREADABLE` 附三证据；`trailing.`→`WRITTEN_TRUNCATED`；保留名边界全绿；每条规则可回原句 | ✅ |
| **M5 容器与编码** | MOD-5 容器/预算 + MOD-2 收尾（编码推断与 0x7075 全量）+ 确定性导出 | 四 mimetype fixture 各命中一 code；`zh_gbk.zip`/`upath.zip` 预测与实测一致；双跑 byte 级一致 | ✅ |
| **M6 发布** | GitHub 公开仓库发布 | **① `git tag v0.1.0`；② GitHub Release 附产物**（`dist/extract-oracle.exe` + 确定性源码包，本地留副本并记 sha256）；**③ 发布留档 `plan/RELEASE-M6.md` 在 tag 之前落盘**（分"tag 时点事实 / tag 后追加事实"两栏）；④ `docs/divergence.md` 定稿；⑤ 干净 clone + 干净环境直跑通过 | ⬜ |

> DoD 口径写死为 **A) Release 附产物**（≥1 个手工上传附件，本地留副本 + sha256）。里程碑表的 DoD 列**只能加不能减**；任何裁剪必须在 §二 决策记录留一行理由。

> 依赖顺序：M1 必须先于 M2/M3（fixture 与平台表是判定真值的前提）；M3 依赖 M1 的 `$UpCase` 表；M5 的编码部分依赖 M2 的原始字节层；M6 最后。

---

## 七、模块 ↔ 规则命名 ↔ 验收 fixture 对照

| 模块 | `ruleId` 前缀 | 核心 fixture | 主验收断言 |
|---|---|---|---|
| MOD-1 双头差分与重叠 | `structure.*` | `mismatch_name.zip`、`alias_lfh.zip`、`overlap.zip`、`wrong_count.zip`、`crc_diverge.zip`、`size_diverge.zip` | 六 fixture 各命中一 code + 三工具行为在 CI 上成立 |
| MOD-2 编码推断与 0x7075 | `encoding.*` / `upath` | `zh_gbk.zip`、`upath.zip` | 三提取器预测互不相同且与实测一致 |
| MOD-3 跨平台折叠 | `collision.*` | `case.zip`、`norm.zip`、`trim.zip`、`filedir.zip`、8 组字符对 | 存活者正确；分平台结论正确；近似法被判错 |
| MOD-4 可访问性分级 | `accessibility` | `reserved.zip`、`trailing.zip` | `WRITTEN_UNREADABLE` / `WRITTEN_TRUNCATED` 分级正确 |
| MOD-5 容器与预算 | `container.*` / `budget.*` | 四个 mimetype fixture、两个预算 fixture | 各命中一 code；普通 ZIP 零误报 |

> 模块编号与 `plan/01` §2 一致（模块 ①…⑤ = MOD-1…MOD-5）。`plan/03` 落地时必须保持同一编号与同一 `ruleId` 前缀，否则视为口径分叉。

---

## 八、交接语（下一棒 = sprint M6）

题目已定稿于 `plan/01-题目文档.md`，口径单点定义在 `data/README.md` §4，台账与里程碑见本文档 §三/§六。

**M4（已收口）**交付六样全部落地：

1. **MOD-4 三级分级**（`src/extract_oracle/rules/access.py`）：`judge_name` / `check` / `count_issues`，
   分级顺序固定（BLOCKED → WRITTEN_UNREADABLE → WRITTEN_TRUNCATED → OK），`reasons[]` 与 `evidence[]`
   同档内**全收不短路**（两个词表都封闭，`tests/test_accessibility.py::test_judge_never_emits_unknown_reasons`）。
2. **`entries[].accessibility` 进报告**：形状写进 `data/README.md` §4.11（`level` / `reasons` / `evidence`），
   只在 `--module` 范围含 `accessibility` 时出现；`inspect` 恒不带（结构事实不产判定）。
3. **`summary` 两个邻近字段**：`accessibility_count`（判定产出，退码 1 的第三条来源）与
   `accessibility_levels`（逐级计数；**不在范围内是 `null` 不是 0** —— "没查"与"全 OK"是两件事）。
4. **`docs/rules.md` 定稿**（M4 的 DoD 第二项）：M1 留下的 5 行原句全部回填（#2/#4/#5/#6/#7），
   反查表补齐到**逐规则一个 `#` 行号**，并**新增 #15** 承载 POSIX §3.170 的真原句。
5. **`capabilities.accessibility` 翻 True**（同提交补 `tests/test_accessibility.py`，60 条）；K10 AST 守门
   对 `rules/access.py` 是第二个实质靶子（它本可以用 `lower()` 做保留名匹配）。
6. **CI 加 `Accessibility smoke`**（12 steps）：四份样本各命中期望级别 + 三条反向
   （`clean.zip` 三平台退 0、`long_comp.zip` 不得判成截断、`CON.txt` 三证据齐），全部断言退出码，不用 `|| true`。

**M4 按实测收窄了四处**（`plan/05` §五 U17–U20、`plan/03` §MOD-4 的 M4 落地记、`data/README.md` §4.2）：

- **上标 ¹²³ 变体不是保留名**（U17）：`CreateFileW('COM¹.txt')` 创建成功且读得到；MS Learn 里
  `echo test > COM¹` 失败是 CMD 走设备命名空间，而提取器走文件 API。
- **`COM0`/`LPT0` 才是保留名，`COM10` 起不是**（U17）：MS Learn 的枚举从 1 起，机器从 0 起都拿不到。
- **`/` 是路径分隔符，不是 Linux 非法字符**（U19）：原表第 2 步会让每一份带子目录的归档假报 `BLOCKED`；
  改成按组件判，只有**空组件**才 `BLOCKED`。
- **保留名按裁剪后组件匹配**（U18）：`con.txt.` 落盘为 `con.txt` 且读不到 → 级别取更严重的那档。
- 另：`pathname(7)` 里**没有** `/`、`NAME_MAX`、`PATH_MAX` 的原句（U20）—— 依据改挂 POSIX §3.170，
  这是"依据挂错出处"而不是"补一句引文"。

M1 的三条硬约束继续适用于 M6：**① 不得用 casefold 近似任何折叠判定**；**② 不得引"规范要求
LFH/CD 一致"**（规范没有，只引实现选择）；**③ 不得下载任何真实归档**（零网络）。

**M5（已收口）交付三样全部落地**（靶子 = `plan/06` §二 点名的三份测试 + 四 mimetype fixture）：

1. **MOD-2 收尾**（`src/extract_oracle/rules/encoding.py`）：`candidates[]`（K02 六项顺序、只收完整解码
   的候选）+ `preferred`（双字节强结构优先）+ 三档 `confidence` + `predictedNames`（四提取器各自的
   落盘名模型）+ `encoding.UPATH_CRC_MISMATCH`。**逐格对账 `data/tool-matrix/` 实测**（该领域内 0 失配）。
2. **MOD-5**（`rules/container.py` + `rules/budget.py`）：五条 `container.*`（`MIMETYPE_PADDING` 在 ODF
   上下文带 `inferred: true`）+ 两条 `budget.*`（`PATH_OVER_260` 是**预算告警**，`COMPONENT_OVER_255`
   是平台硬限；按组件切、Linux 按字节）。
3. **`capabilities.encoding` / `container` 翻 True**（同提交补 `tests/test_encoding.py` /
   `test_container.py` / `test_budget.py`，共 73 条）；**五模块齐备后不带 `--module` 的 `check`
   对 `clean.zip` 退 0 且三数组皆空**——`test_check_refuses_while_modules_missing` 已从"skip 分支"
   改成**正向断言**（不留静默假绿）。

**M5 的一处实测收窄**（写进 `data/README.md` §4.12 与 `docs/rules.md` §八）：**四个提取器的落盘名模型
是按本机实测写的，不是按"应该和谁一致"推的**——`unzip` 走 CP850 + OEM→ANSI best-fit（33 码点实测表），
`7zip`/`libarchive` 走**宿主 ANSI 码页**（本机 GBK）且**不做字符集探测**（有效的 UTF-8 字节照样被解成
`cafe茅.txt`）。APPNOTE 只规定"历史 CP437"与"bit 11 置位则 MUST UTF-8"，**没有**规定实现该用哪个码页。

发布类里程碑（M6）DoD 三件套不裁剪：**tag + Release 附产物（本地留副本 + sha256）+ `plan/RELEASE-M6.md` 留档（tag 之前落盘，两栏）**。
