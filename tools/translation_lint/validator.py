"""Validation and regression check suite for translated and edited catalogs."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tools.esfile.models import extract_inline_tags
from tools.translation_lint.rules import COMPILED_WORD_RULES, TARGETED_BY_ENTRY_ID, apply_outside_tags


@dataclass
class LintValidationIssue:
    """A single issue found during post-editing validation."""

    severity: str  # "error" | "warning"
    location: str
    entry_id: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "location": self.location,
            "entry_id": self.entry_id,
            "message": self.message,
        }


@dataclass
class LintValidationReport:
    """Complete validation report for a translation workspace."""

    valid: bool
    errors: list[LintValidationIssue] = field(default_factory=list)
    warnings: list[LintValidationIssue] = field(default_factory=list)
    files_checked: int = 0
    entries_checked: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "files_checked": self.files_checked,
            "entries_checked": self.entries_checked,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
        }


def validate_workspace_lint(target_path: Path) -> LintValidationReport:
    """Validate all translation catalogs in `target_path` for structural and linguistic integrity."""
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

    errors: list[LintValidationIssue] = []
    warnings: list[LintValidationIssue] = []
    total_entries = 0

    for p in json_files:
        rel = p.relative_to(base_dir).as_posix()
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(
                LintValidationIssue("error", rel, "", f"Invalid JSON syntax: {exc}")
            )
            continue

        entries = data.get("entries", [])
        total_entries += len(entries)

        for entry in entries:
            eid = str(entry.get("id", ""))
            kind = str(entry.get("kind", ""))

            # Validate basic entry fields
            if not eid:
                errors.append(LintValidationIssue("error", rel, "", "Entry missing 'id'."))
            if not kind:
                errors.append(LintValidationIssue("error", rel, eid, "Entry missing 'kind'."))

            if kind == "dialogue":
                segments = entry.get("segments", [])
                for seg in segments:
                    s_idx = seg.get("index", 0)
                    s_text = seg.get("text", "")
                    s_tags = seg.get("inline_tags", [])
                    actual_tags = extract_inline_tags(s_text)
                    if s_tags != actual_tags:
                        errors.append(
                            LintValidationIssue(
                                "error",
                                rel,
                                eid,
                                f"Segment {s_idx} inline_tags {s_tags!r} do not match text tags {actual_tags!r}.",
                            )
                        )
                    # Check for residual known typos
                    for rx, w_from, _w_to, _cat, _reason in COMPILED_WORD_RULES:
                        # Check outside tags
                        found_residual = False
                        def check_res(s: str) -> str:
                            nonlocal found_residual
                            if rx.search(s):
                                found_residual = True
                            return s
                        apply_outside_tags(s_text, check_res)
                        if found_residual:
                            warnings.append(
                                LintValidationIssue(
                                    "warning",
                                    rel,
                                    eid,
                                    f"Residual uncorrected pattern '{w_from}' found in segment {s_idx}.",
                                )
                            )
            elif kind in ("stralias", "bgm_title", "credits_line", "window_caption"):
                e_text = entry.get("text", "")
                e_tags = entry.get("inline_tags", [])
                actual_tags = extract_inline_tags(e_text)
                if e_tags != actual_tags:
                    errors.append(
                        LintValidationIssue(
                            "error",
                            rel,
                            eid,
                            f"Entry inline_tags {e_tags!r} do not match text tags {actual_tags!r}.",
                        )
                    )

    is_valid = len(errors) == 0
    return LintValidationReport(
        valid=is_valid,
        errors=errors,
        warnings=warnings,
        files_checked=len(json_files),
        entries_checked=total_entries,
    )
