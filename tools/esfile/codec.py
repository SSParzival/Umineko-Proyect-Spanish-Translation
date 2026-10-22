"""Binary ONS2 container codec, ZLIB compression bridge, and path security."""

from __future__ import annotations

import ctypes
import hashlib
import os
import re
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ONS2_MAGIC = b"ONS2"
ONS2_HEADER_STRUCT = struct.Struct("<4sIII")
ONS2_HEADER_SIZE = ONS2_HEADER_STRUCT.size  # 16 bytes
ONS2_KEY_FLAG = 0x6E  # 110 ('n')
ONS2_MIN_SIZE = 0x10  # 16 bytes
ONS2_MAX_SIZE = 0x10000000  # 268,435,456 bytes (256 MiB)
GAMEID_SIGNATURE = b";gameid UminekoPS3fication"

# 256-byte bijective substitution table extracted from onscripter-new.exe
# (.rdata VMA 0x140bb6640, file offset 0xbb4840).
SUBSTITUTION_TABLE_T: bytes = bytes.fromhex(
    "376a095e7aaff5a4ba788458351e6b0c49c6c344409e6f65e4f6fe22e295c738"
    "f01a82e05b2ad8e5ce2f7425ec59c0454b6443dcb0b9306d28d116bb66989290"
    "2ca7f180c1d48bd6df242df7fb884d3c72f3db2b9373ef8583eec28d5cb20b94"
    "3da83f1c4c6e037b1d5a51a17041d0aaa07ecdd515a91876c97d7f0e3a99bfab"
    "3b143e9a04da02fd63d9fa9f4ee361be0711a61b19558e770a47e6f80dcfd733"
    "231fbc62de9b295368e821b6345287cb0879f4676954e786eab4207101bd0631"
    "0050c8b8ac5d577c89ebb7368ff2e156814ad28cf9ad60a542105f12b3ff4fdd"
    "4626a217c5759127b58ad3132ec4e99d973932050fcacc48fcae96ed6c9cb1a3"
)

_inv_t = bytearray(256)
for _idx, _val in enumerate(SUBSTITUTION_TABLE_T):
    _inv_t[_val] = _idx
INV_SUBSTITUTION_TABLE_T: bytes = bytes(_inv_t)

# Precomputed 256-byte translation tables for O(N) C-speed byte transformations:
# Outer decode: zlib_byte = T[file_byte ^ 0x86] ^ 0x23
DEOBFUSCATE_OUTER_LUT: bytes = bytes(
    SUBSTITUTION_TABLE_T[b ^ 0x86] ^ 0x23 for b in range(256)
)
# Inner decode: plain_byte = T[decomp_byte ^ 0x45] ^ 0x71
DEOBFUSCATE_INNER_LUT: bytes = bytes(
    SUBSTITUTION_TABLE_T[b ^ 0x45] ^ 0x71 for b in range(256)
)
# Inner encode: decomp_byte = INV_T[plain_byte ^ 0x71] ^ 0x45
OBFUSCATE_INNER_LUT: bytes = bytes(
    INV_SUBSTITUTION_TABLE_T[b ^ 0x71] ^ 0x45 for b in range(256)
)
# Outer encode: file_byte = INV_T[zlib_byte ^ 0x23] ^ 0x86
OBFUSCATE_OUTER_LUT: bytes = bytes(
    INV_SUBSTITUTION_TABLE_T[b ^ 0x23] ^ 0x86 for b in range(256)
)


class EsFileError(Exception):
    """Base exception for all es.file toolkit errors."""


class EsFileFormatError(EsFileError):
    """Raised when an ONS2 file or script violates binary or structural format rules."""


class EsFileSecurityError(EsFileError):
    """Raised when a path violates security, traversal, symlink, or collision rules."""


class EsFileValidationError(EsFileError):
    """Raised when extracted translation files fail validation checks."""


@dataclass(frozen=True)
class Ons2Header:
    """16-byte little-endian ONS2 container header."""

    magic: bytes
    comp_size: int
    uncomp_size: int
    key_flag: int


