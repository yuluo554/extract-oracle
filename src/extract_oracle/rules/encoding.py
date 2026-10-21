"""MOD-2 编码与 Unicode path extra field（骨架 M2 落地；**推断在 M5 收齐**）。

两层职责，刻意分开：

1. **结构事实**（`describe` / `describe_all` / `parse_upath`，M2 起就在）：原始名字节逐字节可逆、
   bit 11 原样、extra 切成 `(id, size)`、`0x7075` 的 `version / name_crc32 / utf8_name` 与 CRC 校验。
   这一层给 `inspect`（结构事实**不是**判定）。
2. **推断**（`check`，M5）：`candidates[]` / `preferred` / `confidence` / `predictedNames`，
   外加 `encoding.UPATH_CRC_MISMATCH` finding。这一层给 `check`（判定）。

口径**只在 `data/README.md` §4.4 与 §4.12 写一次**，本模块不写第二份：

- 候选顺序固定 `UTF-8 / CP437 / GBK / CP932 / CP949 / CP1251`（K02）；
- `high` = bit 11 置位，或 `0x7075` 存在且 CRC 通过；`medium` = 候选完整解码且全部落在常用字区；
  `low` = 其余（含 CRC 失配）；
- `0x7075` CRC 失配 → 覆盖失效、降级 `low`、输出 `encoding.UPATH_CRC_MISMATCH`；
- 无法完整解码的候选**不出现在**候选列表里；不可解码时 `name` 给 `null` + `reason`，不编造替代名。

**四个提取器的落盘名模型**（每个都对着 `data/tool-matrix/` 的实测格，见 §4.12）：

| 提取器 | 名字来源 |
|---|---|
| `python-zipfile` | `0x7075`（CRC 通过）→ 否则 bit 11（UTF-8）→ 否则 **CP437** |
| `info-zip-unzip` | `0x7075`（CRC 通过）→ 否则 **CP850 解码 + OEM→ANSI best-fit 替换表** |
| `7zip` / `libarchive` | `0x7075`（CRC 通过）→ 否则 bit 11 → 否则**候选里胜出的那个**（字符集探测） |

`unzip` 那一行不是猜的：本机 UnZip 6.00（Cygwin）对**置位与未置位 bit 11** 的同一份 UTF-8 字节给出
**同一落盘形**（`tests/` 与 `data/README.md` §4.12 的实测记录），所以模型统一走 OEM 路径；
那张替换表逐条实测（33 个码点），不是"近似规则"——它只做字符替换，不做任何大小写变换（K10）。

本模块是纯函数：不写盘、不联网、不 import 其他判定模块、不 import `cli`（K10）。
"""

from __future__ import annotations

import unicodedata
import zlib
from dataclasses import dataclass

from ..findings import Finding, sort_findings
from ..zip_reader import Archive, EntryView, ExtraField

#: general purpose bit flag bit 11：名字为 UTF-8（APPNOTE 6.3.10 D.1）。
FLAG_UTF8 = 0x0800

#: Info-ZIP Unicode Path extra field（APPNOTE 6.3.10 D.6）。
UPATH_ID = 0x7075
#: Info-ZIP Unicode Comment extra field（只记录不解释）。
UCOMMENT_ID = 0x6375
#: Extended timestamp（只记录不解释）。
EXT_TIMESTAMP_ID = 0x0008

#: M5 的候选顺序（K02 / `data/README.md` §4.4）。
CANDIDATE_ENCODINGS: tuple[str, ...] = ("UTF-8", "CP437", "GBK", "CP932", "CP949", "CP1251")

#: 候选名 → Python codec 名（`codecs` 解码，不做任何大小写转换）。
CODECS: dict[str, str] = {
    "UTF-8": "utf-8",
    "CP437": "cp437",
    "GBK": "gbk",
    "CP932": "cp932",
    "CP949": "cp949",
    "CP1251": "cp1251",
}

#: **双字节**候选：结构约束严格（非法序列即解码失败），因此"完整解码"本身是强证据。
#: 单字节候选（CP437 / CP1251）对任意字节都"能解"，证据强度天然弱一档（§4.4 的 `medium` 判据）。
MULTIBYTE_CANDIDATES: frozenset[str] = frozenset({"UTF-8", "GBK", "CP932", "CP949"})

#: `unzip` 的名字解码用的 OEM 码页。**它不是候选编码之一**（K02 的六项里没有 CP850）：
#: 候选是"这串字节最可能是哪种编码"，CP850 是"这台机器的 Info-ZIP 用哪个码页解释 OEM 字节"。
#: 两者混在一起会让候选列表失真，所以单列。
UNZIP_CODEC = "cp850"

