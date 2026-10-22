"""Comprehensive validation command (`validate`) for extracted ONS2 translation workspaces."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tools.esfile import SCHEMA_VERSION, __version__
from tools.esfile.codec import (
    EsFileSecurityError,
    check_case_collisions,
    resolve_safe_output_path,
    sha256_hex,
)
from tools.esfile.models import (
    CatalogEntry,
    StructuralBlock,
    TranslationCatalog,
    extract_inline_tags,
)

_VALID_ENTRY_KINDS = frozenset(
    {"dialogue", "stralias", "bgm_title", "credits_line", "window_caption"}
)
_VALID_EOLS = frozenset({"CRLF", "LF", "NONE"})
_BRACKET_RE = re.compile(r"[\[\]]")
_MARKER_GROUP_RE = re.compile(r"^(?:\s*\[[^\]]*\])*$")


@dataclass
class ValidationIssue:
    """A single validation error or warning found in an extracted translation directory."""

    severity: str  # "error" | "warning"
    code: str
    location: str
    entry_id: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "location": self.location,
            "entry_id": self.entry_id,
            "message": self.message,
        }


@dataclass
class ValidationReport:
    """Structured result of running `validate_workspace`."""

    valid: bool
    errors: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)
    catalogs_checked: int = 0
    blocks_checked: int = 0
    entries_checked: int = 0
    modified_catalogs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": "valid" if self.valid else "invalid",
            "valid": self.valid,
            "tool_version": __version__,
            "counts": {
                "catalogs_checked": self.catalogs_checked,
                "blocks_checked": self.blocks_checked,
                "entries_checked": self.entries_checked,
                "modified_catalogs": len(self.modified_catalogs),
                "errors": len(self.errors),
                "warnings": len(self.warnings),
            },
            "modified_catalogs": list(self.modified_catalogs),
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
        }


def _check_brace_balance(text: str) -> str | None:
    depth = 0
    for ch in text:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0:
                return "Unbalanced closing brace '}' in text."
    if depth != 0:
        return f"{depth} unclosed '{{' brace(s) in text."
    return None


def _extract_tag_prefixes(tags: list[str]) -> list[str]:
    """Extract structural tag prefixes (e.g. '{n}', '{fit}', '{c:FF0000:', '{f:5:', '{p:13:')."""
    prefixes: list[str] = []
    for tag in tags:
        inner = tag[1:-1]
        parts = inner.split(":")
        if len(parts) == 1:
            prefixes.append(tag)
        elif len(parts) == 2:
            prefixes.append(f"{{{parts[0]}:")
        else:
            prefixes.append(f"{{{parts[0]}:{parts[1]}:")
    return sorted(prefixes)


def _validate_entry_detailed(
    entry: CatalogEntry,
    rel_path: str,
    errors: list[ValidationIssue],
    warnings: list[ValidationIssue],
    *,
    strict: bool = True,
) -> None:
    if not entry.id or not isinstance(entry.id, str):
        errors.append(
            ValidationIssue("error", "SCHEMA_ERROR", rel_path, "", "Entry has an empty or invalid 'id'.")
        )
        return

    if entry.kind not in _VALID_ENTRY_KINDS:
        errors.append(
            ValidationIssue(
                "error",
                "SCHEMA_ERROR",
                rel_path,
                entry.id,
                f"Unsupported entry kind {entry.kind!r}.",
            )
        )
        return

    if entry.line_ending not in _VALID_EOLS:
        errors.append(
            ValidationIssue(
                "error",
                "SCHEMA_ERROR",
                rel_path,
                entry.id,
                f"Invalid line_ending {entry.line_ending!r}.",
            )
        )

    if entry.line_number < 1:
        errors.append(
            ValidationIssue(
                "error",
                "SCHEMA_ERROR",
                rel_path,
                entry.id,
                f"Invalid line_number {entry.line_number}.",
            )
        )

    if entry.kind == "dialogue":
        if not entry.segments:
            errors.append(
                ValidationIssue(
                    "error",
                    "EMPTY_ENTRY",
                    rel_path,
                    entry.id,
                    "Dialogue entry has 0 segments.",
                )
            )
            return

        if len(entry.markers) != len(entry.segments) + 1:
            errors.append(
                ValidationIssue(
                    "error",
                    "ALTERED_MARKERS",
                    rel_path,
                    entry.id,
                    f"Markers count ({len(entry.markers)}) must equal segments count + 1 ({len(entry.segments) + 1}).",
                )
            )

        for m_idx, marker_group in enumerate(entry.markers):
            if marker_group and not _MARKER_GROUP_RE.match(marker_group):
                errors.append(
                    ValidationIssue(
                        "error",
                        "ALTERED_MARKERS",
                        rel_path,
                        entry.id,
                        f"Malformed bracket marker group at index {m_idx}: {marker_group!r}",
                    )
                )

        for expected_idx, seg in enumerate(entry.segments):
            if seg.index != expected_idx:
                errors.append(
                    ValidationIssue(
                        "error",
                        "INVALID_ENTRY_ORDER",
                        rel_path,
                        entry.id,
                        f"Segment index {seg.index} is out of order (expected {expected_idx}).",
                    )
                )
            if seg.text == "" and not entry.allow_empty:
                errors.append(
                    ValidationIssue(
                        "error",
                        "EMPTY_ENTRY",
                        rel_path,
                        entry.id,
                        f"Dialogue segment {expected_idx} is empty.",
                    )
                )
            if "\x00" in seg.text:
                errors.append(
                    ValidationIssue(
                        "error",
                        "INVALID_SEQUENCE",
                        rel_path,
                        entry.id,
                        f"Dialogue segment {expected_idx} contains forbidden NUL byte.",
                    )
                )
            if "\r" in seg.text or "\n" in seg.text:
                errors.append(
                    ValidationIssue(
                        "error",
                        "INVALID_NEWLINE",
                        rel_path,
                        entry.id,
                        f"Dialogue segment {expected_idx} contains literal newline (use '{{n}}').",
                    )
                )
            if "`" in seg.text:
                if entry.has_stray_backtick:
                    warnings.append(
                        ValidationIssue(
                            "warning",
                            "STRAY_BACKTICK_IN_DIALOGUE",
                            rel_path,
                            entry.id,
                            f"Dialogue segment {expected_idx} contains pre-existing stray backtick.",
                        )
                    )
                else:
                    errors.append(
                        ValidationIssue(
                            "error",
                            "INVALID_SEQUENCE",
                            rel_path,
                            entry.id,
                            f"Dialogue segment {expected_idx} introduces an unescaped backtick (`).",
                        )
                    )
            if _BRACKET_RE.search(seg.text):
                errors.append(
                    ValidationIssue(
                        "error",
                        "ALTERED_MARKERS",
                        rel_path,
                        entry.id,
                        f"Dialogue segment {expected_idx} contains '[' or ']' control brackets inside text.",
                    )
                )

            if seg.inline_tags:
                expected_prefixes = _extract_tag_prefixes(seg.inline_tags)
                actual_prefixes = _extract_tag_prefixes(extract_inline_tags(seg.text))
                if expected_prefixes != actual_prefixes:
                    issue_sev = "error" if strict else "warning"
                    target_list = errors if strict else warnings
                    target_list.append(
                        ValidationIssue(
                            issue_sev,
                            "MISSING_INLINE_TAG",
                            rel_path,
                            entry.id,
                            f"Segment {expected_idx} inline tags changed from {expected_prefixes} to {actual_prefixes}.",
                        )
                    )

            try:
                seg.text.encode("utf-8", errors="strict")
            except UnicodeEncodeError as exc:
                errors.append(
                    ValidationIssue(
                        "error",
                        "ENCODING_ERROR",
                        rel_path,
                        entry.id,
                        f"Segment {expected_idx} contains non-UTF-8 representable character: {exc}",
                    )
                )

        full_dialogue_text = "".join(seg.text for seg in entry.segments)
        brace_err = _check_brace_balance(full_dialogue_text)
        if brace_err:
            if entry.has_unbalanced_braces:
                warnings.append(
                    ValidationIssue(
                        "warning",
                        "UNBALANCED_BRACES_IN_SOURCE",
                        rel_path,
                        entry.id,
                        f"Pre-existing unbalanced braces in dialogue: {brace_err}",
                    )
                )
            else:
                errors.append(
                    ValidationIssue(
                        "error",
                        "MISSING_INLINE_TAG",
                        rel_path,
                        entry.id,
                        brace_err,
                    )
                )
    else:
        if entry.text == "" and not entry.allow_empty:
            errors.append(
                ValidationIssue(
                    "error",
                    "EMPTY_ENTRY",
                    rel_path,
                    entry.id,
                    "Translatable string entry is empty.",
                )
            )
        if "\x00" in entry.text:
            errors.append(
                ValidationIssue(
                    "error",
                    "INVALID_SEQUENCE",
                    rel_path,
                    entry.id,
                    "Entry text contains forbidden NUL byte.",
                )
            )
        if '"' in entry.text:
            if entry.has_stray_backtick:
                warnings.append(
                    ValidationIssue(
                        "warning",
                        "EMBEDDED_QUOTE_IN_STRALIAS",
                        rel_path,
                        entry.id,
                        "Entry contains pre-existing unescaped ASCII double quotes.",
                    )
                )
            else:
                errors.append(
                    ValidationIssue(
                        "error",
                        "INVALID_SEQUENCE",
                        rel_path,
                        entry.id,
                        'Entry text contains unescaped double quote (") which breaks ONScripter string literal.',
                    )
                )
        if ("\r" in entry.text or "\n" in entry.text) and entry.line_span < 2:
            errors.append(
                ValidationIssue(
                    "error",
                    "INVALID_NEWLINE",
                    rel_path,
                    entry.id,
                    "Entry text contains literal newline in single-line command (use '{n}').",
                )
            )

        brace_err = _check_brace_balance(entry.text)
        if brace_err:
            if entry.has_unbalanced_braces:
                warnings.append(
                    ValidationIssue(
                        "warning",
                        "UNBALANCED_BRACES_IN_SOURCE",
                        rel_path,
                        entry.id,
                        f"Pre-existing unbalanced braces in entry: {brace_err}",
                    )
                )
            else:
                errors.append(
                    ValidationIssue(
                        "error",
                        "MISSING_INLINE_TAG",
                        rel_path,
                        entry.id,
                        brace_err,
                    )
                )
        elif entry.inline_tags:
            expected_prefixes = _extract_tag_prefixes(entry.inline_tags)
            actual_prefixes = _extract_tag_prefixes(extract_inline_tags(entry.text))
            if expected_prefixes != actual_prefixes:
                issue_sev = "error" if strict else "warning"
                target_list = errors if strict else warnings
                target_list.append(
                    ValidationIssue(
                        issue_sev,
                        "MISSING_INLINE_TAG",
                        rel_path,
                        entry.id,
                        f"Entry inline tags changed from {expected_prefixes} to {actual_prefixes}.",
                    )
                )

        try:
            entry.text.encode("utf-8", errors="strict")
        except UnicodeEncodeError as exc:
            errors.append(
                ValidationIssue(
                    "error",
                    "ENCODING_ERROR",
                    rel_path,
                    entry.id,
                    f"Entry text contains non-UTF-8 representable character: {exc}",
                )
            )


def validate_workspace(
    translation_dir: Path,
    *,
    strict: bool = False,
) -> ValidationReport:
    """Validate an extracted translation directory and return a `ValidationReport`."""
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []

    if not translation_dir.exists() or not translation_dir.is_dir():
        errors.append(
            ValidationIssue(
                "error",
                "MISSING_DIRECTORY",
                str(translation_dir),
                "",
                "Translation directory does not exist or is not a directory.",
            )
        )
        return ValidationReport(valid=False, errors=errors, warnings=warnings)

    try:
        manifest_path = resolve_safe_output_path(translation_dir, "manifest.json")
    except EsFileSecurityError as exc:
        errors.append(ValidationIssue("error", "SECURITY_ERROR", "manifest.json", "", str(exc)))
        return ValidationReport(valid=False, errors=errors, warnings=warnings)

    if not manifest_path.is_file():
        errors.append(
            ValidationIssue(
                "error",
                "MISSING_MANIFEST",
                "manifest.json",
                "",
                "manifest.json is missing from the translation directory.",
            )
        )
        return ValidationReport(valid=False, errors=errors, warnings=warnings)

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(
            ValidationIssue("error", "SCHEMA_ERROR", "manifest.json", "", f"Invalid JSON: {exc}")
        )
        return ValidationReport(valid=False, errors=errors, warnings=warnings)

    if not isinstance(manifest, dict) or manifest.get("schema_version") != SCHEMA_VERSION:
        errors.append(
            ValidationIssue(
                "error",
                "SCHEMA_ERROR",
                "manifest.json",
                "",
                f"Invalid or unsupported schema_version (expected {SCHEMA_VERSION!r}).",
            )
        )
        return ValidationReport(valid=False, errors=errors, warnings=warnings)

    for req_key in ("container", "script_metadata", "catalog_files", "block_files"):
        if req_key not in manifest:
            errors.append(
                ValidationIssue(
                    "error",
                    "SCHEMA_ERROR",
                    "manifest.json",
                    "",
                    f"Missing required top-level key {req_key!r}.",
                )
            )
    if errors:
        return ValidationReport(valid=False, errors=errors, warnings=warnings)

    container_meta = manifest["container"]
    script_meta = manifest["script_metadata"]
    if not isinstance(container_meta, dict) or container_meta.get("format") != "ONS2":
        errors.append(
            ValidationIssue(
                "error",
                "INCONSISTENT_METADATA",
                "manifest.json",
                "",
                "container.format must be 'ONS2'.",
            )
        )
    if not isinstance(script_meta, dict) or ";gameid UminekoPS3fication" not in str(
        script_meta.get("gameid", "")
    ):
        errors.append(
            ValidationIssue(
                "error",
                "INCONSISTENT_METADATA",
                "manifest.json",
                "",
                "script_metadata.gameid must start with ';gameid UminekoPS3fication'.",
            )
        )

    cat_specs = manifest["catalog_files"]
    blk_specs = manifest["block_files"]
    if not isinstance(cat_specs, list) or not isinstance(blk_specs, list) or not blk_specs:
        errors.append(
            ValidationIssue(
                "error",
                "SCHEMA_ERROR",
                "manifest.json",
                "",
                "catalog_files and block_files must be non-empty lists.",
            )
        )
        return ValidationReport(valid=False, errors=errors, warnings=warnings)

    expected_rel_paths: set[str] = set()
    try:
        all_paths = [str(s.get("path", "")) for s in cat_specs] + [
            str(s.get("path", "")) for s in blk_specs
        ]
        check_case_collisions(all_paths)
        expected_rel_paths.update(all_paths)
    except EsFileSecurityError as exc:
        errors.append(ValidationIssue("error", "SECURITY_ERROR", "manifest.json", "", str(exc)))
        return ValidationReport(valid=False, errors=errors, warnings=warnings)

    # Check for unexpected extra JSON files in story/, strings/, blocks/
    for sub in ("story", "strings", "blocks"):
        sub_dir = translation_dir / sub
        if sub_dir.is_dir():
            for found in sorted(sub_dir.rglob("*.json")):
                rel = found.relative_to(translation_dir).as_posix()
                if rel not in expected_rel_paths:
                    errors.append(
                        ValidationIssue(
                            "error",
                            "UNEXPECTED_EXTRA_FILE",
                            rel,
                            "",
                            f"File {rel} is present on disk but not registered in manifest.json.",
                        )
                    )

    entries_by_id: dict[str, tuple[str, CatalogEntry]] = {}
    catalogs_checked = 0
    entries_checked = 0
    modified_catalogs: list[str] = []

    for spec in cat_specs:
        if not isinstance(spec, dict) or "path" not in spec:
            errors.append(
                ValidationIssue("error", "SCHEMA_ERROR", "manifest.json", "", "Malformed catalog spec.")
            )
            continue
        rel_path = str(spec["path"])
        try:
            cat_file = resolve_safe_output_path(translation_dir, rel_path)
        except EsFileSecurityError as exc:
            errors.append(ValidationIssue("error", "SECURITY_ERROR", rel_path, "", str(exc)))
            continue

        if not cat_file.is_file():
            errors.append(
                ValidationIssue(
                    "error",
                    "MISSING_CATALOG_FILE",
                    rel_path,
                    "",
                    f"Missing catalog file: {rel_path}",
                )
            )
            continue

        cat_bytes = cat_file.read_bytes()
        if sha256_hex(cat_bytes) != spec.get("sha256"):
            modified_catalogs.append(rel_path)

        try:
            raw_cat = json.loads(cat_bytes.decode("utf-8", errors="strict"))
            cat = TranslationCatalog.from_dict(raw_cat)
        except UnicodeDecodeError as exc:
            errors.append(
                ValidationIssue("error", "ENCODING_ERROR", rel_path, "", f"Invalid UTF-8: {exc}")
            )
            continue
        except Exception as exc:
            errors.append(
                ValidationIssue("error", "SCHEMA_ERROR", rel_path, "", f"Invalid catalog schema: {exc}")
            )
            continue

        catalogs_checked += 1
        if cat.rel_path != rel_path:
            errors.append(
                ValidationIssue(
                    "error",
                    "INCONSISTENT_METADATA",
                    rel_path,
                    "",
                    f"Catalog internal rel_path {cat.rel_path!r} != {rel_path!r}.",
                )
            )
        if spec.get("entry_count") is not None and len(cat.entries) != int(spec["entry_count"]):
            errors.append(
                ValidationIssue(
                    "error",
                    "INCONSISTENT_METADATA",
                    rel_path,
                    "",
                    f"Catalog entry count ({len(cat.entries)}) != manifest entry_count ({spec['entry_count']}).",
                )
            )

        prev_line = 0
        for entry in cat.entries:
            entries_checked += 1
            _validate_entry_detailed(entry, rel_path, errors, warnings, strict=strict)
            if entry.id in entries_by_id:
                prev_cat, _ = entries_by_id[entry.id]
                errors.append(
                    ValidationIssue(
                        "error",
                        "DUPLICATE_ENTRY_ID",
                        rel_path,
                        entry.id,
                        f"Duplicate entry ID {entry.id!r} (already defined in {prev_cat}).",
                    )
                )
            else:
                entries_by_id[entry.id] = (rel_path, entry)

            if entry.line_number <= prev_line:
                errors.append(
                    ValidationIssue(
                        "error",
                        "INVALID_ENTRY_ORDER",
                        rel_path,
                        entry.id,
                        f"Entry line_number {entry.line_number} is not strictly increasing (previous: {prev_line}).",
                    )
                )
            prev_line = entry.line_number

    blocks_checked = 0
    seen_slot_ids: set[str] = set()
    global_prev_line = 0

    for spec in blk_specs:
        if not isinstance(spec, dict) or "path" not in spec:
            errors.append(
                ValidationIssue("error", "SCHEMA_ERROR", "manifest.json", "", "Malformed block spec.")
            )
            continue
        rel_path = str(spec["path"])
        try:
            blk_file = resolve_safe_output_path(translation_dir, rel_path)
        except EsFileSecurityError as exc:
            errors.append(ValidationIssue("error", "SECURITY_ERROR", rel_path, "", str(exc)))
            continue

        if not blk_file.is_file():
            errors.append(
                ValidationIssue(
                    "error",
                    "MISSING_BLOCK_FILE",
                    rel_path,
                    "",
                    f"Missing structural block file: {rel_path}",
                )
            )
            continue

        blk_bytes = blk_file.read_bytes()
        if spec.get("sha256") and sha256_hex(blk_bytes) != spec.get("sha256"):
            errors.append(
                ValidationIssue(
                    "error",
                    "CHECKSUM_MISMATCH",
                    rel_path,
                    "",
                    f"Structural block file {rel_path} checksum mismatch against manifest.json.",
                )
            )

        try:
            raw_blk = json.loads(blk_bytes.decode("utf-8", errors="strict"))
            blk = StructuralBlock.from_dict(raw_blk)
        except Exception as exc:
            errors.append(
                ValidationIssue("error", "SCHEMA_ERROR", rel_path, "", f"Invalid block schema: {exc}")
            )
            continue

        blocks_checked += 1
        for rec in blk.records:
            kind = rec.get("kind")
            if kind == "raw":
                start_line = int(rec.get("start_line", 0))
                if start_line < global_prev_line:
                    errors.append(
                        ValidationIssue(
                            "error",
                            "INVALID_ENTRY_ORDER",
                            rel_path,
                            "",
                            f"Raw chunk start_line {start_line} is out of global order (< {global_prev_line}).",
                        )
                    )
                global_prev_line = int(rec.get("end_line", start_line))
            elif kind == "entry":
                slot_id = str(rec.get("id", ""))
                slot_cat = str(rec.get("catalog", ""))
                slot_line = int(rec.get("line_number", 0))
                if slot_id not in entries_by_id:
                    errors.append(
                        ValidationIssue(
                            "error",
                            "UNKNOWN_ENTRY_ID",
                            rel_path,
                            slot_id,
                            f"Block slot references unknown entry ID {slot_id!r}.",
                        )
                    )
                else:
                    actual_cat, _ = entries_by_id[slot_id]
                    if actual_cat != slot_cat:
                        errors.append(
                            ValidationIssue(
                                "error",
                                "BROKEN_REFERENCE",
                                rel_path,
                                slot_id,
                                f"Block slot expects catalog {slot_cat!r}, but entry is in {actual_cat!r}.",
                            )
                        )
                if slot_id in seen_slot_ids:
                    errors.append(
                        ValidationIssue(
                            "error",
                            "DUPLICATE_ENTRY_ID",
                            rel_path,
                            slot_id,
                            f"Block slot references entry ID {slot_id!r} multiple times.",
                        )
                    )
                seen_slot_ids.add(slot_id)
                if slot_line < global_prev_line:
                    errors.append(
                        ValidationIssue(
                            "error",
                            "INVALID_ENTRY_ORDER",
                            rel_path,
                            slot_id,
                            f"Entry slot at line {slot_line} is out of global order (< {global_prev_line}).",
                        )
                    )
                global_prev_line = slot_line
            else:
                errors.append(
                    ValidationIssue(
                        "error",
                        "SCHEMA_ERROR",
                        rel_path,
                        "",
                        f"Unsupported block record kind {kind!r}.",
                    )
                )

    for entry_id, (cat_rel, _entry) in entries_by_id.items():
        if entry_id not in seen_slot_ids:
            errors.append(
                ValidationIssue(
                    "error",
                    "ORPHANED_ENTRY_ID",
                    cat_rel,
                    entry_id,
                    f"Entry {entry_id!r} in {cat_rel} has no slot in structural blocks.",
                )
            )

    expected_total = script_meta.get("total_entries")
    if expected_total is not None and entries_checked != int(expected_total):
        errors.append(
            ValidationIssue(
                "error",
                "INCONSISTENT_METADATA",
                "manifest.json",
                "",
                f"Total entries in catalogs ({entries_checked}) != manifest script_metadata.total_entries ({expected_total}).",
            )
        )

    return ValidationReport(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        catalogs_checked=catalogs_checked,
        blocks_checked=blocks_checked,
        entries_checked=entries_checked,
        modified_catalogs=modified_catalogs,
    )