@dataclass(frozen=True)
class Ons2Container:
    """Decoded ONS2 container and metadata."""

    header: Ons2Header
    file_size: int
    file_sha256: str
    zlib_stream_sha256: str
    zlib_header_hex: str
    zlib_adler32_hex: str
    plaintext_bytes: bytes
    plaintext_sha256: str
    compression_level: int
    compression_wbits: int
    compression_mem_level: int
    compression_strategy: int


def sha256_hex(data: bytes) -> str:
    """Return lowercase hexadecimal SHA-256 digest of data."""
    return hashlib.sha256(data).hexdigest()


class _ZStream(ctypes.Structure):
    _fields_ = [
        ("next_in", ctypes.c_void_p),
        ("avail_in", ctypes.c_uint),
        ("total_in", ctypes.c_ulong),
        ("next_out", ctypes.c_void_p),
        ("avail_out", ctypes.c_uint),
        ("total_out", ctypes.c_ulong),
        ("msg", ctypes.c_char_p),
        ("state", ctypes.c_void_p),
        ("zalloc", ctypes.c_void_p),
        ("zfree", ctypes.c_void_p),
        ("opaque", ctypes.c_void_p),
        ("data_type", ctypes.c_int),
        ("adler", ctypes.c_ulong),
        ("reserved", ctypes.c_ulong),
    ]


_CLASSIC_LIBZ_CACHE: tuple[ctypes.CDLL | None, bytes | None] | None = None


def _find_classic_libz() -> tuple[ctypes.CDLL | None, bytes | None]:
    """Locate a classic GNU/Madler libz.so (non-zlib-ng) if present on the host."""
    global _CLASSIC_LIBZ_CACHE
    if _CLASSIC_LIBZ_CACHE is not None:
        return _CLASSIC_LIBZ_CACHE

    candidates: list[Path] = []
    env_libz = os.environ.get("ESFILE_LIBZ_PATH")
    if env_libz:
        candidates.append(Path(env_libz))

    # Standard system locations
    for sys_dir in (
        Path("/lib/x86_64-linux-gnu"),
        Path("/usr/lib/x86_64-linux-gnu"),
        Path("/usr/lib64"),
        Path("/usr/lib"),
    ):
        for name in ("libz.so.1.3.1", "libz.so.1.2.13", "libz.so.1"):
            p = sys_dir / name
            if p.is_file():
                candidates.append(p)

    # User runtime locations (Steam Runtime / Flatpak runtimes often provide classic libz on zlib-ng distros)
    try:
        local_share = Path.home() / ".local" / "share"
        for sub in ("umu", "Steam", "flatpak"):
            base = local_share / sub
            if base.is_dir():
                for found in sorted(base.rglob("libz.so.1.*")):
                    if "i386" not in str(found) and found.is_file():
                        candidates.append(found)
    except Exception:
        pass

    for path in candidates:
        try:
            lib = ctypes.CDLL(str(path))
            lib.zlibVersion.restype = ctypes.c_char_p
            ver: bytes = lib.zlibVersion()
            if ver and b"zlib-ng" not in ver:
                _CLASSIC_LIBZ_CACHE = (lib, ver)
                return _CLASSIC_LIBZ_CACHE
        except Exception:
            continue

    _CLASSIC_LIBZ_CACHE = (None, None)
    return _CLASSIC_LIBZ_CACHE