#: `7zip` / `libarchive` 在 bit 11 未置位时用的**宿主 ANSI 代码页**（实测：本机中文 Windows → GBK）。
#:
#: 这一条是**环境事实**，不是"字符集探测算法"的模拟：实测两者都不做猜测——
#: 有效的 UTF-8 字节（`norm.zip` 的 `café`，bit 11 未置位）照样被按 GBK 解释成
#: `cafe茅.txt` / `cafe虂.txt`；CP932 字节被按 GBK 解释成 `擔杮岅柤.txt`。
#: 所以模型写"按声明的 ANSI 码页解"（可解释、可复现），不写"它会猜"。
#: 换宿主时这个声明的值要跟着换（`docs/rules.md` §八）。
ANSI_CODEC = "gbk"

#: 四个提取器（`data/tool-matrix/` 的列名，顺序固定）。
EXTRACTORS: tuple[str, ...] = ("python-zipfile", "info-zip-unzip", "7zip", "libarchive")

#: `predictedNames[*].rule` 的封闭词表（新增取值同提交改 `data/README.md` §4.12）。
PREDICTION_RULES: tuple[str, ...] = (
    "upath_override",
    "utf8_bit11",
    "ansi_codepage",
    "cp437_fallback",
    "cp850_oem_transliterated",
    "undecodable",
)

#: `precedent` 的合法取值（每条规则一个出处，`docs/rules.md` §二 已给到逐规则行号）。
PRECEDENTS: tuple[str, ...] = (
    "apnote_d1_d2_encoding",  # 候选顺序与 CP437/UTF-8 的取舍
    "apnote_d6_upath_crc",  # 0x7075 的 NameCRC32 校验失配
)

#: `0x7075` 的候选编码：字段体声明「UTF-8 version of the entry File Name」（APPNOTE §4.6.9）。
UPATH_CODEC = "utf-8"

#: 只记录不解释的 extra id（M5 也不解释它们，但报告里要能看见）。
RECORD_ONLY_IDS: tuple[int, ...] = (UCOMMENT_ID, EXT_TIMESTAMP_ID)

#: OEM→ANSI best-fit 替换表：**逐条实测**（本机 UnZip 6.00 / Cygwin，2026-10-21）。
#:
#: 键 = `cp850` 解码得到的字符；值 = 实际落盘字符（`""` = 该字符被丢弃）。33 个码点，
#: 其余 95 个高位字节 `cp850` 解码即为落盘形。实测方法与 128 字节逐字节对照见
#: `data/README.md` §4.12 的 M5 记录；**这张表是数据不是规则**（同 `$UpCase` 表的性质），
#: 换宿主时整表重测，不在这里加"近似推断"。
CP850_TRANSLITERATION: dict[str, str] = {
    "\u00ff": "",  # 0x98 ÿ → 丢弃
    "\u0192": "\x83",  # 0x9f ƒ
    "\u2591": "\u00a6",  # 0xb0 ░ → ¦
    "\u2592": "\u00a6",  # 0xb1 ▒ → ¦
    "\u2593": "\u00a6",  # 0xb2 ▓ → ¦
    "\u2502": "\u00a6",  # 0xb3 │ → ¦
    "\u2524": "\u00a6",  # 0xb4 ┤ → ¦
    "\u2563": "\u00a6",  # 0xb9 ╣ → ¦
    "\u2551": "\u00a6",  # 0xba ║ → ¦
    "\u2560": "\u00a6",  # 0xcc ╠ → ¦
    "\u2588": "\u00a6",  # 0xdb █ → ¦
    "\u25a0": "\u00a6",  # 0xfe ■ → ¦
    "\u2557": "+",  # 0xbb ╗
    "\u255d": "+",  # 0xbc ╝
    "\u2510": "+",  # 0xbf ┐
    "\u2514": "+",  # 0xc0 └
    "\u251c": "+",  # 0xc3 ├
    "\u253c": "+",  # 0xc5 ┼
    "\u255a": "+",  # 0xc8 ╚
    "\u2554": "+",  # 0xc9 ╔
    "\u256c": "+",  # 0xce ╬
    "\u2518": "+",  # 0xd9 ┘
    "\u250c": "+",  # 0xda ┌
    "\u2534": "-",  # 0xc1 ┴
    "\u252c": "-",  # 0xc2 ┬
    "\u2500": "-",  # 0xc4 ─
    "\u2569": "-",  # 0xca ╩
    "\u2566": "-",  # 0xcb ╦
    "\u2550": "-",  # 0xcd ═
    "\u2584": "_",  # 0xdc ▄
    "\u2580": "\u00af",  # 0xdf ▀ → ¯
    "\u0131": "i",  # 0xd5 ı → i
    "\u2017": "=",  # 0xf2 ‗ → =
}


