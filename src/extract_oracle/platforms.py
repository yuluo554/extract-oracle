"""平台语义表（`data/platforms/`）：读取、`sha256` 对账、NTFS `$UpCase` 查表原语。

为什么是包根的叶子模块（和 `findings.py` 同一位置）：K10 要求判定模块之间互不 import，
而 `rules/fold.py` 需要一张**表**才能做 Windows 折叠。表不是判定——它是数据访问；
判定（四个 `collision.*` 的判定顺序与存活者）仍在 `rules/fold.py`。

三条契约（`plan/02` §四，K04）：

1. `source` 只能是 `volume_read` / `host_probe`——`casefold` 不是合法取值（决策记录 ③）；
2. `sha256` 必须与表本体逐字节对得上；对不上 = 表被换过 → `platform_table_missing`（退出码 3），
   **不静默使用**；
3. `probed_at_utc` 是环境事实，**不是判定输入**——`to_report_dict()` 刻意不返回它
   （否则跨机复跑的报告 digest 必红）。

本模块只读字节，不写盘、不联网。
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from .errors import OracleError, ReasonCode

#: `meta.json` 里 `ntfs_upcase.source` 的合法取值（K04）。`casefold` **不在**其中。
VALID_SOURCES: tuple[str, ...] = ("volume_read", "host_probe")

#: `data/README.md` §4.7 的四个证据强度取值（输出字段 `evidence_strength`）。
EVIDENCE_STRENGTHS: tuple[str, ...] = ("measured", "table_simulated", "medium", "inferred")

#: `$UpCase` 覆盖 BMP（U+0000–U+FFFF），每项 uint16 小端。
TABLE_CODEPOINTS = 65536
TABLE_BYTES = TABLE_CODEPOINTS * 2

BIN_NAME = "ntfs-upcase.bin"
META_NAME = "meta.json"

#: 确定表位置的候选（按序取第一个含 `meta.json` 的目录）。
#: 环境变量优先，便于冻结态/换机复跑时显式指定；路径**不出现在任何报告或错误里**。
ENV_DIR = "ORACLE_PLATFORM_DIR"


def candidate_dirs() -> list[Path]:
    """平台表目录的候选序列（顺序固定 → 同机解析结果确定）。"""

    found: list[Path] = []
    env = os.environ.get(ENV_DIR)
    if env:
        found.append(Path(env))
    # 源码树：src/extract_oracle/platforms.py → <repo>/data/platforms
    found.append(Path(__file__).resolve().parent.parent.parent / "data" / "platforms")
    # 冻结态（PyInstaller）：数据随包解包到 _MEIPASS
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        found.append(Path(meipass) / "data" / "platforms")
    found.append(Path.cwd() / "data" / "platforms")
    return found


def resolve_dir(explicit: Path | None = None) -> Path:
    """返回平台表目录；找不到抛 `PLATFORM_TABLE_MISSING`（退出码 3），**不猜、不近似**。

    `ORACLE_PLATFORM_DIR` 是**权威覆盖**（不是"候选之一"）：设了就用它，缺文件即拒。
    否则一个"设了环境变量却被静默回落到源码树"的行为会让"表缺失 → 退 3"的判据失效。
    """

    if explicit is not None:
        return explicit
    env = os.environ.get(ENV_DIR)
    if env:
        return Path(env)
    for path in candidate_dirs():
        if (path / META_NAME).is_file():
            return path
    raise OracleError(
        ReasonCode.PLATFORM_TABLE_MISSING,
        "未找到平台语义表（需要 meta.json + ntfs-upcase.bin）",
        {
            "expected": f"data/platforms/{META_NAME} + data/platforms/{BIN_NAME}",
            "env": ENV_DIR,
        },
    )


@dataclass(frozen=True)
class NtfsUpcase:
    """NTFS `$UpCase` 表：BMP 内逐码元 `upcase` 映射。

    `map_unit` **只做查表**，不做任何 Unicode 库的近似（决策 ③）。非 BMP 码点表里没有，
    原样保留（NTFS 按 UTF-16 码元比较，而表本身对代理区是恒等映射——`tests/test_m3_platforms.py`
    钉住这一条）。
    """

    table: bytes
    sha256: str
    source: str
    volume: dict
    entries: int

    def map_unit(self, unit: int) -> int:
        if 0 <= unit < self.entries:
            offset = unit * 2
            return int.from_bytes(self.table[offset : offset + 2], "little")
        return unit

    def fold(self, text: str) -> str:
        """按表折叠一个名字（逐码元查表）。`/` 是 U+002F，表对它是恒等 → 分隔符不受影响。"""

        out: list[str] = []
        for ch in text:
            codepoint = ord(ch)
            if codepoint < TABLE_CODEPOINTS:
                out.append(chr(self.map_unit(codepoint)))
            else:
                out.append(ch)  # 表只覆盖 BMP；非 BMP 原样保留（不编造映射）
        return "".join(out)

    @property
    def table_id(self) -> str:
        """报告里可出现的表指纹（sha256 前 16 位；完整值只在 `platforms --verify`）。"""

        return self.sha256[:16]


@dataclass(frozen=True)
class PlatformTables:
    """注入给判定层的平台语义表（构造参数，不做模块级全局单例——同输入双跑要求）。"""

    ntfs: NtfsUpcase
    macos: dict
    linux: dict
    #: 环境事实（探测时点）。**只供 `platforms --verify` 打印**，绝不进判定输入——见
    #: `to_report_dict()`（`plan/02` §四 第 3 条）。
    probed_at_utc: str | None = None

    @property
    def windows(self) -> NtfsUpcase:
        return self.ntfs

    def verify_report(self) -> dict:
        """`platforms --verify` 的诊断面：**含**卷标识与探测时点（那是它的用途）。

        与 `to_report_dict()` 分开正是关键：`--verify` 是"查表是否可信"的一次性诊断，
        它的输出不进任何 `check` 报告，所以带上环境事实不会污染跨机复跑。
        """

        return {
            "ntfs_upcase": {
                "entries": self.ntfs.entries,
                "sha256": self.ntfs.sha256,
                "sha256_short": self.ntfs.table_id,
                "source": self.ntfs.source,
                "volume": dict(self.ntfs.volume),
                "probed_at_utc": self.probed_at_utc,
            },
            "tables": {"linux": dict(self.linux), "macos": dict(self.macos)},
        }

    def to_report_dict(self) -> dict:
        """判定报告里的平台表身份块。

        **刻意不含**两项：`probed_at_utc`（环境事实，不是判定输入——否则跨机复跑的报告
        必红，`plan/02` §四 第 3 条）与 `volume`（卷标识是本机指纹；它只出现在
        `platforms --verify` 的诊断输出里）。表身份用 `sha256` 表达，跨机可比。
        """

        return {
            "ntfs_upcase": {
                "entries": self.ntfs.entries,
                "sha256": self.ntfs.sha256,
                "source": self.ntfs.source,
            },
            "tables": {
                "linux": {"evidence_strength": self.linux.get("evidence_strength"), "source": self.linux.get("source")},
                "macos": {"evidence_strength": self.macos.get("evidence_strength"), "source": self.macos.get("source")},
            },
        }


def _fail(message: str, **detail) -> OracleError:
    """统一的拒绝构造器。`detail` 里**不出现路径**（报告不得含本机绝对路径，K03）。"""

    return OracleError(ReasonCode.PLATFORM_TABLE_MISSING, message, dict(detail))


def _read_meta(path: Path) -> dict:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise _fail("平台表元数据读不了", reason=exc.__class__.__name__) from exc
    try:
        meta = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise _fail("平台表元数据不是合法 JSON") from None
    if not isinstance(meta, dict):
        raise _fail("平台表元数据顶层不是对象")
    return meta


def load(platform_dir: Path | None = None) -> PlatformTables:
    """读取 + 校验平台表。任何一项对不上 → `platform_table_missing`（退出码 3）。

    校验项（顺序固定，失败即拒）：
    `meta.json` 可解析 → `ntfs_upcase` 必填键齐 → `source` ∈ 枚举 → `entries` = 65536 →
    表本体长度 = `entries × 2` → `sha256(本体) == meta.sha256` → 两张副表的证据强度在枚举内。
    """

    root = resolve_dir(platform_dir)
    meta = _read_meta(root / META_NAME)

    block = meta.get("ntfs_upcase")
    if not isinstance(block, dict):
        raise _fail("meta.json 缺 ntfs_upcase 块")

    required = ("source", "volume", "entries", "sha256", "encoding")
    lack = [key for key in required if key not in block]
    if lack:
        raise _fail("meta.json 的 ntfs_upcase 缺字段", missing=lack)

    source = block["source"]
    if source not in VALID_SOURCES:
        raise _fail(
            "ntfs_upcase.source 不是合法取值（casefold 不是合法值）",
            value=source,
            allowed=list(VALID_SOURCES),
        )

    entries = block["entries"]
    if entries != TABLE_CODEPOINTS:
        raise _fail(
            "ntfs_upcase.entries 与表结构不符（$UpCase 覆盖 BMP）",
            value=entries,
            expected=TABLE_CODEPOINTS,
        )

    try:
        table = (root / BIN_NAME).read_bytes()
    except OSError as exc:
        raise _fail("平台表本体读不了", reason=exc.__class__.__name__) from exc

    if len(table) != TABLE_BYTES:
        raise _fail(
            "平台表本体长度不是 entries × 2 字节",
            actual=len(table),
            expected=TABLE_BYTES,
        )

    actual_sha = hashlib.sha256(table).hexdigest()
    if actual_sha != block["sha256"]:
        raise _fail(
            "平台表本体与 meta.json 的 sha256 对不上（表被换过）",
            expected_sha256=block["sha256"],
            actual_sha256=actual_sha,
        )

    tables = meta.get("tables") or {}
    for name in ("macos", "linux"):
        entry = tables.get(name) or {}
        strength = entry.get("evidence_strength")
        if strength not in EVIDENCE_STRENGTHS:
            raise _fail(
                "平台副表的 evidence_strength 不在枚举内",
                platform=name,
                value=strength,
                allowed=list(EVIDENCE_STRENGTHS),
            )

    return PlatformTables(
        ntfs=NtfsUpcase(
            table=table,
            sha256=actual_sha,
            source=source,
            volume=dict(block.get("volume") or {}),
            entries=entries,
        ),
        macos=dict(tables.get("macos") or {}),
        linux=dict(tables.get("linux") or {}),
        probed_at_utc=block.get("probed_at_utc"),
    )


def verify(platform_dir: Path | None = None) -> PlatformTables:
    """`platforms --verify` 的实现：真校验（不再是无条件退 3 的占位）。"""

    return load(platform_dir)


__all__ = [
    "BIN_NAME",
    "ENV_DIR",
    "EVIDENCE_STRENGTHS",
    "META_NAME",
    "NtfsUpcase",
    "PlatformTables",
    "TABLE_BYTES",
    "TABLE_CODEPOINTS",
    "VALID_SOURCES",
    "candidate_dirs",
    "load",
    "resolve_dir",
    "verify",
]