def compress_zlib_deterministic(
    data: bytes,
    *,
    level: int = 6,
    wbits: int = 15,
    mem_level: int = 9,
    strategy: int = zlib.Z_DEFAULT_STRATEGY,
    expected_sha256: str | None = None,
) -> bytes:
    """Compress `data` into a standard RFC 1950 ZLIB stream.

    Uses classic `libz` via ctypes when available so that outputs match PHP's
    `gzcompress($data, 6)` (`deflateInit2` with `memLevel=9`) bit-for-bit, even on
    systems where Python's `zlib` module is linked against `zlib-ng`.
    Falls back to Python's standard `zlib.compressobj` when classic `libz` is unavailable.
    """
    lib, ver = _find_classic_libz()
    mem_levels_to_try = [mem_level]
    if expected_sha256 is not None:
        for alt in (9, 8):
            if alt not in mem_levels_to_try:
                mem_levels_to_try.append(alt)

    first_result: bytes | None = None

    if lib is not None and ver is not None:
        for ml in mem_levels_to_try:
            try:
                strm = _ZStream()
                ret = lib.deflateInit2_(
                    ctypes.byref(strm),
                    level,
                    8,  # Z_DEFLATED
                    wbits,
                    ml,
                    strategy,
                    ver,
                    ctypes.sizeof(_ZStream),
                )
                if ret == 0:
                    in_buf = ctypes.create_string_buffer(data, len(data))
                    out_cap = len(data) + (len(data) >> 3) + 1024
                    out_buf = ctypes.create_string_buffer(out_cap)
                    strm.next_in = ctypes.cast(in_buf, ctypes.c_void_p)
                    strm.avail_in = len(data)
                    strm.next_out = ctypes.cast(out_buf, ctypes.c_void_p)
                    strm.avail_out = out_cap
                    ret = lib.deflate(ctypes.byref(strm), 4)  # Z_FINISH = 4
                    total_out = strm.total_out
                    lib.deflateEnd(ctypes.byref(strm))
                    if ret == 1:  # Z_STREAM_END
                         candidate = out_buf.raw[:total_out]
                         if first_result is None:
                             first_result = candidate
                         if expected_sha256 is None or sha256_hex(candidate) == expected_sha256:
                             return candidate
            except Exception:
                pass

    for ml in mem_levels_to_try:
        cobj = zlib.compressobj(level, zlib.DEFLATED, wbits, ml, strategy)
        candidate = cobj.compress(data) + cobj.flush()
        if first_result is None:
            first_result = candidate
        if expected_sha256 is None or sha256_hex(candidate) == expected_sha256:
            return candidate

    assert first_result is not None
    return first_result


def parse_ons2_header(data: bytes) -> Ons2Header:
    """Parse and validate the 16-byte ONS2 header."""
    if len(data) < ONS2_HEADER_SIZE:
        raise EsFileFormatError(
            f"Truncated ONS2 header: expected at least {ONS2_HEADER_SIZE} bytes, got {len(data)} bytes."
        )
    magic, comp_size, uncomp_size, key_flag = ONS2_HEADER_STRUCT.unpack_from(data, 0)
    if magic != ONS2_MAGIC:
        raise EsFileFormatError(
            f"Invalid ONS2 magic bytes: expected {ONS2_MAGIC!r}, got {magic!r}."
        )
    if key_flag != ONS2_KEY_FLAG:
        raise EsFileFormatError(
            f"Unsupported ONS2 key_flag: expected 0x{ONS2_KEY_FLAG:02x} ({ONS2_KEY_FLAG}), "
            f"got 0x{key_flag:08x} ({key_flag})."
        )
    if not (ONS2_MIN_SIZE <= comp_size <= ONS2_MAX_SIZE):
        raise EsFileFormatError(
            f"Invalid ONS2 comp_size {comp_size}: must be in range [{ONS2_MIN_SIZE}, {ONS2_MAX_SIZE}]."
        )
    if not (ONS2_MIN_SIZE <= uncomp_size <= ONS2_MAX_SIZE):
        raise EsFileFormatError(
            f"Invalid ONS2 uncomp_size {uncomp_size}: must be in range [{ONS2_MIN_SIZE}, {ONS2_MAX_SIZE}]."
        )
    return Ons2Header(
        magic=magic,
        comp_size=comp_size,
        uncomp_size=uncomp_size,
        key_flag=key_flag,
    )


