"""Structured extraction of ONS2 (es.file) into editable JSON catalogs and blocks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.esfile import SCHEMA_VERSION, __version__
from tools.esfile.codec import (
    EsFileError,
    EsFileFormatError,
    check_case_collisions,
    decode_ons2,
    resolve_safe_output_path,
    sha256_hex,
)
from tools.esfile.parser import parse_script


def _serialize_json_deterministic(payload: dict[str, Any]) -> bytes:
    """Serialize a dictionary to deterministic UTF-8 JSON bytes with LF line endings."""
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    return text.encode("utf-8")


def extract_esfile(
    input_path: Path,
    output_dir: Path,
    *,
    force: bool = False,
    strict: bool = True,
    encoding: str = "utf-8",
    keep_raw: bool = False,
    report_path: Path | None = None,
) -> dict[str, Any]:
    """Extract an ONS2 archive (`es.file`) into a structured translation directory."""
    if encoding.lower().replace("-", "") != "utf8":
        raise EsFileError(
            f"Unsupported script encoding {encoding!r}: Umineko Project ONS2 scripts use UTF-8."
        )
    if not input_path.exists() or not input_path.is_file():
        raise EsFileError(f"Input file does not exist or is not a regular file: {input_path}")

    if output_dir.exists():
        if output_dir.is_symlink():
            raise EsFileError(f"Output directory must not be a symlink: {output_dir}")
        if not output_dir.is_dir():
            raise EsFileError(f"Output path exists and is not a directory: {output_dir}")
        if any(output_dir.iterdir()) and not force:
            raise EsFileError(
                f"Output directory is not empty: {output_dir} (use --force to overwrite)."
            )
    else:
        output_dir.mkdir(parents=True, exist_ok=True)

    raw_bytes = input_path.read_bytes()
    container = decode_ons2(raw_bytes, strict=strict, verify_gameid=True)
    try:
        plaintext_str = container.plaintext_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise EsFileFormatError(f"UTF-8 decoding failed: {exc}") from exc

    parsed = parse_script(plaintext_str)

    # Collect all relative paths to check for security & case-insensitive collisions
    all_rel_paths: list[str] = ["manifest.json", "report.json"]
    all_rel_paths.extend(parsed.catalogs.keys())
    all_rel_paths.extend(blk.rel_path for blk in parsed.blocks)
    if keep_raw:
        all_rel_paths.append("raw/decoded_script.txt")
    check_case_collisions(all_rel_paths)

    # Write catalog files in deterministic order
    catalog_manifest_entries: list[dict[str, Any]] = []
    total_entries = 0
    dialogue_entries = 0
    string_entries = 0

    for rel_path in sorted(parsed.catalogs.keys()):
        cat = parsed.catalogs[rel_path]
        target = resolve_safe_output_path(output_dir, rel_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        cat_bytes = _serialize_json_deterministic(cat.to_dict())
        target.write_bytes(cat_bytes)

        count = len(cat.entries)
        total_entries += count
        for entry in cat.entries:
            if entry.kind == "dialogue":
                dialogue_entries += 1
            else:
                string_entries += 1

        catalog_manifest_entries.append(
            {
                "path": rel_path,
                "category": cat.category,
                "episode": cat.episode,
                "section": cat.chapter,
                "entry_count": count,
                "sha256": sha256_hex(cat_bytes),
            }
        )

    # Write structural block files in deterministic execution order
    block_manifest_entries: list[dict[str, Any]] = []
    for blk in parsed.blocks:
        target = resolve_safe_output_path(output_dir, blk.rel_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        blk_bytes = _serialize_json_deterministic(blk.to_dict())
        target.write_bytes(blk_bytes)

        # Count physical lines covered by this block
        line_count = 0
        for rec in blk.records:
            if rec["kind"] == "raw":
                line_count += int(rec["end_line"]) - int(rec["start_line"]) + 1
            else:
                line_count += 1

        block_manifest_entries.append(
            {
                "path": blk.rel_path,
                "section": blk.block_id,
                "line_count": max(1, line_count),
                "sha256": sha256_hex(blk_bytes),
            }
        )

    if keep_raw:
        raw_target = resolve_safe_output_path(output_dir, "raw/decoded_script.txt")
        raw_target.parent.mkdir(parents=True, exist_ok=True)
        raw_target.write_bytes(container.plaintext_bytes)

    manifest_data: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "tool_version": __version__,
        "container": {
            "format": "ONS2",
            "magic": container.header.magic.decode("ascii"),
            "key_flag": container.header.key_flag,
            "encoding": "utf-8",
            "zlib_level": container.compression_level,
            "zlib_wbits": container.compression_wbits,
            "zlib_mem_level": container.compression_mem_level,
            "original_file_size": container.file_size,
            "original_comp_size": container.header.comp_size,
            "original_uncomp_size": container.header.uncomp_size,
            "original_sha256": container.file_sha256,
            "original_zlib_adler32": container.zlib_adler32_hex,
            "plaintext_sha256": container.plaintext_sha256,
            "trailing_newline": plaintext_str.endswith("\n"),
        },
        "script_metadata": {
            "mode_directive": parsed.metadata.mode_directive,
            "gameid": parsed.metadata.gameid_directive,
            "version": parsed.metadata.chiru_mode_version,
            "releasedate": parsed.metadata.releasedate or 0,
            "localisation": parsed.metadata.localisation,
            "total_lines": parsed.metadata.total_physical_lines,
            "total_entries": total_entries,
        },
        "catalog_files": catalog_manifest_entries,
        "block_files": block_manifest_entries,
    }

    manifest_target = resolve_safe_output_path(output_dir, "manifest.json")
    manifest_bytes = _serialize_json_deterministic(manifest_data)
    manifest_target.write_bytes(manifest_bytes)

    report_data: dict[str, Any] = {
        "status": "ok",
        "tool_version": __version__,
        "container": manifest_data["container"],
        "script_metadata": manifest_data["script_metadata"],
        "counts": {
            "catalog_files": len(catalog_manifest_entries),
            "block_files": len(block_manifest_entries),
            "total_entries": total_entries,
            "dialogue_entries": dialogue_entries,
            "string_entries": string_entries,
            "warnings": len(parsed.warnings),
        },
        "warnings": [w.to_dict() for w in parsed.warnings],
    }

    default_report_target = resolve_safe_output_path(output_dir, "report.json")
    report_bytes = _serialize_json_deterministic(report_data)
    default_report_target.write_bytes(report_bytes)

    if report_path is not None and report_path.resolve() != default_report_target.resolve():
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_bytes(report_bytes)

    return report_data