@dataclass(frozen=True)
class UpathField:
    """`0x7075` 的结构事实。`crc_valid is None` = 字段不存在。"""

    present: bool
    version: int | None = None
    name_crc32: int | None = None
    utf8_name: str | None = None
    crc_valid: bool | None = None

    def to_dict(self) -> dict:
        return {
            "present": self.present,
            "version": self.version,
            "name_crc32": self.name_crc32,
            "utf8_name": self.utf8_name,
            "crc_valid": self.crc_valid,
        }


@dataclass(frozen=True)
class NameFacts:
    """一个条目的名字层结构事实（`inspect` 的输出）。**不含任何推断出的"会写成什么名"**。"""

    entry_index: int
    raw_name_hex: str
    raw_name_length: int
    bit11: bool
    extra_ids: tuple[int, ...]
    upath: UpathField

    def to_dict(self) -> dict:
        return {
            "entryIndex": self.entry_index,
            "rawNameHex": self.raw_name_hex,
            "rawNameLength": self.raw_name_length,
            "bit11": self.bit11,
            "extraIds": list(self.extra_ids),
            "upath": self.upath.to_dict(),
        }


def _find(extra: tuple[ExtraField, ...], field_id: int) -> ExtraField | None:
    return next((item for item in extra if item.field_id == field_id), None)


def expected_name_crc(entry: EntryView) -> int:
    """`0x7075` 的 `NameCRC32` 应当等于的値：**条目原名字节**的 CRC32（APPNOTE 6.3.10 D.6）。"""

    return zlib.crc32(entry.cd_name) & 0xFFFFFFFF


def parse_upath(entry: EntryView) -> UpathField:
    """解析 `0x7075`：`version(1) / name_crc32(4) / utf8_name(rest)`。

    CRC 按**条目原名字节**校验（APPNOTE 6.3.10 D.6）。结构不完整时 `present=True` 但
    `crc_valid=None`——"字段在但读不懂"与"字段不在"是两件事，不能合并。
    """

    field = _find(entry.cd_extra, UPATH_ID)
    if field is None:
        return UpathField(present=False)
    if len(field.data) < 5:
        return UpathField(present=True)
    version = field.data[0]
    name_crc32 = int.from_bytes(field.data[1:5], "little")
    raw_utf8 = field.data[5:]
    try:
        utf8_name: str | None = raw_utf8.decode("utf-8")
    except UnicodeDecodeError:
        utf8_name = None
    return UpathField(
        present=True,
        version=version,
        name_crc32=name_crc32,
        utf8_name=utf8_name,
        crc_valid=name_crc32 == expected_name_crc(entry),
    )


def describe(entry: EntryView) -> NameFacts:
    return NameFacts(
        entry_index=entry.index,
        raw_name_hex=entry.cd_name.hex(),
        raw_name_length=len(entry.cd_name),
        bit11=bool(entry.cd_flags & FLAG_UTF8),
        extra_ids=tuple(item.field_id for item in entry.cd_extra),
        upath=parse_upath(entry),
    )


def describe_all(archive: Archive) -> tuple[NameFacts, ...]:
    """按 CD 顺序（= `entry_index` 升序）给出全部条目的名字层事实。"""

    return tuple(describe(entry) for entry in archive.entries)


# ------------------------------------------------------------------ M5：推断


def is_common_zone(text: str) -> bool:
    """"常用字区"的判据（`data/README.md` §4.4 的 `medium` 档，唯一表述）。

    定义为：每个字符要么是 ASCII 可打印字符，要么 Unicode 类别属于 **字母 / 标记 / 数字**
    （`L*` / `M*` / `N*`）。符号（`S*`，含框线 `U+2500` 段与 `√`）与非 ASCII 标点
    **不算**常用字区——这正是 CP437 解 GBK 字节得到的那类"能解但是乱码"的形态。

    判据只用 `unicodedata` 的类别，不做任何大小写/规范化变换（K10）。
    """

    for ch in text:
        if " " <= ch <= "~":
            continue
        if unicodedata.category(ch)[0] in {"L", "M", "N"}:
            continue
        return False
    return True


