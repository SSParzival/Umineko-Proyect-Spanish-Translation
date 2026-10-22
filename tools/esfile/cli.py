"""Command-line interface for `python -m tools.esfile`."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from tools.esfile import __version__
from tools.esfile.builder import build_esfile
from tools.esfile.codec import EsFileError
from tools.esfile.differ import diff_targets, format_diff_report
from tools.esfile.extractor import extract_esfile
from tools.esfile.inspector import format_inspection_report, inspect_esfile
from tools.esfile.validator import validate_workspace


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tools.esfile",
        description="Lossless ONS2 (es.file) extraction, compilation, validation, and diff toolkit for Umineko Project.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 1. inspect
    p_inspect = subparsers.add_parser(
        "inspect",
        help="Inspect an ONS2 (es.file) container and display format, checksum, and entry statistics.",
    )
    p_inspect.add_argument("input", type=Path, help="Path to the ONS2 (.file) archive.")
    p_inspect.add_argument(
        "--json",
        action="store_true",
        help="Output inspection summary as JSON.",
    )
    p_inspect.add_argument(
        "--strict",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enforce strict binary and script format checks (default: true).",
    )
    p_inspect.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Include detailed source warning list.",
    )

    # 2. extract
    p_extract = subparsers.add_parser(
        "extract",
        help="Extract an ONS2 (es.file) container into structured editable JSON catalogs and structural blocks.",
    )
    p_extract.add_argument("input", type=Path, help="Path to the input ONS2 (.file) archive.")
    p_extract.add_argument(
        "output_pos",
        nargs="?",
        type=Path,
        default=None,
        help="Optional positional output directory (use --output or positional).",
    )
    p_extract.add_argument(
        "--output",
        "-o",
        dest="output_opt",
        type=Path,
        default=None,
        help="Target directory for extracted translation files.",
    )
    p_extract.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Allow overwriting a non-empty output directory.",
    )
    p_extract.add_argument(
        "--strict",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enforce strict header, ZLIB, and UTF-8 checks (default: true).",
    )
    p_extract.add_argument(
        "--encoding",
        default="utf-8",
        help="Expected script character encoding (default: utf-8).",
    )
    p_extract.add_argument(
        "--keep-raw",
        action="store_true",
        help="Also save the full decoded UTF-8 script under raw/decoded_script.txt.",
    )
    p_extract.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Optional path to write a copy of the extraction JSON report.",
    )
    p_extract.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print detailed extraction statistics and warnings.",
    )

    # 3. validate
    p_validate = subparsers.add_parser(
        "validate",
        help="Validate an extracted translation directory for schema, tag, marker, and checksum integrity.",
    )
    p_validate.add_argument(
        "translation_dir",
        type=Path,
        help="Path to the extracted translation directory containing manifest.json.",
    )
    p_validate.add_argument(
        "--strict",
        action="store_true",
        default=False,
        help="Treat inline formatting tag prefix changes as errors instead of warnings.",
    )
    p_validate.add_argument(
        "--json",
        action="store_true",
        help="Output validation report as JSON.",
    )
    p_validate.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Optional path to write the JSON validation report.",
    )
    p_validate.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print all warnings in addition to errors.",
    )

    # 4. build
    p_build = subparsers.add_parser(
        "build",
        help="Compile a structured translation directory back into an ONS2 (.file) archive.",
    )
    p_build.add_argument(
        "translation_dir",
        type=Path,
        help="Path to the extracted translation directory containing manifest.json.",
    )
    p_build.add_argument(
        "output_pos",
        nargs="?",
        type=Path,
        default=None,
        help="Target path for the rebuilt .file archive (positional or --output).",
    )
    p_build.add_argument(
        "--output",
        "-o",
        dest="output_opt",
        type=Path,
        default=None,
        help="Target path for the rebuilt .file archive.",
    )
    p_build.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Allow overwriting an existing output .file archive.",
    )
    p_build.add_argument(
        "--strict",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enforce strict syntax and inline tag balance checks before building (default: true).",
    )
    p_build.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Optional path to write the JSON build report.",
    )
    p_build.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print detailed build checksums and comparison metrics.",
    )

    # 5. diff
    p_diff = subparsers.add_parser(
        "diff",
        help="Compare two ONS2 (.file) archives or two extracted translation directories semantically and binarily.",
    )
    p_diff.add_argument("target_a", type=Path, help="First .file archive or translation directory.")
    p_diff.add_argument("target_b", type=Path, help="Second .file archive or translation directory.")
    p_diff.add_argument(
        "--json",
        action="store_true",
        help="Output diff report as JSON.",
    )
    p_diff.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Optional path to write the JSON diff report.",
    )
    p_diff.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show all modified entries without truncation.",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "inspect":
            info = inspect_esfile(args.input, strict=args.strict)
            if args.json:
                print(json.dumps(info, ensure_ascii=False, indent=2))
            else:
                print(format_inspection_report(info, verbose=args.verbose))
            return 0

        if args.command == "extract":
            output_dir = args.output_opt or args.output_pos
            if output_dir is None:
                parser.error("extract requires an output directory via --output <dir> or positional argument.")
            report = extract_esfile(
                args.input,
                output_dir,
                force=args.force,
                strict=args.strict,
                encoding=args.encoding,
                keep_raw=args.keep_raw,
                report_path=args.report,
            )
            counts = report["counts"]
            print(
                f"Extracted {args.input.name} -> {output_dir} "
                f"({counts['catalog_files']} catalogs, {counts['block_files']} blocks, "
                f"{counts['total_entries']:,} entries, {counts['warnings']} warnings)."
            )
            if args.verbose and report["warnings"]:
                for w in report["warnings"]:
                    print(f"  [WARN L{w['line_number']}] {w['code']} ({w['entry_id']}): {w['message']}")
            return 0

        if args.command == "validate":
            v_report = validate_workspace(args.translation_dir, strict=args.strict)
            v_dict = v_report.to_dict()
            if args.report is not None:
                args.report.parent.mkdir(parents=True, exist_ok=True)
                args.report.write_text(
                    json.dumps(v_dict, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
            if args.json:
                print(json.dumps(v_dict, ensure_ascii=False, indent=2))
            else:
                status_word = "VALID" if v_report.valid else "INVALID"
                print(
                    f"Validation {status_word}: {args.translation_dir} "
                    f"({v_report.catalogs_checked} catalogs, {v_report.blocks_checked} blocks, "
                    f"{v_report.entries_checked:,} entries, {len(v_report.errors)} errors, "
                    f"{len(v_report.warnings)} warnings, {len(v_report.modified_catalogs)} modified catalogs)."
                )
                for err in v_report.errors:
                    print(f"  [ERROR] {err.code} ({err.location} {err.entry_id}): {err.message}")
                if args.verbose:
                    for warn in v_report.warnings:
                        print(f"  [WARN]  {warn.code} ({warn.location} {warn.entry_id}): {warn.message}")
            return 0 if v_report.valid else 1

        if args.command == "build":
            output_file = args.output_opt or args.output_pos
            if output_file is None:
                parser.error("build requires an output file path via positional argument or --output <file>.")
            report = build_esfile(
                args.translation_dir,
                output_file,
                force=args.force,
                strict=args.strict,
                report_path=args.report,
            )
            match_str = (
                "BINARY-IDENTICAL"
                if report["binary_identical_to_original"]
                else (
                    "PLAINTEXT-IDENTICAL"
                    if report["plaintext_identical_to_original"]
                    else f"MODIFIED ({len(report['modified_catalogs'])} catalog(s) changed)"
                )
            )
            print(
                f"Built {output_file} from {args.translation_dir} "
                f"({report['file_size_bytes']:,} bytes, SHA-256={report['file_sha256'][:16]}..., {match_str})."
            )
            if args.verbose:
                print(f"  File SHA-256      : {report['file_sha256']}")
                print(f"  Plaintext SHA-256 : {report['plaintext_sha256']}")
                print(f"  ZLIB Adler-32     : {report['zlib_adler32']}")
                print(f"  Entries compiled  : {report['entries_compiled']:,}")
            return 0

        if args.command == "diff":
            diff_data = diff_targets(args.target_a, args.target_b, report_path=args.report)
            if args.json:
                print(json.dumps(diff_data, ensure_ascii=False, indent=2))
            else:
                print(format_diff_report(diff_data, verbose=args.verbose))
            return 0

    except EsFileError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0