def decode_ons2(
    data: bytes,
    *,
    strict: bool = True,
    verify_gameid: bool = True,
) -> Ons2Container:
    """Decode an ONS2 binary archive into its UTF-8 script payload and metadata."""
    header = parse_ons2_header(data)
    expected_file_size = ONS2_HEADER_SIZE + header.comp_size
    if len(data) < expected_file_size:
        raise EsFileFormatError(
            f"Truncated ONS2 payload: header declares comp_size={header.comp_size} "
            f"(total {expected_file_size} bytes), but file has {len(data)} bytes."
        )
    if len(data) > expected_file_size and strict:
        raise EsFileFormatError(
            f"Unexpected trailing bytes in ONS2 file: header declares comp_size={header.comp_size} "
            f"(total {expected_file_size} bytes), but file has {len(data)} bytes."
        )

    payload = data[ONS2_HEADER_SIZE:expected_file_size]
    zlib_stream = payload.translate(DEOBFUSCATE_OUTER_LUT)
    if len(zlib_stream) < 6:
        raise EsFileFormatError("Deobfuscated ZLIB stream is too short (< 6 bytes).")

    try:
        dobj = zlib.decompressobj()
        decomp = dobj.decompress(zlib_stream, header.uncomp_size + 1024)
        decomp += dobj.flush()
    except zlib.error as exc:
        raise EsFileFormatError(f"Corrupted ZLIB stream in ONS2 payload: {exc}") from exc

    if not dobj.eof:
        raise EsFileFormatError(
            "Incomplete or truncated ZLIB stream (EOF marker not reached within bounds)."
        )
    if dobj.unused_data and strict:
        raise EsFileFormatError(
            f"Unexpected {len(dobj.unused_data)} trailing bytes after ZLIB stream end."
        )
    if len(decomp) != header.uncomp_size:
        raise EsFileFormatError(
            f"Decompressed size mismatch: header declares uncomp_size={header.uncomp_size}, "
            f"but ZLIB inflation produced {len(decomp)} bytes."
        )

    plaintext = decomp.translate(DEOBFUSCATE_INNER_LUT)

    if b"\x00" in plaintext:
        raise EsFileFormatError("Decoded script contains forbidden NUL (0x00) bytes.")

    try:
        plaintext.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise EsFileFormatError(
            f"Decoded script is not valid UTF-8 at byte offset {exc.start}: {exc.reason}"
        ) from exc

    if verify_gameid and GAMEID_SIGNATURE not in plaintext[:256]:
        raise EsFileFormatError(
            f"Missing required engine signature {GAMEID_SIGNATURE.decode('ascii')!r} in the first 256 bytes."
        )

    return Ons2Container(
        header=header,
        file_size=len(data),
        file_sha256=sha256_hex(data),
        zlib_stream_sha256=sha256_hex(zlib_stream),
        zlib_header_hex=zlib_stream[:2].hex(),
        zlib_adler32_hex=zlib_stream[-4:].hex(),
        plaintext_bytes=plaintext,
        plaintext_sha256=sha256_hex(plaintext),
        compression_level=6,
        compression_wbits=15,
        compression_mem_level=9,
        compression_strategy=0,
    )


def encode_ons2(
    plaintext: bytes,
    *,
    level: int = 6,
    wbits: int = 15,
    mem_level: int = 9,
    strategy: int = 0,
    key_flag: int = ONS2_KEY_FLAG,
    expected_zlib_sha256: str | None = None,
    verify_gameid: bool = True,
) -> bytes:
    """Encode a UTF-8 script payload into an ONS2 binary container."""
    uncomp_size = len(plaintext)
    if not (ONS2_MIN_SIZE <= uncomp_size <= ONS2_MAX_SIZE):
        raise EsFileFormatError(
            f"Plaintext size {uncomp_size} is outside valid ONS2 range [{ONS2_MIN_SIZE}, {ONS2_MAX_SIZE}]."
        )
    if b"\x00" in plaintext:
        raise EsFileFormatError("Cannot encode script containing NUL (0x00) bytes.")
    try:
        plaintext.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise EsFileFormatError(
            f"Cannot encode invalid UTF-8 script at byte offset {exc.start}: {exc.reason}"
        ) from exc

    if verify_gameid and GAMEID_SIGNATURE not in plaintext[:256]:
        raise EsFileFormatError(
            f"Script must contain {GAMEID_SIGNATURE.decode('ascii')!r} within the first 256 bytes."
        )

    inner_obfuscated = plaintext.translate(OBFUSCATE_INNER_LUT)
    zlib_stream = compress_zlib_deterministic(
        inner_obfuscated,
        level=level,
        wbits=wbits,
        mem_level=mem_level,
        strategy=strategy,
        expected_sha256=expected_zlib_sha256,
    )
    comp_size = len(zlib_stream)
    if not (ONS2_MIN_SIZE <= comp_size <= ONS2_MAX_SIZE):
        raise EsFileFormatError(
            f"Compressed size {comp_size} is outside valid ONS2 range [{ONS2_MIN_SIZE}, {ONS2_MAX_SIZE}]."
        )

    outer_obfuscated = zlib_stream.translate(OBFUSCATE_OUTER_LUT)
    header_bytes = ONS2_HEADER_STRUCT.pack(ONS2_MAGIC, comp_size, uncomp_size, key_flag)
    return header_bytes + outer_obfuscated