def decode(raw: bytes, encoding: str) -> str | None:
    """按候选名解码；解不全返回 `None`（**不**用 replace/ignore 伪造结果）。

    `encoding` 可以是 `CODECS` 里的候选名，也可以是 `UNZIP_CODEC`（`cp850`，不是候选）。
    """

    codec = CODECS.get(encoding, encoding)
    try:
        return raw.decode(codec)
    except (UnicodeDecodeError, LookupError):
        return None


def candidates(raw: bytes) -> list[dict]:
    """候选列表：只收**完整解码**成功的候选，顺序按 K02（`data/README.md` §4.4）。"""

    out: list[dict] = []
    for name in CANDIDATE_ENCODINGS:
        text = decode(raw, name)
        if text is None:
            continue
        out.append(
            {
                "encoding": name,
                "name": text,
                # 双字节候选的"完整解码"本身即强证据；单字节恒可解 → 只到 medium 档的下一级。
                "strongStructure": name in MULTIBYTE_CANDIDATES,
                "commonZone": is_common_zone(text),
            }
        )
    return out


def preferred(candidate_list: list[dict]) -> dict | None:
    """在候选里挑一个"最像真名"的。判据（§4.4）：

    1. 双字节完整解码优先于单字节（单字节对任意字节都成立，证据弱）；
    2. 同档内按 K02 顺序（稳定、可解释，不用频率表这类无出处的东西）。

    返回 `None` 表示一个候选都解不全——此时**不编造**替代名。
    """

    if not candidate_list:
        return None
    order = {name: index for index, name in enumerate(CANDIDATE_ENCODINGS)}
    ranked = sorted(
        candidate_list,
        key=lambda item: (0 if item["strongStructure"] else 1, order[item["encoding"]]),
    )
    return ranked[0]


def _transliterate_oem(text: str) -> str:
    """把 `cp850` 解码结果过一遍实测的 OEM→ANSI best-fit 表（只替换字符，不改变大小写）。"""

    return "".join(CP850_TRANSLITERATION.get(ch, ch) for ch in text)


def _prediction(name: str | None, rule: str, **extra) -> dict:
    assert rule in PREDICTION_RULES, rule
    record: dict = {"name": name, "rule": rule}
    record.update(extra)
    return record


def predict_names(
    raw: bytes,
    bit11: bool,
    upath: UpathField,
    chosen: dict | None,
) -> dict[str, dict]:
    """四个提取器各自的落盘名预测（模型见模块头表与 `data/README.md` §4.12）。

    两条纪律：

    - **不可解码就 `null` + `reason`**，不拿别的编码猜一个出来；
    - `unzip` 走实测的 OEM 路径（`cp850` + best-fit），`7zip`/`libarchive` 走实测的
      ANSI 码页路径——都不按"它应该和谁一致"去凑。
    """

    upath_hit = upath.present and upath.crc_valid is True and upath.utf8_name is not None
    utf8_text = None
    if bit11:
        utf8_text = decode(raw, "UTF-8")
    cp437_text = decode(raw, "CP437")
    cp850_text = decode(raw, UNZIP_CODEC)
    ansi_text = decode(raw, ANSI_CODEC)

    if upath_hit:
        override = _prediction(upath.utf8_name, "upath_override", source=UPATH_CODEC)
        return {tool: dict(override) for tool in EXTRACTORS}

    out: dict[str, dict] = {}
    # python-zipfile：0x7075 → bit11 → CP437。
    if utf8_text is not None:
        out["python-zipfile"] = _prediction(utf8_text, "utf8_bit11")
    else:
        out["python-zipfile"] = _prediction(cp437_text, "cp437_fallback")

    # info-zip-unzip：0x7075 → 实测的 OEM 路径（cp850 解码 + best-fit）。bit 11 不改变本机落盘形
    # （实测：置位/未置位同一份 UTF-8 字节给出同一结果，§4.12）。
    out["info-zip-unzip"] = _prediction(
        _transliterate_oem(cp850_text), "cp850_oem_transliterated", source=UNZIP_CODEC
    )

    # 7zip / libarchive：0x7075 → bit11 → **声明的 ANSI 码页**（实测不做字符集探测，见常量注释）。
    for tool in ("7zip", "libarchive"):
        if utf8_text is not None:
            out[tool] = _prediction(utf8_text, "utf8_bit11")
        elif ansi_text is not None:
            out[tool] = _prediction(ansi_text, "ansi_codepage", source=ANSI_CODEC)
        elif chosen is not None:
            # 声明码页解不全，但候选里另有解全的：如实给出，并说明依据来自哪个候选。
            out[tool] = _prediction(chosen["name"], "ansi_codepage", source=chosen["encoding"])
        else:
            out[tool] = _prediction(None, "undecodable", reason="no_complete_candidate")
    return out


