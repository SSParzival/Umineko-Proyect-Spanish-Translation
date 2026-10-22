"""Line-by-line parser for decoded Umineko Project ONScripter-RU scripts."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from tools.esfile import SCHEMA_VERSION
from tools.esfile.codec import EsFileFormatError
from tools.esfile.models import (
    CatalogEntry,
    EditableSegment,
    StructuralBlock,
    TranslationCatalog,
    extract_inline_tags,
    extract_voice_files,
)

# Top-level chapter label patterns
EPISODE_CHAPTER_RE = re.compile(
    r"^\*(umi([1-8])_(?:op|\d+)|teatime_([1-8])|ura_teatime_([1-8]))$"
)
OMAKE_CHAPTERS = frozenset(
    {
        "o1_0",
        "o2_0",
        "o3_start",
        "o4_0",
        "chiru_trailer",
        "o_chiru_start",
        "omake_chiru_menu",
        "o8_0",
        "o9_0",
    }
)
POST_STORY_START_LABELS = frozenset({"*ep1_end", "*bt_def", "*load_font_preference", "*bgm_locale_title"})

# Dialogue command pattern: `d ...` or `d2 ...`
D_LINE_RE = re.compile(r"^([ \t]*d2?[ \t]+)(.*?)(\r\n|\n)?$", re.DOTALL)
TAG_SPLIT_RE = re.compile(r"((?:\s*\[[^\]]*\])+)")
MSGWND_RE = re.compile(r"^[ \t]*msgwnd_([A-Za-z0-9_]+)\b")

# stralias command pattern (supports single-line and 2-line strings, and optional comma)
STRALIAS_RE = re.compile(
    r'^([ \t]*stralias[ \t]+([A-Za-z0-9_]+)([ \t]*,?[ \t]*)"'
    r")(:s;#[0-9A-Fa-f]{6}(?:#[0-9A-Fa-f]{6})?`)?(.*?)"
    r'("[ \t]*(?:;[^\r\n]*)?)(\r\n|\n)?$',
    re.DOTALL,
)

# Window caption pattern in *define
CAPTION_RE = re.compile(
    r'^([ \t]*(?:if[ \t]+[^\r\n]+?[ \t]+)?caption[ \t]+")([^"]*)("[^\r\n]*)(\r\n|\n)?$'
)

# Credits line pattern in *credits_base
CREDITS_ADD_RE = re.compile(
    r'^([ \t]*(?:if[ \t]+[^\r\n]+?[ \t]+)?add[ \t]+\$Free1[ \t]*,[ \t]*")([^"]*)("[ \t]*(?:;[^\r\n]*)?)(\r\n|\n)?$'
)

# Localized BGM title pattern in *bgm_locale_title
BGM_LOCALE_RE = re.compile(
    r'^([ \t]*if[ \t]+%BGM_Id[ \t]*==[ \t]*(\d+)[ \t]+mov[ \t]+\$BGM_Title[ \t]*,[ \t]*")([^"]*)("[ \t]*:[ \t]*return[ \t]*(?:;[^\r\n]*)?)(\r\n|\n)?$'
)

ASSET_EXTENSIONS = (
    ".png",
    ".jpg",
    ".jpeg",
    ".bmp",
    ".ttf",
    ".otf",
    ".ogg",
    ".wav",
    ".mp4",
    ".mkv",
    ".avi",
    ".dat",
)
NON_TRANSLATABLE_STRALIAS_KEYS = frozenset({"localisation", "end_8a_current"})

STRING_CATALOG_SPECS: dict[str, tuple[str, str]] = {
    "define_system": (
        "strings/define_system.json",
        "Window captions and file verification messages in *define.",
    ),
    "credits": (
        "strings/credits.json",
        "Scrolling credits lines in *credits_base.",
    ),
    "tips_titles": (
        "strings/tips_titles.json",
        "Tips menu list titles (r_tips_*).",
    ),
    "tips_texts": (
        "strings/tips_texts.json",
        "Tips menu body texts and descriptions (tips_*).",
    ),
    "grimoire_texts": (
        "strings/grimoire_texts.json",
        "Grimoire of the Witch titles and explanations (r_grim*, grim_*).",
    ),
    "characters": (
        "strings/characters.json",
        "Character profile bios and display names (chars_*, name_*).",
    ),
    "menu_and_ui": (
        "strings/menu_and_ui.json",
        "Scenario titles, timestamps, save/load strings, and settings menu labels.",
    ),
    "ep8_mystery": (
        "strings/ep8_mystery.json",
        "Episode 8 Bernkastel mystery game and quiz strings (ep8_*, quiz_*).",
    ),
    "trophies": (
        "strings/trophies.json",
        "In-game trophy titles and unlock descriptions (trophy_text_*).",
    ),
    "font_preview": (
        "strings/font_preview.json",
        "Font preference preview dialogue lines (*goa_1e..4e, *kak_1e..10e).",
    ),
    "bgm_titles": (
        "strings/bgm_titles.json",
        "Localized Spanish BGM track titles in *bgm_locale_title.",
    ),
}


@dataclass
class ParseWarning:
    """Non-fatal anomaly detected in the source script (preserved for round-trip)."""

    code: str
    line_number: int
    entry_id: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "line_number": self.line_number,
            "entry_id": self.entry_id,
            "message": self.message,
        }


@dataclass
class ScriptMetadata:
    """Header directives and version metadata extracted from the script."""

    mode_directive: str = ""
    gameid_directive: str = ""
    localisation: str = ""
    releasedate: int | None = None
    chiru_mode_version: str = ""
    total_physical_lines: int = 0
    crlf_line_count: int = 0
    lf_line_count: int = 0
    unique_label_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode_directive": self.mode_directive,
            "gameid_directive": self.gameid_directive,
            "localisation": self.localisation,
            "releasedate": self.releasedate,
            "chiru_mode_version": self.chiru_mode_version,
            "total_physical_lines": self.total_physical_lines,
            "crlf_line_count": self.crlf_line_count,
            "lf_line_count": self.lf_line_count,
            "unique_label_count": self.unique_label_count,
        }


@dataclass
class ParseResult:
    """Complete result of parsing a decoded ONScripter-RU script."""

    metadata: ScriptMetadata
    catalogs: dict[str, TranslationCatalog] = field(default_factory=dict)
    blocks: list[StructuralBlock] = field(default_factory=list)
    warnings: list[ParseWarning] = field(default_factory=list)


def _detect_eol(raw_line: str) -> str:
    if raw_line.endswith("\r\n"):
        return "CRLF"
    if raw_line.endswith("\n"):
        return "LF"
    return "NONE"


def _classify_stralias_catalog(alias_key: str) -> str:
    if alias_key.startswith(("verify_", "verification_")):
        return "define_system"
    if alias_key.startswith("r_tips_"):
        return "tips_titles"
    if alias_key.startswith("tips_"):
        return "tips_texts"
    if alias_key.startswith(("r_grim", "grim_")):
        return "grimoire_texts"
    if alias_key.startswith(("chars_", "name_")):
        return "characters"
    if alias_key.startswith(("ep8_", "quiz_")):
        return "ep8_mystery"
    if alias_key.startswith("trophy_text_"):
        return "trophies"
    return "menu_and_ui"


def _tokenize_dialogue_body(
    body: str, line_number: int
) -> tuple[list[str], list[EditableSegment], bool]:
    """Split dialogue body into `markers` (len N+1) and `segments` (len N)."""
    parts = TAG_SPLIT_RE.split(body)
    tokens: list[tuple[str, str]] = []
    for idx, part in enumerate(parts):
        if idx % 2 == 1:
            if tokens and tokens[-1][0] == "M":
                tokens[-1] = ("M", tokens[-1][1] + part)
            else:
                tokens.append(("M", part))
        else:
            if part == "":
                continue
            if not (len(part) >= 2 and part.startswith("`") and part.endswith("`")):
                raise EsFileFormatError(
                    f"Line {line_number}: malformed dialogue segment outside brackets: {part!r}"
                )
            tokens.append(("S", part[1:-1]))

    markers: list[str] = []
    segments: list[EditableSegment] = []
    has_stray_backtick = False
    cur_marker = ""

    for kind, val in tokens:
        if kind == "M":
            cur_marker += val
        else:
            markers.append(cur_marker)
            cur_marker = ""
            if "`" in val:
                has_stray_backtick = True
            seg_idx = len(segments)
            segments.append(
                EditableSegment(
                    index=seg_idx,
                    text=val,
                    inline_tags=extract_inline_tags(val),
                )
            )
    markers.append(cur_marker)
    if not segments:
        raise EsFileFormatError(f"Line {line_number}: dialogue line contains 0 backtick segments.")
    return markers, segments, has_stray_backtick


def parse_script(plaintext: str) -> ParseResult:
    """Parse decoded ONScripter-RU UTF-8 script into editable catalogs and structural blocks."""
    lines = plaintext.splitlines(keepends=True)
    metadata = ScriptMetadata(total_physical_lines=len(lines))
    if lines:
        first = lines[0].strip()
        if first.startswith(";mode"):
            metadata.mode_directive = first
    if len(lines) >= 2:
        second = lines[1].strip()
        if second.startswith(";gameid"):
            metadata.gameid_directive = second

    catalogs: dict[str, TranslationCatalog] = {}
    blocks_by_id: dict[str, StructuralBlock] = {}
    block_order: list[str] = []
    warnings: list[ParseWarning] = []

    def get_block(block_id: str, rel_path: str) -> StructuralBlock:
        if block_id not in blocks_by_id:
            blocks_by_id[block_id] = StructuralBlock(
                schema_version=SCHEMA_VERSION,
                block_id=block_id,
                rel_path=rel_path,
            )
            block_order.append(block_id)
        return blocks_by_id[block_id]

    def get_string_catalog(cat_key: str) -> TranslationCatalog:
        rel_path, desc = STRING_CATALOG_SPECS[cat_key]
        if rel_path not in catalogs:
            catalogs[rel_path] = TranslationCatalog(
                schema_version=SCHEMA_VERSION,
                catalog_id=f"strings.{cat_key}",
                category="strings",
                rel_path=rel_path,
                episode=None,
                chapter=cat_key,
                description=desc,
            )
        return catalogs[rel_path]

    def get_story_catalog(episode: int | None, chapter: str) -> TranslationCatalog:
        if episode is not None:
            rel_path = f"story/ep{episode}/{chapter}.json"
            cat_id = f"story.ep{episode}.{chapter}"
            category = "story"
            ep_str: str | None = f"ep{episode}"
            desc = f"Episode {episode} story script chapter '{chapter}'."
        else:
            rel_path = f"story/omake/{chapter}.json"
            cat_id = f"story.omake.{chapter}"
            category = "omake"
            ep_str = None
            desc = f"Omake / bonus script chapter '{chapter}'."
        if rel_path not in catalogs:
            catalogs[rel_path] = TranslationCatalog(
                schema_version=SCHEMA_VERSION,
                catalog_id=cat_id,
                category=category,
                rel_path=rel_path,
                episode=ep_str,
                chapter=chapter,
                description=desc,
            )
        return catalogs[rel_path]

    current_block = get_block("00_define_and_start", "blocks/00_define_and_start.json")
    current_chapter = "define"
    current_episode: int | None = None
    in_story = False
    in_post_story = False
    in_credits_base = False
    in_bgm_locale = False
    current_label = "*define"
    current_speaker = "narrator"

    seen_entry_ids: set[str] = set()
    unique_labels: set[str] = set()
    credits_seq = 0
    caption_seq = 0

    def make_unique_id(base_id: str, line_no: int) -> str:
        candidate = base_id
        if candidate in seen_entry_ids:
            candidate = f"{base_id}.L{line_no}"
        seen_entry_ids.add(candidate)
        return candidate

    i = 0
    n_lines = len(lines)
    while i < n_lines:
        raw_line = lines[i]
        line_no = i + 1
        eol_kind = _detect_eol(raw_line)
        if eol_kind == "CRLF":
            metadata.crlf_line_count += 1
        elif eol_kind == "LF":
            metadata.lf_line_count += 1

        stripped = raw_line.strip()

        # Metadata extraction in *define
        if not in_story and not in_post_story:
            if stripped.startswith('stralias localisation,'):
                m_loc = re.search(r'"([^"]+)"', stripped)
                if m_loc:
                    metadata.localisation = m_loc.group(1)
            elif stripped.startswith("numalias releasedate,"):
                m_rel = re.search(r"releasedate,(\d+)", stripped)
                if m_rel:
                    metadata.releasedate = int(m_rel.group(1))
            elif stripped.startswith('mov $CHIRU_MODE,'):
                m_cm = re.search(r'"([^"]+)"', stripped)
                if m_cm:
                    metadata.chiru_mode_version = m_cm.group(1)

        # Track labels and section transitions
        if stripped.startswith("*"):
            label_token = stripped.split()[0]
            unique_labels.add(label_token)
            current_label = label_token

            ep_match = EPISODE_CHAPTER_RE.match(label_token) if not in_post_story else None
            if ep_match:
                chapter_name = ep_match.group(1)
                ep_num = int(ep_match.group(2) or ep_match.group(3) or ep_match.group(4))
                current_chapter = chapter_name
                current_episode = ep_num
                in_story = True
                in_post_story = False
                in_credits_base = False
                in_bgm_locale = False
                current_block = get_block(
                    f"0{ep_num}_story_ep{ep_num}",
                    f"blocks/0{ep_num}_story_ep{ep_num}.json",
                )
            elif not in_post_story and label_token[1:] in OMAKE_CHAPTERS:
                chapter_name = label_token[1:]
                current_chapter = chapter_name
                current_episode = None
                in_story = True
                in_post_story = False
                in_credits_base = False
                in_bgm_locale = False
                current_block = get_block("09_story_omake", "blocks/09_story_omake.json")
            elif label_token in POST_STORY_START_LABELS or (in_post_story and label_token.startswith("*")):
                if not in_post_story:
                    in_story = False
                    in_post_story = True
                    current_episode = None
                    current_block = get_block("10_post_story", "blocks/10_post_story.json")
                if label_token == "*credits_base":
                    in_credits_base = True
                    current_chapter = "credits_base"
                elif label_token in ("*credits_end", "*chiru_ending", "*end_game"):
                    in_credits_base = False
                elif label_token == "*bt_def":
                    current_chapter = "bt_def"
                elif label_token == "*load_font_preference":
                    current_chapter = "load_font_preference"
                elif label_token == "*bgm_locale_title":
                    in_bgm_locale = True
                    current_chapter = "bgm_locale_title"

            current_block.append_raw_line(line_no, raw_line)
            i += 1
            continue

        # Track speaker window commands
        m_wnd = MSGWND_RE.match(raw_line)
        if m_wnd:
            wnd_id = m_wnd.group(1)
            current_speaker = "narrator" if wnd_id == "non" else wnd_id
            current_block.append_raw_line(line_no, raw_line)
            i += 1
            continue

        # 1. Check dialogue command (`d` / `d2`)
        lstripped = raw_line.lstrip()
        if lstripped.startswith(("d ", "d\t", "d2 ", "d2\t")) and "`" in lstripped:
            m_d = D_LINE_RE.match(raw_line)
            if m_d:
                cmd_prefix, body, _eol = m_d.groups()
                markers, segments, has_stray = _tokenize_dialogue_body(body, line_no)
                if in_story:
                    cat = get_story_catalog(current_episode, current_chapter)
                    lbl_clean = current_label.lstrip("*") or f"L{line_no}"
                    prefix_id = (
                        f"ep{current_episode}.{current_chapter}.{lbl_clean}"
                        if current_episode is not None
                        else f"omake.{current_chapter}.{lbl_clean}"
                    )
                else:
                    cat = get_string_catalog("font_preview")
                    lbl_clean = current_label.lstrip("*") or f"L{line_no}"
                    prefix_id = f"font_preview.{lbl_clean}"

                entry_id = make_unique_id(prefix_id, line_no)
                joined_text = " ".join(seg.text for seg in segments)
                all_inline_tags: list[str] = []
                for seg in segments:
                    all_inline_tags.extend(seg.inline_tags)

                notes = ""
                if has_stray:
                    notes = (
                        "Pre-existing stray backtick inside segment; preserved for lossless round-trip."
                    )
                    warnings.append(
                        ParseWarning(
                            code="STRAY_BACKTICK_IN_DIALOGUE",
                            line_number=line_no,
                            entry_id=entry_id,
                            message=f"Dialogue line contains an extra backtick inside a segment ({entry_id}).",
                        )
                    )

                entry = CatalogEntry(
                    id=entry_id,
                    kind="dialogue",
                    line_number=line_no,
                    line_span=1,
                    line_ending=eol_kind,
                    chapter=current_chapter,
                    label=current_label,
                    speaker=current_speaker,
                    voice_files=extract_voice_files(markers),
                    command_prefix=cmd_prefix,
                    command_suffix="",
                    sprite_prefix="",
                    markers=markers,
                    segments=segments,
                    text=joined_text,
                    inline_tags=all_inline_tags,
                    has_stray_backtick=has_stray,
                    status="translated",
                    notes=notes,
                )
                cat.entries.append(entry)
                current_block.append_entry_slot(entry.id, cat.rel_path, line_no)
                i += 1
                continue

        # 2. Check stralias commands (single-line or 2-line literal)
        if lstripped.startswith("stralias "):
            combined_raw = raw_line
            span = 1
            if combined_raw.count('"') < 2 and (i + 1) < n_lines:
                next_line = lines[i + 1]
                combined_raw = raw_line + next_line
                span = 2
                next_eol = _detect_eol(next_line)
                if next_eol == "CRLF":
                    metadata.crlf_line_count += 1
                elif next_eol == "LF":
                    metadata.lf_line_count += 1
                eol_kind = next_eol

            m_str = STRALIAS_RE.match(combined_raw)
            if m_str:
                cmd_pre, alias_key, sep_part, sprite_pre, text_body, cmd_suf, _eol = m_str.groups()
                sprite_pre = sprite_pre or ""
                lower_body = text_body.lower()
                is_asset = lower_body.endswith(ASSET_EXTENSIONS)
                if not is_asset and alias_key not in NON_TRANSLATABLE_STRALIAS_KEYS:
                    cat_key = _classify_stralias_catalog(alias_key)
                    cat = get_string_catalog(cat_key)
                    entry_id = make_unique_id(f"stralias.{alias_key}", line_no)
                    notes_list: list[str] = []
                    if span > 1:
                        notes_list.append("Multiline stralias containing embedded newline.")
                        warnings.append(
                            ParseWarning(
                                code="MULTILINE_STRALIAS",
                                line_number=line_no,
                                entry_id=entry_id,
                                message=f"stralias '{alias_key}' spans {span} physical lines.",
                            )
                        )
                    if "," not in sep_part:
                        notes_list.append("Original stralias omits comma before opening quote.")
                        warnings.append(
                            ParseWarning(
                                code="MISSING_COMMA_IN_STRALIAS",
                                line_number=line_no,
                                entry_id=entry_id,
                                message=f"stralias '{alias_key}' omits comma separator before string literal.",
                            )
                        )

                    entry = CatalogEntry(
                        id=entry_id,
                        kind="stralias",
                        line_number=line_no,
                        line_span=span,
                        line_ending=eol_kind,
                        chapter=current_chapter,
                        label=current_label,
                        speaker="",
                        voice_files=[],
                        command_prefix=cmd_pre,
                        command_suffix=cmd_suf,
                        sprite_prefix=sprite_pre,
                        markers=[],
                        segments=[],
                        text=text_body,
                        inline_tags=extract_inline_tags(text_body),
                        has_stray_backtick=False,
                        status="translated",
                        notes=" ".join(notes_list),
                    )
                    cat.entries.append(entry)
                    current_block.append_entry_slot(entry.id, cat.rel_path, line_no)
                    i += span
                    continue

        # 3. Check window caption in *define
        if not in_story and not in_post_story and "caption " in lstripped:
            m_cap = CAPTION_RE.match(raw_line)
            if m_cap:
                cmd_pre, text_body, cmd_suf, _eol = m_cap.groups()
                caption_seq += 1
                cat = get_string_catalog("define_system")
                entry_id = make_unique_id(f"define.caption.{caption_seq}", line_no)
                entry = CatalogEntry(
                    id=entry_id,
                    kind="window_caption",
                    line_number=line_no,
                    line_span=1,
                    line_ending=eol_kind,
                    chapter="define",
                    label=current_label,
                    speaker="",
                    voice_files=[],
                    command_prefix=cmd_pre,
                    command_suffix=cmd_suf,
                    sprite_prefix="",
                    markers=[],
                    segments=[],
                    text=text_body,
                    inline_tags=extract_inline_tags(text_body),
                )
                cat.entries.append(entry)
                current_block.append_entry_slot(entry.id, cat.rel_path, line_no)
                i += 1
                continue

        # 4. Check credits lines in *credits_base
        if in_credits_base and "add $Free1," in lstripped:
            m_cred = CREDITS_ADD_RE.match(raw_line)
            if m_cred:
                cmd_pre, text_body, cmd_suf, _eol = m_cred.groups()
                credits_seq += 1
                cat = get_string_catalog("credits")
                entry_id = make_unique_id(f"credits.line.{credits_seq:03d}", line_no)
                entry = CatalogEntry(
                    id=entry_id,
                    kind="credits_line",
                    line_number=line_no,
                    line_span=1,
                    line_ending=eol_kind,
                    chapter="credits_base",
                    label=current_label,
                    speaker="",
                    voice_files=[],
                    command_prefix=cmd_pre,
                    command_suffix=cmd_suf,
                    sprite_prefix="",
                    markers=[],
                    segments=[],
                    text=text_body,
                    inline_tags=extract_inline_tags(text_body),
                )
                cat.entries.append(entry)
                current_block.append_entry_slot(entry.id, cat.rel_path, line_no)
                i += 1
                continue

        # 5. Check localized BGM titles in *bgm_locale_title
        if in_bgm_locale and "$BGM_Title," in lstripped:
            m_bgm = BGM_LOCALE_RE.match(raw_line)
            if m_bgm:
                cmd_pre, bgm_id_str, text_body, cmd_suf, _eol = m_bgm.groups()
                cat = get_string_catalog("bgm_titles")
                entry_id = make_unique_id(f"bgm.locale.{int(bgm_id_str):03d}", line_no)
                entry = CatalogEntry(
                    id=entry_id,
                    kind="bgm_title",
                    line_number=line_no,
                    line_span=1,
                    line_ending=eol_kind,
                    chapter="bgm_locale_title",
                    label=current_label,
                    speaker="",
                    voice_files=[],
                    command_prefix=cmd_pre,
                    command_suffix=cmd_suf,
                    sprite_prefix="",
                    markers=[],
                    segments=[],
                    text=text_body,
                    inline_tags=extract_inline_tags(text_body),
                )
                cat.entries.append(entry)
                current_block.append_entry_slot(entry.id, cat.rel_path, line_no)
                i += 1
                continue

        # Otherwise: preserve raw structural script line
        current_block.append_raw_line(line_no, raw_line)
        i += 1

    metadata.unique_label_count = len(unique_labels)
    ordered_blocks = [blocks_by_id[bid] for bid in block_order]
    return ParseResult(
        metadata=metadata,
        catalogs=catalogs,
        blocks=ordered_blocks,
        warnings=warnings,
    )
