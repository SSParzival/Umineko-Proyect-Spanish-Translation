"""Recursive scanning of translation catalogs for linguistic issues and discrepancies."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from tools.translation_lint.models import Finding, LintReport
from tools.translation_lint.rules import (
    COMPILED_WORD_RULES,
    HUMAN_REVIEW_FINDINGS,
    TARGETED_BY_ENTRY_ID,
    apply_outside_tags,
    load_accepted_words,
)

SPACE_BEFORE_PUNCT_RE = re.compile(r"([A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9])\s+([,;:.])")


def scan_entry_text(
    rel_file: str,
    entry: dict[str, Any],
    field_path: str,
    text: str,
    accepted_words: set[str],
) -> list[Finding]:
    """Scan a single translatable text field and return all detected findings."""
    findings: list[Finding] = []
    eid = str(entry.get("id", ""))
    speaker = str(entry.get("speaker", ""))

    cur_text = text

    # 1. Check targeted entry rules
    if eid in TARGETED_BY_ENTRY_ID:
        for s_from, s_to, cat, reason in TARGETED_BY_ENTRY_ID[eid]:
            if s_from in cur_text:
                new_text = apply_outside_tags(
                    cur_text, lambda seg, sf=s_from, st=s_to: seg.replace(sf, st)
                )
                if new_text != cur_text:
                    findings.append(
                        Finding(
                            file_path=rel_file,
                            entry_id=eid,
                            speaker=speaker,
                            field_path=field_path,
                            category=cat,
                            confidence="ALTA",
                            before=s_from,
                            after=s_to,
                            rule_or_reason=reason,
                            applied=False,
                            context_preview=cur_text[:120],
                        )
                    )
                    cur_text = new_text

    # 2. Check global word rules
    for rx, w_from, w_to, cat, reason in COMPILED_WORD_RULES:
        if rx.search(cur_text):
            new_text = apply_outside_tags(cur_text, lambda seg, r=rx, wt=w_to: r.sub(wt, seg))
            if new_text != cur_text:
                findings.append(
                    Finding(
                        file_path=rel_file,
                        entry_id=eid,
                        speaker=speaker,
                        field_path=field_path,
                        category=cat,
                        confidence="ALTA",
                        before=w_from,
                        after=w_to,
                        rule_or_reason=reason,
                        applied=False,
                        context_preview=cur_text[:120],
                    )
                )
                cur_text = new_text

    return findings


def scan_workspace(
    target_path: Path,
    *,
    accepted_words_file: Path | None = None,
) -> LintReport:
    """Scan translation catalogs under `target_path` and produce a LintReport."""
    accepted = load_accepted_words(accepted_words_file)
    report = LintReport()

    if target_path.is_file() and target_path.suffix == ".json":
        json_files = [target_path]
        base_dir = target_path.parent
    else:
        base_dir = target_path
        # Exclude blocks/, schemas/, raw/, manifest.json, report.json
        json_files = sorted(
            p
            for p in base_dir.rglob("*.json")
            if "blocks" not in p.parts
            and "schemas" not in p.parts
            and "raw" not in p.parts
            and p.name not in ("manifest.json", "report.json")
        )

    report.total_files_checked = len(json_files)

    # Add registered human review candidates
    for item in HUMAN_REVIEW_FINDINGS:
        report.findings.append(Finding.from_dict(item))

    for p in json_files:
        rel = p.relative_to(base_dir).as_posix()
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue

        entries = data.get("entries", [])
        report.total_entries_checked += len(entries)

        for entry in entries:
            kind = entry.get("kind", "")
            if kind == "dialogue":
                segments = entry.get("segments", [])
                for seg in segments:
                    seg_idx = seg.get("index", 0)
                    seg_text = seg.get("text", "")
                    field_p = f"segments[{seg_idx}].text"
                    found = scan_entry_text(rel, entry, field_p, seg_text, accepted)
                    report.findings.extend(found)
            elif kind in ("stralias", "bgm_title", "credits_line", "window_caption"):
                text_val = entry.get("text", "")
                found = scan_entry_text(rel, entry, "text", text_val, accepted)
                report.findings.extend(found)

    report.total_findings = len(report.findings)
    return report