# --- Path Security Utilities (Requirement 28) ---

_WINDOWS_RESERVED_NAMES = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
)
_INVALID_PATH_CHARS_RE = re.compile(r'[\x00-\x1f<>:"|?*\\]')
_DRIVE_PREFIX_RE = re.compile(r"^[A-Za-z]:")


def validate_safe_relative_path(rel_path: str) -> str:
    """Validate that `rel_path` is a safe, portable relative POSIX path.

    Rejects:
    - Empty paths
    - Absolute paths (leading `/` or `\\` or Windows drive letter `C:`)
    - Backslashes (`\\`)
    - Parent traversal (`..`) or current-dir (`.`) segments
    - Control characters or Windows-forbidden characters (`<>:"|?*`)
    - Leading/trailing spaces or trailing dots in path components
    - Windows reserved device names (`CON`, `PRN`, `AUX`, `NUL`, `COM1..9`, `LPT1..9`)
    """
    if not rel_path or not isinstance(rel_path, str):
        raise EsFileSecurityError("Relative path must be a non-empty string.")
    if rel_path.startswith(("/", "\\")) or _DRIVE_PREFIX_RE.match(rel_path):
        raise EsFileSecurityError(f"Absolute or drive-prefixed path is forbidden: {rel_path!r}")
    if _INVALID_PATH_CHARS_RE.search(rel_path):
        raise EsFileSecurityError(
            f"Path contains forbidden or non-portable characters: {rel_path!r}"
        )

    parts = rel_path.split("/")
    for part in parts:
        if not part:
            raise EsFileSecurityError(f"Path contains empty component: {rel_path!r}")
        if part in (".", ".."):
            raise EsFileSecurityError(f"Path traversal component {part!r} is forbidden: {rel_path!r}")
        if part != part.strip() or part.endswith("."):
            raise EsFileSecurityError(
                f"Path component {part!r} has leading/trailing whitespace or trailing dot: {rel_path!r}"
            )
        stem = part.split(".")[0].upper()
        if stem in _WINDOWS_RESERVED_NAMES:
            raise EsFileSecurityError(
                f"Path component {part!r} uses reserved device name {stem!r}: {rel_path!r}"
            )

    return rel_path


def check_case_collisions(rel_paths: Iterable[str]) -> None:
    """Ensure no two relative paths collide on case-insensitive filesystems."""
    seen: dict[str, str] = {}
    for path in rel_paths:
        validate_safe_relative_path(path)
        lowered = path.lower()
        if lowered in seen and seen[lowered] != path:
            raise EsFileSecurityError(
                f"Case-insensitive path collision detected between {seen[lowered]!r} and {path!r}."
            )
        seen[lowered] = path


def resolve_safe_output_path(base_dir: Path, rel_path: str) -> Path:
    """Resolve `rel_path` inside `base_dir`, rejecting symlinks and escapes."""
    validate_safe_relative_path(rel_path)
    if base_dir.is_symlink():
        raise EsFileSecurityError(f"Base output directory must not be a symlink: {base_dir}")
    base_resolved = base_dir.resolve()
    candidate = base_dir / rel_path

    # Check intermediate existing parents for symlinks
    cur = base_dir
    for part in rel_path.split("/"):
        cur = cur / part
        if cur.is_symlink():
            raise EsFileSecurityError(
                f"Refusing to traverse or overwrite symlink inside workspace: {cur}"
            )

    resolved = candidate.resolve()
    try:
        resolved.relative_to(base_resolved)
    except ValueError as exc:
        raise EsFileSecurityError(
            f"Resolved path {resolved} escapes base directory {base_resolved}."
        ) from exc

    return candidate
