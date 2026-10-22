#!/usr/bin/env python3
"""Double space normalizer and auditor for Spanish translation catalogs.

Collapses unnecessary double spaces (leading, trailing, sentence spacing, and internal)
outside markup tags while strictly preserving intentional artistic formatting and puzzle blocks
(such as Beatrice's broken puzzle phone call in Episode 7).
"""
from __future__ import annotations

import json
import re
import hashlib
from pathlib import Path
from typing import Any

TAG_RE = re.compile(r"\{[^{}]*\}")

# Entries with intentional artistic spacing / puzzle design that MUST be preserved:
PROTECTED_ENTRIES = {
    "ep7.umi7_2.d51163",  # Beatrice ghost call: spaced letters "Yo... no  p u e d o  llamarlo..."
    "ep7.umi7_2.d51165",  # Beatrice ghost call: spaced letters "Si  us ted  ins iste..."
    "ep7.umi7_2.d51167",  # Silence / pause represented by 60 spaces: '"                 ."'
}


def normalize_spacing(text: str) -> str:
    """Normalize double spaces in a single string outside tags."""
    if "  " not in text:
        return text

    new_text = text

    # 1. Normalize leading double spaces (segment continuation with 2 spaces instead of 1)
    if new_text.startswith("  "):
        new_text = " " + new_text[2:]

    # 2. Normalize trailing double spaces
    if new_text.endswith("  "):
        new_text = new_text.rstrip(" ")

    # 3. Collapse internal multiple spaces outside tags
    parts = TAG_RE.split(new_text)
    tags = TAG_RE.findall(new_text)
    new_parts = [re.sub(r" {2,}", " ", part) for part in parts]

    reassembled: list[str] = []
    for i, np in enumerate(new_parts):
        reassembled.append(np)
        if i < len(tags):
            reassembled.append(tags[i])
    return "".join(reassembled)


def apply_double_space_normalization(
    translation_dir: Path, dry_run: bool = False
) -> list[dict[str, Any]]:
    """Scan and normalize all editable catalogs in translation_dir."""
    changes: list[dict[str, Any]] = []
    modified_files: set[Path] = set()

    for p in sorted(translation_dir.rglob("*.json")):
        if (
            "blocks" in p.parts
            or "schemas" in p.parts
            or "raw" in p.parts
            or "config" in p.parts
            or p.name in ("manifest.json", "report.json")
        ):
            continue

        rel_path = p.relative_to(translation_dir).as_posix()
        data = json.loads(p.read_text(encoding="utf-8"))
        file_modified = False

        for entry in data.get("entries", []):
            eid = entry.get("id", "")
            if eid in PROTECTED_ENTRIES:
                continue

            kind = entry.get("kind", "")
            if kind == "dialogue":
                entry_modified = False
                for seg in entry.get("segments", []):
                    old_text = seg.get("text", "")
                    if "  " in old_text:
                        new_text = normalize_spacing(old_text)
                        if new_text != old_text:
                            seg["text"] = new_text
                            seg["inline_tags"] = TAG_RE.findall(new_text)
                            entry_modified = True
                            file_modified = True
                            changes.append({
                                "file": rel_path,
                                "entry_id": eid,
                                "segment_index": seg.get("index"),
                                "before": old_text,
                                "after": new_text,
                            })
                if entry_modified:
                    entry["text"] = " ".join(s["text"] for s in entry["segments"])
                    entry["inline_tags"] = [
                        tag for s in entry["segments"] for tag in s["inline_tags"]
                    ]
            else:
                old_text = entry.get("text", "")
                if "  " in old_text:
                    new_text = normalize_spacing(old_text)
                    if new_text != old_text:
                        entry["text"] = new_text
                        entry["inline_tags"] = TAG_RE.findall(new_text)
                        file_modified = True
                        changes.append({
                            "file": rel_path,
                            "entry_id": eid,
                            "segment_index": None,
                            "before": old_text,
                            "after": new_text,
                        })

        if file_modified and not dry_run:
            p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            modified_files.add(p)

    if not dry_run and modified_files:
        manifest_path = translation_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for cat_entry in manifest.get("catalog_files", []):
            cat_rel = cat_entry["path"]
            cat_file = translation_dir / cat_rel
            if cat_file.resolve() in {mf.resolve() for mf in modified_files}:
                content = cat_file.read_bytes()
                cat_entry["sha256"] = hashlib.sha256(content).hexdigest()
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    return changes


if __name__ == "__main__":
    import sys

    root = Path(__file__).resolve().parent.parent.parent / "translation"
    dry = "--dry-run" in sys.argv
    res = apply_double_space_normalization(root, dry_run=dry)
    print(f"Applied {len(res)} double space normalizations across translation catalogs (dry_run={dry}).")
