"""Deterministic compiler (`build`) from extracted translation catalogs back to ONS2 (es.file)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from tools.esfile import SCHEMA_VERSION, __version__
from tools.esfile.codec import (
    EsFileError,
    EsFileFormatError,
    EsFileValidationError,
    check_case_collisions,
    decode_ons2,
    encode_ons2,
    resolve_safe_output_path,
    sha256_hex,
)
from tools.esfile.models import CatalogEntry, StructuralBlock, TranslationCatalog

_VALID_ENTRY_KINDS = frozenset(
    {"dialogue", "stralias", "bgm_title", "credits_line", "window_caption"}
)
_VALID_EOLS = frozenset({"CRLF", "LF", "NONE"})
_BRACKET_RE = re.compile(r"[\[\]]")


def _validate_brace_balance(text: str, entry_id: str, context: str) -> None:
    """Verify that `{` and `}` inline formatting braces are balanced."""
    depth = 0
    for ch in text:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0:
                raise EsFileValidationError(
                    f"Entry {entry_id} ({context}): unbalanced closing brace '}}' in text."
                )
    if depth != 0:
        raise EsFileValidationError(
            f"Entry {entry_id} ({context}): {depth} unclosed '{{' brace(s) in text."
        )


def validate_entry_for_build(entry: CatalogEntry, *, strict: bool = True) -> None:
    """Validate an individual `CatalogEntry` prior to script compilation."""
    if not entry.id or not isinstance(entry.id, str):
        raise EsFileValidationError("Entry has an empty or invalid 'id'.")
    if entry.kind not in _VALID_ENTRY_KINDS:
        raise EsFileValidationError(
            f"Entry {entry.id}: unsupported kind {entry.kind!r} (expected one of {sorted(_VALID_ENTRY_KINDS)})."
        )
    if entry.line_ending not in _VALID_EOLS:
        raise EsFileValidationError(
            f"Entry {entry.id}: invalid line_ending {entry.line_ending!r} (expected CRLF, LF, or NONE)."
        )
    if entry.line_number < 1:
        raise EsFileValidationError(
            f"Entry {entry.id}: invalid line_number {entry.line_number} (must be >= 1)."
        )

    if entry.kind == "dialogue":
        if not entry.segments:
            raise EsFileValidationError(f"Dialogue entry {entry.id} has 0 segments.")
        if len(entry.markers) != len(entry.segments) + 1:
            raise EsFileValidationError(
                f"Dialogue entry {entry.id}: markers count ({len(entry.markers)}) must equal "
                f"segments count + 1 ({len(entry.segments) + 1})."
            )
        for expected_idx, seg in enumerate(entry.segments):
            if seg.index != expected_idx:
                raise EsFileValidationError(
                    f"Dialogue entry {entry.id}: segment index {seg.index} out of order (expected {expected_idx})."
                )
            if "\x00" in seg.text:
                raise EsFileValidationError(
                    f"Dialogue entry {entry.id} segment {expected_idx} contains NUL byte."
                )
            if "\r" in seg.text or "\n" in seg.text:
                raise EsFileValidationError(
                    f"Dialogue entry {entry.id} segment {expected_idx} contains literal newline "
                    f"(use '{{n}}' inline tag for line breaks inside dialogue)."
                )
            if "`" in seg.text and not entry.has_stray_backtick:
                raise EsFileValidationError(
                    f"Dialogue entry {entry.id} segment {expected_idx} introduces an unescaped backtick (`)."
                )
            if _BRACKET_RE.search(seg.text):
                raise EsFileValidationError(
                    f"Dialogue entry {entry.id} segment {expected_idx} contains forbidden '[' or ']' bracket "
                    f"(control markers belong in 'markers', not segment text)."
                )
            try:
                seg.text.encode("utf-8", errors="strict")
            except UnicodeEncodeError as exc:
                raise EsFileValidationError(
                    f"Dialogue entry {entry.id} segment {expected_idx} is not valid UTF-8: {exc}"
                ) from exc
        if strict and not entry.has_unbalanced_braces:
            full_dialogue_text = "".join(seg.text for seg in entry.segments)
            _validate_brace_balance(full_dialogue_text, entry.id, "dialogue")
    else:
        if "\x00" in entry.text:
            raise EsFileValidationError(f"Entry {entry.id} contains NUL byte.")
        if '"' in entry.text and not entry.has_stray_backtick:
            raise EsFileValidationError(
                f"Entry {entry.id} contains unescaped double quote (\") which breaks ONScripter string literal."
            )
        if ("\r" in entry.text or "\n" in entry.text) and entry.line_span < 2:
            raise EsFileValidationError(
                f"Entry {entry.id} contains unexpected literal newline (use '{{n}}' inline tag)."
            )
        if strict and not entry.has_unbalanced_braces:
            _validate_brace_balance(entry.text, entry.id, "text")
        try:
            entry.text.encode("utf-8", errors="strict")
        except UnicodeEncodeError as exc:
            raise EsFileValidationError(
                f"Entry {entry.id} text is not valid UTF-8: {exc}"
            ) from exc


def load_and_validate_workspace(
    translation_dir: Path, *, strict: bool = True
) -> tuple[dict[str, Any], dict[str, TranslationCatalog], list[StructuralBlock], dict[str, CatalogEntry]]:
    """Load `manifest.json`, all `TranslationCatalog` files, and all `StructuralBlock` files."""
    if not translation_dir.exists() or not translation_dir.is_dir():
        raise EsFileError(f"Translation directory does not exist: {translation_dir}")
    if translation_dir.is_symlink():
        raise EsFileError(f"Translation directory must not be a symlink: {translation_dir}")

    manifest_path = resolve_safe_output_path(translation_dir, "manifest.json")
    if not manifest_path.is_file():
        raise EsFileValidationError(f"Missing manifest.json in {translation_dir}")

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise EsFileValidationError(f"Failed to parse manifest.json: {exc}") from exc

    if not isinstance(manifest, dict):
        raise EsFileValidationError("manifest.json root must be a JSON object.")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise EsFileValidationError(
            f"Unsupported manifest schema_version {manifest.get('schema_version')!r} "
            f"(expected {SCHEMA_VERSION!r})."
        )
    for req_key in ("container", "script_metadata", "catalog_files", "block_files"):
        if req_key not in manifest:
            raise EsFileValidationError(f"manifest.json is missing required key {req_key!r}.")

    container_meta = manifest["container"]
    if not isinstance(container_meta, dict) or container_meta.get("format") != "ONS2":
        raise EsFileValidationError("manifest.json container.format must be 'ONS2'.")

    cat_specs = manifest["catalog_files"]
    blk_specs = manifest["block_files"]
    if not isinstance(cat_specs, list) or not isinstance(blk_specs, list) or not blk_specs:
        raise EsFileValidationError("manifest.json must contain non-empty catalog_files and block_files lists.")

    all_paths = [spec.get("path", "") for spec in cat_specs] + [
        spec.get("path", "") for spec in blk_specs
    ]
    check_case_collisions(all_paths)

    catalogs: dict[str, TranslationCatalog] = {}
    entries_by_id: dict[str, CatalogEntry] = {}

    for spec in cat_specs:
        if not isinstance(spec, dict) or "path" not in spec:
            raise EsFileValidationError("Invalid catalog specification in manifest.json.")
        rel_path = str(spec["path"])
        cat_file = resolve_safe_output_path(translation_dir, rel_path)
        if not cat_file.is_file():
            raise EsFileValidationError(f"Missing catalog file referenced by manifest: {rel_path}")
        try:
            raw_cat = json.loads(cat_file.read_text(encoding="utf-8"))
            cat = TranslationCatalog.from_dict(raw_cat)
        except Exception as exc:
            raise EsFileValidationError(f"Invalid catalog file {rel_path}: {exc}") from exc

        if cat.rel_path != rel_path:
            raise EsFileValidationError(
                f"Catalog {rel_path} declares mismatched internal rel_path {cat.rel_path!r}."
            )
        expected_count = spec.get("entry_count")
        if expected_count is not None and len(cat.entries) != int(expected_count):
            raise EsFileValidationError(
                f"Catalog {rel_path} entry count ({len(cat.entries)}) does not match "
                f"manifest entry_count ({expected_count})."
            )

        prev_line = 0
        for entry in cat.entries:
            validate_entry_for_build(entry, strict=strict)
            if entry.id in entries_by_id:
                raise EsFileValidationError(f"Duplicate entry ID {entry.id!r} in catalog {rel_path}.")
            if entry.line_number <= prev_line:
                raise EsFileValidationError(
                    f"Out-of-order entry {entry.id!r} in {rel_path}: line {entry.line_number} <= {prev_line}."
                )
            prev_line = entry.line_number
            entries_by_id[entry.id] = entry

        catalogs[rel_path] = cat

    blocks: list[StructuralBlock] = []
    seen_slot_ids: set[str] = set()
    global_prev_line = 0

    for spec in blk_specs:
        if not isinstance(spec, dict) or "path" not in spec:
            raise EsFileValidationError("Invalid block specification in manifest.json.")
        rel_path = str(spec["path"])
        blk_file = resolve_safe_output_path(translation_dir, rel_path)
        if not blk_file.is_file():
            raise EsFileValidationError(f"Missing structural block file referenced by manifest: {rel_path}")
        blk_bytes = blk_file.read_bytes()
        expected_sha = spec.get("sha256")
        if expected_sha and sha256_hex(blk_bytes) != expected_sha:
            raise EsFileValidationError(
                f"Structural block file {rel_path} checksum mismatch: expected {expected_sha}, "
                f"got {sha256_hex(blk_bytes)}."
            )
        try:
            raw_blk = json.loads(blk_bytes.decode("utf-8"))
            blk = StructuralBlock.from_dict(raw_blk)
        except Exception as exc:
            raise EsFileValidationError(f"Invalid structural block file {rel_path}: {exc}") from exc

        for rec in blk.records:
            kind = rec.get("kind")
            if kind == "raw":
                start_line = int(rec.get("start_line", 0))
                if start_line < global_prev_line:
                    raise EsFileValidationError(
                        f"Block {rel_path} raw chunk at line {start_line} is out of global order (< {global_prev_line})."
                    )
                global_prev_line = int(rec.get("end_line", start_line))
            elif kind == "entry":
                slot_id = str(rec.get("id", ""))
                slot_cat = str(rec.get("catalog", ""))
                slot_line = int(rec.get("line_number", 0))
                if slot_id not in entries_by_id:
                    raise EsFileValidationError(
                        f"Block {rel_path} references unknown entry ID {slot_id!r}."
                    )
                if slot_id in seen_slot_ids:
                    raise EsFileValidationError(
                        f"Block {rel_path} references entry ID {slot_id!r} more than once."
                    )
                if slot_cat not in catalogs:
                    raise EsFileValidationError(
                        f"Block {rel_path} entry {slot_id!r} references unknown catalog {slot_cat!r}."
                    )
                if slot_line < global_prev_line:
                    raise EsFileValidationError(
                        f"Block {rel_path} entry slot {slot_id!r} at line {slot_line} is out of global order (< {global_prev_line})."
                    )
                global_prev_line = slot_line
                seen_slot_ids.add(slot_id)
            else:
                raise EsFileValidationError(
                    f"Block {rel_path} contains unsupported record kind {kind!r}."
                )

        blocks.append(blk)

    missing_slots = set(entries_by_id.keys()) - seen_slot_ids
    if missing_slots:
        sample = sorted(missing_slots)[:5]
        raise EsFileValidationError(
            f"{len(missing_slots)} catalog entries have no corresponding slot in structural blocks: {sample}"
        )

    return manifest, catalogs, blocks, entries_by_id


def build_esfile(
    translation_dir: Path,
    output_file: Path,
    *,
    force: bool = False,
    strict: bool = True,
    report_path: Path | None = None,
) -> dict[str, Any]:
    """Compile an extracted translation workspace back into an ONS2 (.file) archive."""
    if output_file.exists():
        if output_file.is_symlink():
            raise EsFileError(f"Refusing to overwrite symlink output path: {output_file}")
        if output_file.is_dir():
            raise EsFileError(f"Output path is a directory, expected a file path: {output_file}")
        if not force:
            raise EsFileError(
                f"Output file already exists: {output_file} (use --force to overwrite)."
            )

    manifest, catalogs, blocks, entries_by_id = load_and_validate_workspace(
        translation_dir, strict=strict
    )
    container_meta = manifest["container"]

    # Reconstruct full script text in exact block & slot order
    script_chunks: list[str] = []
    modified_entries = 0

    for blk in blocks:
        for rec in blk.records:
            if rec["kind"] == "raw":
                script_chunks.append(str(rec["text"]))
            else:
                entry = entries_by_id[str(rec["id"])]
                script_chunks.append(entry.reconstruct_script_line())

    reconstructed_script = "".join(script_chunks)
    if container_meta.get("trailing_newline", True) and not reconstructed_script.endswith("\n"):
        raise EsFileValidationError("Reconstructed script is missing required trailing newline.")

    plaintext_bytes = reconstructed_script.encode("utf-8", errors="strict")
    plaintext_sha = sha256_hex(plaintext_bytes)

    # Check how many catalog files differ from their extraction SHA-256
    modified_catalogs: list[str] = []
    for spec in manifest["catalog_files"]:
        rel_path = str(spec["path"])
        cat_file = resolve_safe_output_path(translation_dir, rel_path)
        if sha256_hex(cat_file.read_bytes()) != spec.get("sha256"):
            modified_catalogs.append(rel_path)

    encoded_bytes = encode_ons2(
        plaintext_bytes,
        level=int(container_meta.get("zlib_level", 6)),
        wbits=int(container_meta.get("zlib_wbits", 15)),
        mem_level=int(container_meta.get("zlib_mem_level", 9)),
        key_flag=int(container_meta.get("key_flag", 0x6E)),
        verify_gameid=True,
    )

    # Self-verify that the newly built ONS2 container decodes cleanly
    verified = decode_ons2(encoded_bytes, strict=True, verify_gameid=True)
    if verified.plaintext_sha256 != plaintext_sha:
        raise EsFileFormatError("Internal build verification failed: plaintext SHA-256 mismatch.")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_bytes(encoded_bytes)

    orig_sha = str(container_meta.get("original_sha256", ""))
    orig_pt_sha = str(container_meta.get("plaintext_sha256", ""))
    binary_identical = verified.file_sha256 == orig_sha
    plaintext_identical = verified.plaintext_sha256 == orig_pt_sha

    build_report: dict[str, Any] = {
        "status": "ok",
        "tool_version": __version__,
        "output_file": output_file.name,
        "file_size_bytes": verified.file_size,
        "comp_size_bytes": verified.header.comp_size,
        "uncomp_size_bytes": verified.header.uncomp_size,
        "file_sha256": verified.file_sha256,
        "zlib_stream_sha256": verified.zlib_stream_sha256,
        "zlib_adler32": f"0x{verified.zlib_adler32_hex}",
        "plaintext_sha256": verified.plaintext_sha256,
        "original_file_sha256": orig_sha,
        "original_plaintext_sha256": orig_pt_sha,
        "binary_identical_to_original": binary_identical,
        "plaintext_identical_to_original": plaintext_identical,
        "catalogs_loaded": len(catalogs),
        "blocks_loaded": len(blocks),
        "entries_compiled": len(entries_by_id),
        "modified_catalogs": modified_catalogs,
    }

    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_text = json.dumps(build_report, ensure_ascii=False, indent=2) + "\n"
        report_path.write_bytes(report_text.encode("utf-8"))

    return build_report