def confidence(bit11: bool, upath: UpathField, chosen: dict | None) -> str:
    """条目级可信度（`data/README.md` §4.4）：

    - `high`：bit 11 置位，或 `0x7075` 存在且 CRC 通过；
    - `medium`：胜出的候选完整解码且全部落在常用字区；
    - `low`：其余（含 CRC 失配、无完整候选、解码含符号/控制字符）。
    """

    if bit11:
        return "high"
    if upath.present and upath.crc_valid is True:
        return "high"
    if upath.present and upath.crc_valid is False:
        return "low"
    if chosen is not None and chosen["commonZone"]:
        return "medium"
    return "low"


def check(archive: Archive) -> tuple[tuple[Finding, ...], list[dict]]:
    """MOD-2 的全部判定：`(findings, 报告块)`。

    报告块是**按 `entry_index` 升序**的数组（与 `entries[]` 同序，便于对读）；字段口径见
    `data/README.md` §4.12。
    """

    findings: list[Finding] = []
    block: list[dict] = []

    for entry in archive.entries:
        facts = describe(entry)
        candidate_list = candidates(entry.cd_name)
        chosen = preferred(candidate_list)
        level = confidence(facts.bit11, facts.upath, chosen)
        predictions = predict_names(entry.cd_name, facts.bit11, facts.upath, chosen)

        if facts.upath.present and facts.upath.crc_valid is False:
            findings.append(
                Finding(
                    rule_id="encoding.UPATH_CRC_MISMATCH",
                    message=(
                        "Unicode path extra field 的 NameCRC32 与条目原名字节不符："
                        "0x7075 的覆盖失效，按原名字节解释（不同工具会写出不同名字）"
                    ),
                    evidence={
                        "fieldId": UPATH_ID,
                        "version": facts.upath.version,
                        "nameCrc32": facts.upath.name_crc32,
                        "expectedCrc32": expected_name_crc(entry),
                        "utf8Name": facts.upath.utf8_name,
                        "downgradedTo": level,
                    },
                    precedent="apnote_d6_upath_crc",
                    entry_index=entry.index,
                    lfh_offset=entry.lfh_offset,
                    cd_offset=entry.cd_offset,
                    lfh_name=entry.lfh_name.decode("utf-8", "backslashreplace"),
                    cd_name=entry.cd_name.decode("utf-8", "backslashreplace"),
                )
            )

        block.append(
            {
                "entryIndex": entry.index,
                "rawNameHex": facts.raw_name_hex,
                "bit11": facts.bit11,
                "upath": facts.upath.to_dict(),
                "candidates": candidate_list,
                "preferred": chosen["encoding"] if chosen is not None else None,
                "confidence": level,
                "effectiveName": predictions["7zip"]["name"]
                if predictions["7zip"]["rule"] == "upath_override"
                else (chosen["name"] if chosen is not None else None),
                "predictedNames": predictions,
            }
        )

    return sort_findings(findings), block


def count_low_confidence(block: list[dict]) -> int:
    """`confidence == "low"` 的条目数（`summary` 的邻近字段；**不**参与退码，§4.1 仍是三条来源）。"""

    return sum(1 for item in block if item["confidence"] == "low")


__all__ = [
    "ANSI_CODEC",
    "CANDIDATE_ENCODINGS",
    "CODECS",
    "CP850_TRANSLITERATION",
    "EXT_TIMESTAMP_ID",
    "EXTRACTORS",
    "FLAG_UTF8",
    "MULTIBYTE_CANDIDATES",
    "PRECEDENTS",
    "PREDICTION_RULES",
    "RECORD_ONLY_IDS",
    "UCOMMENT_ID",
    "UNZIP_CODEC",
    "UPATH_CODEC",
    "UPATH_ID",
    "NameFacts",
    "UpathField",
    "candidates",
    "check",
    "confidence",
    "count_low_confidence",
    "decode",
    "describe",
    "describe_all",
    "expected_name_crc",
    "is_common_zone",
    "parse_upath",
    "predict_names",
    "preferred",
]
