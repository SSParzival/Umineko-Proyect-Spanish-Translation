"""Command-line interface for `python -m tools.esfile`."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from tools.esfile import __version__
from tools.esfile.codec import EsFileError
from tools.esfile.extractor import extract_esfile
from tools.esfile.inspector import format_inspection_report, inspect_esfile


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

    except EsFileError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0
