"""Semantic and binary comparator (`diff`) for ONS2 (.file) archives and extracted workspaces."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tools.esfile.builder import load_and_validate_workspace
from tools.esfile.codec import EsFileError, decode_ons2, sha256_hex
from tools.esfile.models import CatalogEntry, StructuralBlock
from tools.esfile.parser import parse_script


@dataclass
class _LoadedTarget:
    """Normalized representation of either an ONS2 file or an extracted directory."""

    label: str
    kind: str  # "file" | "directory"
    file_size: int | None
    file_sha256: str | None
    zlib_sha256: str | None
    plaintext_sha256: str
    metadata: dict[str, Any]
    entries_ordered: list[tuple[str, str, CatalogEntry]]  # (entry_id, catalog_rel_path, entry)
    blocks: list[StructuralBlock]


def _entry_editable_value(entry: CatalogEntry) -> str | list[str]:
    if entry.kind == "dialogue":
        return [seg.text for seg in entry.segments]
    return entry.text


def _load_target(path: Path) -> _LoadedTarget:
    if not path.exists():
        raise EsFileError(f"Diff target does not exist: {path}")

    if path.is_file():
        raw_bytes = path.read_bytes()
        container = decode_ons2(raw_bytes, strict=True, verify_gameid=True)
        pt_str = container.plaintext_bytes.decode("utf-8", errors="strict")
        parsed = parse_script(pt_str)

        cat_by_entry_id: dict[str, tuple[str, CatalogEntry]] = {}
        for rel_path, cat in parsed.catalogs.items():
            for entry in cat.entries:
                cat_by_entry_id[entry.id] = (rel_path, entry)

        ordered: list[tuple[str, str, CatalogEntry]] = []
        for blk in parsed.blocks:
            for rec in blk.records:
                if rec["kind"] == "entry":
                    eid = str(rec["id"])
                    rel_cat, ent = cat_by_entry_id[eid]
                    ordered.append((eid, rel_cat, ent))

        meta = {
            "mode_directive": parsed.metadata.mode_directive,
            "gameid": parsed.metadata.gameid_directive,
            "version": parsed.metadata.chiru_mode_version,
            "releasedate": parsed.metadata.releasedate or 0,
            "localisation": parsed.metadata.localisation,
            "total_lines": parsed.metadata.total_physical_lines,
            "total_entries": len(ordered),
        }
        return _LoadedTarget(
            label=path.name,
            kind="file",
            file_size=container.file_size,
            file_sha256=container.file_sha256,
            zlib_sha256=container.zlib_stream_sha256,
            plaintext_sha256=container.plaintext_sha256,
            metadata=meta,
            entries_ordered=ordered,
            blocks=parsed.blocks,
        )

    if path.is_dir():
        manifest, catalogs, blocks, entries_by_id = load_and_validate_workspace(
            path, strict=False
        )
        cat_map: dict[str, str] = {}
        for rel_path, cat in catalogs.items():
            for ent in cat.entries:
                cat_map[ent.id] = rel_path

        ordered = []
        script_chunks: list[str] = []
        for blk in blocks:
            for rec in blk.records:
                if rec["kind"] == "raw":
                    script_chunks.append(str(rec["text"]))
                else:
                    eid = str(rec["id"])
                    ent = entries_by_id[eid]
                    ordered.append((eid, cat_map[eid], ent))
                    script_chunks.append(ent.reconstruct_script_line())

        pt_bytes = "".join(script_chunks).encode("utf-8", errors="strict")
        sm = manifest["script_metadata"]
        meta = {
            "mode_directive": str(sm.get("mode_directive", "")),
            "gameid": str(sm.get("gameid", "")),
            "version": str(sm.get("version", "")),
            "releasedate": int(sm.get("releasedate", 0)),
            "localisation": str(sm.get("localisation", "")),
            "total_lines": int(sm.get("total_lines", 0)),
            "total_entries": len(ordered),
        }
        return _LoadedTarget(
            label=path.name,
            kind="directory",
            file_size=None,
            file_sha256=None,
            zlib_sha256=None,
            plaintext_sha256=sha256_hex(pt_bytes),
            metadata=meta,
            entries_ordered=ordered,
            blocks=blocks,
        )

    raise EsFileError(f"Unsupported diff target path: {path}")


def diff_targets(path_a: Path, path_b: Path, *, report_path: Path | None = None) -> dict[str, Any]:
    """Compare two ONS2 files or extracted translation directories semantically and binarily."""
    target_a = _load_target(path_a)
    target_b = _load_target(path_b)

    ids_a = [eid for eid, _, _ in target_a.entries_ordered]
    ids_b = [eid for eid, _, _ in target_b.entries_ordered]
    set_a = set(ids_a)
    set_b = set(ids_b)

    added_entries = [eid for eid in ids_b if eid not in set_a]
    removed_entries = [eid for eid in ids_a if eid not in set_b]

    common_a = [eid for eid in ids_a if eid in set_b]
    common_b = [eid for eid in ids_b if eid in set_a]
    altered_order = common_a != common_b

    map_a = {eid: (cat, ent) for eid, cat, ent in target_a.entries_ordered}
    map_b = {eid: (cat, ent) for eid, cat, ent in target_b.entries_ordered}

    modified_entries: list[dict[str, Any]] = []
    altered_markers: list[str] = []

    for eid in common_a:
        cat_a, ent_a = map_a[eid]
        cat_b, ent_b = map_b[eid]
        val_a = _entry_editable_value(ent_a)
        val_b = _entry_editable_value(ent_b)
        markers_diff = ent_a.markers != ent_b.markers
        prefix_diff = (
            ent_a.command_prefix != ent_b.command_prefix
            or ent_a.command_suffix != ent_b.command_suffix
            or ent_a.sprite_prefix != ent_b.sprite_prefix
        )
        if markers_diff or prefix_diff:
            altered_markers.append(eid)

        if val_a != val_b or markers_diff or prefix_diff:
            modified_entries.append(
                {
                    "id": eid,
                    "catalog": cat_b,
                    "line_number": ent_b.line_number,
                    "before": val_a,
                    "after": val_b,
                    "markers_altered": markers_diff or prefix_diff,
                }
            )

    modified_metadata: dict[str, dict[str, Any]] = {}
    for k in sorted(set(target_a.metadata.keys()) | set(target_b.metadata.keys())):
        va = target_a.metadata.get(k)
        vb = target_b.metadata.get(k)
        if va != vb:
            modified_metadata[k] = {"before": va, "after": vb}

    # Compare structural non-editable raw chunks per block
    blocks_a = {
        blk.block_id: "".join(r["text"] for r in blk.records if r["kind"] == "raw")
        for blk in target_a.blocks
    }
    blocks_b = {
        blk.block_id: "".join(r["text"] for r in blk.records if r["kind"] == "raw")
        for blk in target_b.blocks
    }
    altered_structural_blocks: list[str] = []
    for bid in sorted(set(blocks_a.keys()) | set(blocks_b.keys())):
        if blocks_a.get(bid) != blocks_b.get(bid):
            altered_structural_blocks.append(bid)

    plaintext_identical = target_a.plaintext_sha256 == target_b.plaintext_sha256
    binary_identical: bool | None = None
    expected_binary_differences: list[str] = []
    unexpected_binary_differences: list[str] = []

    if target_a.file_sha256 is not None and target_b.file_sha256 is not None:
        binary_identical = target_a.file_sha256 == target_b.file_sha256
        if not binary_identical:
            if not plaintext_identical:
                expected_binary_differences.append(
                    "Compressed payload, sizes, and ZLIB Adler-32 differ because script plaintext was modified."
                )
            else:
                unexpected_binary_differences.append(
                    "Plaintext is identical, but ZLIB deflate stream differs (e.g. different ZLIB memLevel/implementation)."
                )

    semantically_identical = (
        not added_entries
        and not removed_entries
        and not modified_entries
        and not modified_metadata
        and not altered_markers
        and not altered_order
        and not altered_structural_blocks
    )

    result: dict[str, Any] = {
        "target_a": {
            "label": target_a.label,
            "kind": target_a.kind,
            "file_size": target_a.file_size,
            "file_sha256": target_a.file_sha256,
            "plaintext_sha256": target_a.plaintext_sha256,
        },
        "target_b": {
            "label": target_b.label,
            "kind": target_b.kind,
            "file_size": target_b.file_size,
            "file_sha256": target_b.file_sha256,
            "plaintext_sha256": target_b.plaintext_sha256,
        },
        "summary": {
            "binary_identical": binary_identical,
            "plaintext_identical": plaintext_identical,
            "semantically_identical": semantically_identical,
            "added_count": len(added_entries),
            "removed_count": len(removed_entries),
            "modified_count": len(modified_entries),
            "metadata_changes_count": len(modified_metadata),
            "altered_markers_count": len(altered_markers),
            "altered_order": altered_order,
            "altered_structural_blocks_count": len(altered_structural_blocks),
        },
        "added_entries": added_entries,
        "removed_entries": removed_entries,
        "modified_entries": modified_entries,
        "modified_metadata": modified_metadata,
        "altered_markers": altered_markers,
        "altered_order": altered_order,
        "altered_structural_blocks": altered_structural_blocks,
        "expected_binary_differences": expected_binary_differences,
        "unexpected_binary_differences": unexpected_binary_differences,
    }

    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_bytes = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        report_path.write_bytes(report_bytes)

    return result


def format_diff_report(diff_data: dict[str, Any], *, verbose: bool = False) -> str:
    """Format a `diff_targets` dictionary into a readable CLI report."""
    ta = diff_data["target_a"]
    tb = diff_data["target_b"]
    s = diff_data["summary"]

    lines = [
        f"=== ONS2 / Translation Diff: {ta['label']} vs {tb['label']} ===",
        f"Plaintext Identical   : {s['plaintext_identical']}",
        f"Semantically Identical: {s['semantically_identical']}",
    ]
    if s["binary_identical"] is not None:
        lines.insert(1, f"Binary Identical      : {s['binary_identical']}")

    lines.extend(
        [
            "",
            "--- Semantic Change Counts ---",
            f"Added Entries             : {s['added_count']}",
            f"Removed Entries           : {s['removed_count']}",
            f"Modified Entries          : {s['modified_count']}",
            f"Modified Metadata Fields  : {s['metadata_changes_count']}",
            f"Altered Command Markers   : {s['altered_markers_count']}",
            f"Altered Entry Order       : {s['altered_order']}",
            f"Altered Structural Blocks : {s['altered_structural_blocks_count']}",
        ]
    )

    if diff_data["expected_binary_differences"]:
        lines.append("")
        lines.append("--- Expected Binary Differences ---")
        for msg in diff_data["expected_binary_differences"]:
            lines.append(f"  * {msg}")

    if diff_data["unexpected_binary_differences"]:
        lines.append("")
        lines.append("--- Unexpected Binary Differences ---")
        for msg in diff_data["unexpected_binary_differences"]:
            lines.append(f"  ! {msg}")

    if diff_data["modified_entries"]:
        lines.append("")
        limit = len(diff_data["modified_entries"]) if verbose else min(10, len(diff_data["modified_entries"]))
        lines.append(f"--- Modified Entries (showing {limit} of {len(diff_data['modified_entries'])}) ---")
        for item in diff_data["modified_entries"][:limit]:
            lines.append(f"  * [{item['catalog']}:L{item['line_number']}] {item['id']}")
            lines.append(f"      - before: {item['before']!r}")
            lines.append(f"      + after : {item['after']!r}")

    return "\n".join(lines)
