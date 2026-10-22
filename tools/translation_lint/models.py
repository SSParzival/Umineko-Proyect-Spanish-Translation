"""Data models for translation linting, findings, and correction reporting."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tools.translation_lint import CATEGORIES, CONFIDENCE_LEVELS, __version__


@dataclass
class Finding:
    """A linguistic or structural issue identified in a translation entry."""

    file_path: str
    entry_id: str
    speaker: str
    field_path: str  # e.g. "segments[0].text" or "text"
    category: str
    confidence: str  # "ALTA" | "MEDIA" | "BAJA"
    before: str
    after: str
    rule_or_reason: str
    applied: bool = False
    context_preview: str = ""

    def __post_init__(self) -> None:
        if self.category not in CATEGORIES:
            raise ValueError(f"Invalid finding category: {self.category!r}")
        if self.confidence not in CONFIDENCE_LEVELS:
            raise ValueError(f"Invalid finding confidence: {self.confidence!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "file": self.file_path,
            "entry_id": self.entry_id,
            "speaker": self.speaker,
            "field_path": self.field_path,
            "category": self.category,
            "confidence": self.confidence,
            "before": self.before,
            "after": self.after,
            "rule_or_reason": self.rule_or_reason,
            "applied": self.applied,
            "context_preview": self.context_preview,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Finding:
        return cls(
            file_path=str(data["file"]),
            entry_id=str(data["entry_id"]),
            speaker=str(data.get("speaker", "")),
            field_path=str(data.get("field_path", "text")),
            category=str(data["category"]),
            confidence=str(data["confidence"]),
            before=str(data["before"]),
            after=str(data["after"]),
            rule_or_reason=str(data["rule_or_reason"]),
            applied=bool(data.get("applied", False)),
            context_preview=str(data.get("context_preview", "")),
        )


@dataclass
class LintReport:
    """Aggregated linting report containing all findings and summary statistics."""

    tool_version: str = __version__
    total_files_checked: int = 0
    total_entries_checked: int = 0
    total_findings: int = 0
    findings: list[Finding] = field(default_factory=list)

    def count_by_category(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for f in self.findings:
            counts[f.category] = counts.get(f.category, 0) + 1
        return counts

    def count_by_confidence(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for f in self.findings:
            counts[f.confidence] = counts.get(f.confidence, 0) + 1
        return counts

    def count_applied(self) -> int:
        return sum(1 for f in self.findings if f.applied)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_version": self.tool_version,
            "summary": {
                "total_files_checked": self.total_files_checked,
                "total_entries_checked": self.total_entries_checked,
                "total_findings": len(self.findings),
                "total_applied": self.count_applied(),
                "by_category": self.count_by_category(),
                "by_confidence": self.count_by_confidence(),
            },
            "findings": [f.to_dict() for f in self.findings],
        }
