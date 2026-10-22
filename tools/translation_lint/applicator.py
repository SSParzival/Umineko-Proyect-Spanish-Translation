"""Application of high-confidence Spanish proofreading corrections to translation catalogs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.esfile.codec import sha256_hex
from tools.esfile.models import extract_inline_tags
from tools.translation_lint.models import Finding
from tools.translation_lint.rules import (
    COMPILED_WORD_RULES,
    TARGETED_BY_ENTRY_ID,
    apply_outside_tags,
)


def _serialize_deterministic(data: dict[str, Any]) -> bytes:
    """Serialize JSON with 2-space indentation, no ASCII escaping, and final LF newline."""
    return (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def apply_corrections_to_entry(
    rel_path: str,
    entry: dict[str, Any],
) -> list[Finding]:
    """Apply high-confidence linguistic rules to a catalog entry and return applied findings."""
    applied_findings: list[Finding] = []
    eid = str(entry.get("id", ""))
    speaker = str(entry.get("speaker", ""))
    kind = str(entry.get("kind", ""))

    def transform_text(field_name: str, cur_text: str) -> str:
        new_text = cur_text
        # 1. Targeted entry rules
        if eid in TARGETED_BY_ENTRY_ID:
            for s_from, s_to, cat, reason in TARGETED_BY_ENTRY_ID[eid]:
                if s_from in new_text:
                    transformed = apply_outside_tags(
                        new_text, lambda seg, sf=s_from, st=s_to: seg.replace(sf, st)
                    )
                    if transformed != new_text:
                        applied_findings.append(
                            Finding(
                                file_path=rel_path,
                                entry_id=eid,
                                speaker=speaker,
                                field_path=field_name,
                                category=cat,
                                confidence="ALTA",
                                before=s_from,
                                after=s_to,
                                rule_or_reason=reason,
                                applied=True,
                                context_preview=transformed[:120],
                            )
                        )
                        new_text = transformed

        # 2. Global word rules
        for rx, w_from, w_to, cat, reason in COMPILED_WORD_RULES:
            if rx.search(new_text):
                transformed = apply_outside_tags(
                    new_text, lambda seg, r=rx, wt=w_to: r.sub(wt, seg)
                )
                if transformed != new_text:
                    applied_findings.append(
                        Finding(
                            file_path=rel_path,
                            entry_id=eid,
                            speaker=speaker,
                            field_path=field_name,
                            category=cat,
                            confidence="ALTA",
                            before=w_from,
                            after=w_to,
                            rule_or_reason=reason,
                            applied=True,
                            context_preview=transformed[:120],
                        )
                    )
                    new_text = transformed
        return new_text

    if kind == "dialogue":
        segments = entry.get("segments", [])
        entry_modified = False
        for seg in segments:
            idx = seg.get("index", 0)
            orig_text = seg.get("text", "")
            field_name = f"segments[{idx}].text"
            fixed_text = transform_text(field_name, orig_text)
            if fixed_text != orig_text:
                seg["text"] = fixed_text
                seg["inline_tags"] = extract_inline_tags(fixed_text)
                entry_modified = True

        if entry_modified:
            entry["text"] = " ".join(s["text"] for s in segments)
            entry["inline_tags"] = [t for s in segments for t in s.get("inline_tags", [])]
    elif kind in ("stralias", "bgm_title", "credits_line", "window_caption"):
        orig_text = entry.get("text", "")
        fixed_text = transform_text("text", orig_text)
        if fixed_text != orig_text:
            entry["text"] = fixed_text
            entry["inline_tags"] = extract_inline_tags(fixed_text)

    return applied_findings


def apply_corrections_workspace(
    target_path: Path,
    *,
    dry_run: bool = False,
    update_manifest: bool = True,
) -> tuple[list[Finding], list[str]]:
    """Apply high-confidence corrections to all catalogs under `target_path`."""
    if target_path.is_file() and target_path.suffix == ".json":
        json_files = [target_path]
        base_dir = target_path.parent
    else:
        base_dir = target_path
        json_files = sorted(
            p
            for p in base_dir.rglob("*.json")
            if "blocks" not in p.parts
            and "schemas" not in p.parts
            and "raw" not in p.parts
            and p.name not in ("manifest.json", "report.json")
        )

    all_applied_findings: list[Finding] = []
    modified_catalogs: list[str] = []
    updated_catalog_hashes: dict[str, str] = {}

    for p in json_files:
        rel_path = p.relative_to(base_dir).as_posix()
        try:
            content = p.read_text(encoding="utf-8")
            data = json.loads(content)
        except Exception:
            continue

        entries = data.get("entries", [])
        file_findings: list[Finding] = []

        for entry in entries:
            findings = apply_corrections_to_entry(rel_path, entry)
            file_findings.extend(findings)

        if file_findings:
            modified_catalogs.append(rel_path)
            all_applied_findings.extend(file_findings)
            serialized_bytes = _serialize_deterministic(data)
            updated_catalog_hashes[rel_path] = sha256_hex(serialized_bytes)
            if not dry_run:
                p.write_bytes(serialized_bytes)

    # Update manifest.json if requested and not in dry_run
    manifest_path = base_dir / "manifest.json"
    if update_manifest and manifest_path.exists() and not dry_run and updated_catalog_hashes:
        try:
            manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
            for cat_info in manifest_data.get("catalogs", []):
                cat_rel = cat_info.get("path")
                if cat_rel in updated_catalog_hashes:
                    cat_info["sha256"] = updated_catalog_hashes[cat_rel]
            manifest_path.write_bytes(_serialize_deterministic(manifest_data))
        except Exception:
            pass

    return all_applied_findings, modified_catalogs
