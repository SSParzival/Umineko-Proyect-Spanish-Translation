"""Data structures for extracted ONS2 translation catalogs, entries, and structural blocks."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

INLINE_TAG_RE = re.compile(r"\{[^{}]*\}")
VOICE_TAG_RE = re.compile(r'\[lv\s+\d+\*"([^"]+)"\*"([^"]+)"\]')


def extract_inline_tags(text: str) -> list[str]:
    """Return all `{...}` inline formatting tags in order of appearance."""
    return INLINE_TAG_RE.findall(text)


def extract_voice_files(markers: list[str]) -> list[str]:
    """Extract `folder/clip_id` voice references from `[lv ...]` markers."""
    voices: list[str] = []
    for marker_group in markers:
        for folder, clip in VOICE_TAG_RE.findall(marker_group):
            voices.append(f"{folder}/{clip}")
    return voices


@dataclass
class EditableSegment:
    """A single backtick-delimited translatable text segment inside a `d` or `d2` line."""

    index: int
    text: str
    inline_tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "text": self.text,
            "inline_tags": list(self.inline_tags),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EditableSegment:
        if not isinstance(data, dict):
            raise ValueError("Segment must be a JSON object.")
        if "index" not in data or "text" not in data:
            raise ValueError("Segment requires 'index' and 'text' fields.")
        return cls(
            index=int(data["index"]),
            text=str(data["text"]),
            inline_tags=list(data.get("inline_tags", [])),
        )


@dataclass
class CatalogEntry:
    """A single translatable resource entry (dialogue, stralias, bgm_title, credits_line, caption)."""

    id: str
    kind: str  # "dialogue" | "stralias" | "bgm_title" | "credits_line" | "window_caption"
    line_number: int
    line_span: int
    line_ending: str  # "CRLF" | "LF" | "NONE"
    chapter: str
    label: str
    speaker: str
    voice_files: list[str]
    command_prefix: str
    command_suffix: str
    sprite_prefix: str
    markers: list[str]
    segments: list[EditableSegment]
    text: str
    inline_tags: list[str]
    has_stray_backtick: bool = False
    status: str = "translated"
    notes: str = ""

    def eol_str(self) -> str:
        if self.line_ending == "CRLF":
            return "\r\n"
        if self.line_ending == "LF":
            return "\n"
        return ""

    def reconstruct_script_line(self) -> str:
        """Reconstruct the exact ONScripter-RU script line(s) from this entry."""
        eol = self.eol_str()
        if self.kind == "dialogue":
            if len(self.markers) != len(self.segments) + 1:
                raise ValueError(
                    f"Entry {self.id}: markers count ({len(self.markers)}) must equal "
                    f"segments count + 1 ({len(self.segments) + 1})."
                )
            body = (
                "".join(
                    f"{self.markers[i]}`{self.segments[i].text}`"
                    for i in range(len(self.segments))
                )
                + self.markers[-1]
            )
            return f"{self.command_prefix}{body}{self.command_suffix}{eol}"

        # Non-dialogue single-string commands: stralias, bgm_title, credits_line, window_caption
        return f"{self.command_prefix}{self.sprite_prefix}{self.text}{self.command_suffix}{eol}"

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.id,
            "kind": self.kind,
            "line_number": self.line_number,
            "line_span": self.line_span,
            "line_ending": self.line_ending,
            "chapter": self.chapter,
            "label": self.label,
            "speaker": self.speaker,
            "voice_files": list(self.voice_files),
            "command_prefix": self.command_prefix,
            "command_suffix": self.command_suffix,
            "sprite_prefix": self.sprite_prefix,
            "markers": list(self.markers),
            "segments": [seg.to_dict() for seg in self.segments],
            "text": self.text,
            "inline_tags": list(self.inline_tags),
            "has_stray_backtick": self.has_stray_backtick,
            "status": self.status,
            "notes": self.notes,
        }
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CatalogEntry:
        if not isinstance(data, dict):
            raise ValueError("CatalogEntry must be a JSON object.")
        required = (
            "id",
            "kind",
            "line_number",
            "line_ending",
            "command_prefix",
            "command_suffix",
            "markers",
            "segments",
            "text",
        )
        for req in required:
            if req not in data:
                raise ValueError(f"CatalogEntry missing required field {req!r}.")
        return cls(
            id=str(data["id"]),
            kind=str(data["kind"]),
            line_number=int(data["line_number"]),
            line_span=int(data.get("line_span", 1)),
            line_ending=str(data["line_ending"]),
            chapter=str(data.get("chapter", "")),
            label=str(data.get("label", "")),
            speaker=str(data.get("speaker", "")),
            voice_files=list(data.get("voice_files", [])),
            command_prefix=str(data["command_prefix"]),
            command_suffix=str(data["command_suffix"]),
            sprite_prefix=str(data.get("sprite_prefix", "")),
            markers=[str(m) for m in data["markers"]],
            segments=[EditableSegment.from_dict(s) for s in data["segments"]],
            text=str(data["text"]),
            inline_tags=[str(t) for t in data.get("inline_tags", [])],
            has_stray_backtick=bool(data.get("has_stray_backtick", False)),
            status=str(data.get("status", "translated")),
            notes=str(data.get("notes", "")),
        )


@dataclass
class TranslationCatalog:
    """A structured JSON file containing an ordered list of translatable entries."""

    schema_version: str
    catalog_id: str
    category: str  # "story" | "omake" | "strings"
    rel_path: str
    episode: str | None
    chapter: str
    description: str
    entries: list[CatalogEntry] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "catalog_id": self.catalog_id,
            "category": self.category,
            "rel_path": self.rel_path,
            "episode": self.episode,
            "section": self.chapter,
            "chapter": self.chapter,
            "description": self.description,
            "entry_count": len(self.entries),
            "entries": [e.to_dict() for e in self.entries],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TranslationCatalog:
        if not isinstance(data, dict):
            raise ValueError("TranslationCatalog must be a JSON object.")
        for req in ("schema_version", "catalog_id", "category", "rel_path", "entries"):
            if req not in data:
                raise ValueError(f"TranslationCatalog missing required field {req!r}.")
        if not isinstance(data["entries"], list):
            raise ValueError("TranslationCatalog 'entries' must be a list.")
        chapter_val = str(data.get("chapter") or data.get("section") or "")
        return cls(
            schema_version=str(data["schema_version"]),
            catalog_id=str(data["catalog_id"]),
            category=str(data["category"]),
            rel_path=str(data["rel_path"]),
            episode=str(data["episode"]) if data.get("episode") is not None else None,
            chapter=chapter_val,
            description=str(data.get("description", "")),
            entries=[CatalogEntry.from_dict(item) for item in data["entries"]],
        )


@dataclass
class StructuralBlock:
    """An ordered sequence of raw non-editable script chunks and entry slots."""

    schema_version: str
    block_id: str
    rel_path: str
    records: list[dict[str, Any]] = field(default_factory=list)

    def append_raw_line(self, line_number: int, raw_text: str) -> None:
        if self.records and self.records[-1]["kind"] == "raw":
            last = self.records[-1]
            last["end_line"] = line_number
            last["text"] += raw_text
        else:
            self.records.append(
                {
                    "kind": "raw",
                    "start_line": line_number,
                    "end_line": line_number,
                    "text": raw_text,
                }
            )

    def append_entry_slot(self, entry_id: str, catalog_rel_path: str, line_number: int) -> None:
        self.records.append(
            {
                "kind": "entry",
                "id": entry_id,
                "catalog": catalog_rel_path,
                "line_number": line_number,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "block_id": self.block_id,
            "rel_path": self.rel_path,
            "record_count": len(self.records),
            "records": self.records,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StructuralBlock:
        if not isinstance(data, dict):
            raise ValueError("StructuralBlock must be a JSON object.")
        for req in ("schema_version", "block_id", "rel_path", "records"):
            if req not in data:
                raise ValueError(f"StructuralBlock missing required field {req!r}.")
        return cls(
            schema_version=str(data["schema_version"]),
            block_id=str(data["block_id"]),
            rel_path=str(data["rel_path"]),
            records=list(data["records"]),
        )
