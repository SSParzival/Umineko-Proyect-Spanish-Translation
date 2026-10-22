"""Inspection command implementation for ONS2 (es.file) containers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.esfile.codec import EsFileError, decode_ons2
from tools.esfile.parser import parse_script


def inspect_esfile(input_path: Path, *, strict: bool = True) -> dict[str, Any]:
    """Inspect an ONS2 file and return a structured summary without dumping translation text."""
    if not input_path.exists() or not input_path.is_file():
        raise EsFileError(f"Input file does not exist or is not a regular file: {input_path}")

    raw_bytes = input_path.read_bytes()
    container = decode_ons2(raw_bytes, strict=strict, verify_gameid=True)
    plaintext_str = container.plaintext_bytes.decode("utf-8", errors="strict")
    parsed = parse_script(plaintext_str)

    story_cats = [c for c in parsed.catalogs.values() if c.category == "story"]
    omake_cats = [c for c in parsed.catalogs.values() if c.category == "omake"]
    string_cats = [c for c in parsed.catalogs.values() if c.category == "strings"]

    story_entries = sum(len(c.entries) for c in story_cats)
    omake_entries = sum(len(c.entries) for c in omake_cats)
    string_entries = sum(len(c.entries) for c in string_cats)
    total_entries = story_entries + omake_entries + string_entries

    ratio = (
        (container.header.comp_size / container.header.uncomp_size) * 100.0
        if container.header.uncomp_size
        else 0.0
    )

    return {
        "file_name": input_path.name,
        "format": {
            "container_type": "ONS2",
            "magic": container.header.magic.decode("ascii"),
            "key_flag": container.header.key_flag,
            "key_flag_hex": f"0x{container.header.key_flag:02x}",
            "endianness": "little-endian",
            "header_size_bytes": 16,
            "encoding": "utf-8",
        },
        "script_metadata": parsed.metadata.to_dict(),
        "sizes": {
            "file_size_bytes": container.file_size,
            "compressed_payload_bytes": container.header.comp_size,
            "uncompressed_script_bytes": container.header.uncomp_size,
            "compression_ratio_percent": round(ratio, 2),
        },
        "compression": {
            "algorithm": "ZLIB (RFC 1950 DEFLATE)",
            "zlib_header_hex": container.zlib_header_hex,
            "level": container.compression_level,
            "wbits": container.compression_wbits,
            "mem_level": container.compression_mem_level,
        },
        "checksums": {
            "file_sha256": container.file_sha256,
            "zlib_stream_sha256": container.zlib_stream_sha256,
            "zlib_adler32": f"0x{container.zlib_adler32_hex}",
            "plaintext_sha256": container.plaintext_sha256,
        },
        "counts": {
            "total_catalogs": len(parsed.catalogs),
            "story_catalogs": len(story_cats),
            "omake_catalogs": len(omake_cats),
            "string_catalogs": len(string_cats),
            "structural_blocks": len(parsed.blocks),
            "total_entries": total_entries,
            "story_dialogue_entries": story_entries,
            "omake_dialogue_entries": omake_entries,
            "string_catalog_entries": string_entries,
            "warnings_count": len(parsed.warnings),
        },
        "warnings": [w.to_dict() for w in parsed.warnings],
    }


def format_inspection_report(info: dict[str, Any], *, verbose: bool = False) -> str:
    """Format the inspection dictionary into a clean human-readable CLI summary."""
    fmt = info["format"]
    meta = info["script_metadata"]
    sizes = info["sizes"]
    comp = info["compression"]
    sums = info["checksums"]
    cnt = info["counts"]

    lines = [
        f"=== ONS2 Container Inspection: {info['file_name']} ===",
        f"Format Type       : {fmt['container_type']} (magic={fmt['magic']!r}, key_flag={fmt['key_flag_hex']}, {fmt['endianness']})",
        f"Encoding          : {fmt['encoding'].upper()}",
        f"Game ID Directive : {meta['gameid_directive']}",
        f"Mode Directive    : {meta['mode_directive']}",
        f"Script Version    : {meta['chiru_mode_version']} (localisation={meta['localisation']!r}, releasedate={meta['releasedate']})",
        "",
        "--- Sizes & Compression ---",
        f"Container Size    : {sizes['file_size_bytes']:,} bytes (16 B header + {sizes['compressed_payload_bytes']:,} B payload)",
        f"Uncompressed Size : {sizes['uncompressed_script_bytes']:,} bytes ({sizes['compression_ratio_percent']:.2f}% of uncompressed)",
        f"Compression       : {comp['algorithm']} (header=0x{comp['zlib_header_hex']}, level={comp['level']}, wbits={comp['wbits']}, memLevel={comp['mem_level']})",
        "",
        "--- Checksums ---",
        f"File SHA-256      : {sums['file_sha256']}",
        f"ZLIB SHA-256      : {sums['zlib_stream_sha256']}",
        f"ZLIB Adler-32     : {sums['zlib_adler32']}",
        f"Plaintext SHA-256 : {sums['plaintext_sha256']}",
        "",
        "--- Script & Translation Counts ---",
        f"Physical Lines    : {meta['total_physical_lines']:,} (CRLF={meta['crlf_line_count']:,}, LF={meta['lf_line_count']:,})",
        f"Unique *Labels    : {meta['unique_label_count']:,}",
        f"Structural Blocks : {cnt['structural_blocks']}",
        f"Editable Catalogs : {cnt['total_catalogs']} (story={cnt['story_catalogs']}, omake={cnt['omake_catalogs']}, strings={cnt['string_catalogs']})",
        f"Editable Entries  : {cnt['total_entries']:,} (story={cnt['story_dialogue_entries']:,}, omake={cnt['omake_dialogue_entries']:,}, strings={cnt['string_catalog_entries']:,})",
        f"Source Warnings   : {cnt['warnings_count']}",
    ]

    if verbose and info["warnings"]:
        lines.append("")
        lines.append("--- Warnings Detail ---")
        for w in info["warnings"]:
            lines.append(f"  [L{w['line_number']}] {w['code']} ({w['entry_id']}): {w['message']}")

    return "\n".join(lines)
