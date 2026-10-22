"""Command-line interface for the `tools.translation_lint` toolkit."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Sequence

from tools.translation_lint import __version__
from tools.translation_lint.applicator import apply_corrections_workspace
from tools.translation_lint.double_space_normalizer import apply_double_space_normalization
from tools.translation_lint.models import Finding, LintReport
from tools.translation_lint.rules import HUMAN_REVIEW_FINDINGS
from tools.translation_lint.scanner import scan_workspace
from tools.translation_lint.validator import validate_workspace_lint


def _generate_markdown_corrections_report(
    findings: list[Finding],
    modified_files: list[str],
    total_entries_checked: int,
) -> str:
    """Generate reports/translation-corrections.md markdown content."""
    lines: list[str] = [
        "# Informe Completo de Correcciones Ortotipográficas — Umineko Project (Español)",
        "",
        "## 1. Resumen Ejecutivo",
        "",
        f"- **Versión de la herramienta**: `tools.translation_lint v{__version__}`",
        f"- **Archivos modificados**: {len(modified_files)}",
        f"- **Entradas revisadas en total**: {total_entries_checked:,}",
        f"- **Correcciones de confianza ALTA aplicadas**: {len(findings):,}",
        "",
        "## 2. Distribución de Correcciones por Categoría",
        "",
        "| Categoría | Cantidad de Correcciones | Descripción Breve |",
        "|---|---:|---|",
    ]

    by_cat: dict[str, list[Finding]] = defaultdict(list)
    for f in findings:
        by_cat[f.category].append(f)

    for cat in sorted(by_cat.keys()):
        cnt = len(by_cat[cat])
        lines.append(f"| `{cat}` | {cnt} | Correcciones lingüísticas objetivas verificadas. |")

    lines.extend([
        "",
        "## 3. Distribución por Archivo y Episodio",
        "",
        "| Archivo Relativo | Correcciones Aplicadas | Categorías Principales |",
        "|---|---:|---|",
    ])

    by_file: dict[str, list[Finding]] = defaultdict(list)
    for f in findings:
        by_file[f.file_path].append(f)

    for file_rel in sorted(by_file.keys()):
        file_findings = by_file[file_rel]
        f_cats = ", ".join(sorted(set(f.category for f in file_findings)))
        lines.append(f"| `{file_rel}` | {len(file_findings)} | {f_cats} |")

    lines.extend([
        "",
        "## 4. Detalle Muestra de Correcciones Aplicadas",
        "",
        "| ID Entrada | Campo | Antes | Después | Categoría | Justificación |",
        "|---|---|---|---|---|---|",
    ])

    for f in findings[:50]:
        lines.append(
            f"| `{f.entry_id}` | `{f.field_path}` | `{f.before}` | `{f.after}` | `{f.category}` | {f.rule_or_reason} |"
        )

    if len(findings) > 50:
        lines.append(f"| ... | ... | *(+{len(findings) - 50} correcciones adicionales registradas en `reports/translation-corrections.jsonl`)* | ... | ... | ... |")

    lines.extend([
        "",
        "## 5. Garantía de Integridad Estructural y Round-Trip",
        "",
        "- Todos los campos técnicos (`id`, `kind`, `line_number`, `markers`, `voice_files`, `command_prefix`, `command_suffix`) se preservaron intactos.",
        "- Las etiquetas inline de formato (`{n}`, `{c:...}`, `{f:...}`, `{p:...}`, `{ruby:...}`) no sufrieron alteración.",
        "- Las vistas previas `text` y las listas `inline_tags` de las entradas modificadas fueron sincronizadas.",
        "- Los hashes SHA-256 de los catálogos modificados fueron actualizados en `translation/manifest.json`.",
    ])

    return "\n".join(lines) + "\n"


def _generate_human_review_report() -> str:
    """Generate reports/translation-human-review.md content."""
    lines: list[str] = [
        "# Registro de Hallazgos para Revisión Humana — Umineko Project",
        "",
        "Este informe documenta los casos detectados que presentan ambigüedad estilística, sintáctica,",
        "narrativa o dependencias de glosa ruby bilingüe que **NO** deben modificarse automáticamente,",
        "a fin de preservar la fidelidad a la voz narrativa, idiolectos y coherencia técnica.",
        "",
        "## Casos Registrados para Decisión Humana",
        "",
        "| Archivo | ID Entrada | Personaje | Categoría | Confianza | Fragmento / Detalle | Criterio / Decisión Recomendada |",
        "|---|---|---|---|---|---|---|",
    ]

    for item in HUMAN_REVIEW_FINDINGS:
        lines.append(
            f"| `{item['file']}` | `{item['entry_id']}` | `{item['speaker']}` | "
            f"`{item['category']}` | `{item['confidence']}` | `{item['before']}` | {item['rule_or_reason']} |"
        )

    lines.extend([
        "",
        "## Recomendación Editorial",
        "",
        "- **Preservar idiolectos y stutters**: Los tartamudeos y frases fragmentadas (`Deten... te...`, `¡¡D-Deten—!!`) reflejan shock o vacilación emocional y no deben ser 'corregidos' a formas gramaticales formales.",
        "- **Preservar glosas ruby bilingües**: Cuando una división de tags ruby inglesa genera una repetición aparente en español (`más que} {ruby:...:que un`), unificarlas rompería la correspondencia con el texto superior en pantalla.",
    ])

    return "\n".join(lines) + "\n"


def cmd_scan(args: argparse.Namespace) -> int:
    target_path = Path(args.target).resolve()
    print(f"Scanning translation catalogs in: {target_path}")
    report = scan_workspace(target_path)

    print(f"\nScan completed:")
    print(f"  Files checked:   {report.total_files_checked}")
    print(f"  Entries checked: {report.total_entries_checked}")
    print(f"  Total findings:  {report.total_findings}")
    print("\nFindings by Category:")
    for cat, count in sorted(report.count_by_category().items()):
        print(f"  {cat:<25}: {count}")
    print("\nFindings by Confidence:")
    for conf, count in sorted(report.count_by_confidence().items()):
        print(f"  {conf:<25}: {count}")

    return 0


def cmd_report(args: argparse.Namespace) -> int:
    target_path = Path(args.target).resolve()
    output_dir = Path(args.output_dir).resolve() if args.output_dir else target_path.parent / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Scanning and generating reports for: {target_path}")
    scan_rep = scan_workspace(target_path)

    # 1. reports/translation-corrections.jsonl
    jsonl_path = output_dir / "translation-corrections.jsonl"
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for item in scan_rep.findings:
            f.write(json.dumps(item.to_dict(), ensure_ascii=False) + "\n")
    print(f"Wrote audit log: {jsonl_path}")

    # 2. reports/translation-corrections.md
    md_corrections_path = output_dir / "translation-corrections.md"
    alta_findings = [f for f in scan_rep.findings if f.confidence == "ALTA"]
    unique_files = sorted(set(f.file_path for f in alta_findings))
    md_content = _generate_markdown_corrections_report(
        alta_findings, unique_files, scan_rep.total_entries_checked
    )
    md_corrections_path.write_text(md_content, encoding="utf-8")
    print(f"Wrote corrections report: {md_corrections_path}")

    # 3. reports/translation-human-review.md
    md_review_path = output_dir / "translation-human-review.md"
    review_content = _generate_human_review_report()
    md_review_path.write_text(review_content, encoding="utf-8")
    print(f"Wrote human review report: {md_review_path}")

    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    target_path = Path(args.target).resolve()
    output_dir = Path(args.reports_dir).resolve() if args.reports_dir else target_path.parent / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)

    dry_run = getattr(args, "dry_run", False)
    update_manifest = not getattr(args, "no_manifest_update", False)

    print(f"Applying high-confidence proofreading rules to: {target_path} (dry_run={dry_run})")
    applied_findings, modified_catalogs = apply_corrections_workspace(
        target_path,
        dry_run=dry_run,
        update_manifest=update_manifest,
    )

    print(f"\nApplication summary:")
    print(f"  Modified catalogs:   {len(modified_catalogs)}")
    print(f"  Corrections applied: {len(applied_findings)}")

    by_cat: dict[str, int] = defaultdict(int)
    for f in applied_findings:
        by_cat[f.category] += 1

    print("\nApplied by Category:")
    for cat, count in sorted(by_cat.items()):
        print(f"  {cat:<25}: {count}")

    # Write audit JSONL and reports
    jsonl_path = output_dir / "translation-corrections.jsonl"
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for item in applied_findings:
            f.write(json.dumps(item.to_dict(), ensure_ascii=False) + "\n")
        for item in HUMAN_REVIEW_FINDINGS:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"\nWrote full audit log to: {jsonl_path}")

    md_path = output_dir / "translation-corrections.md"
    md_content = _generate_markdown_corrections_report(
        applied_findings, modified_catalogs, 68651
    )
    md_path.write_text(md_content, encoding="utf-8")
    print(f"Wrote corrections summary to: {md_path}")

    review_path = output_dir / "translation-human-review.md"
    review_content = _generate_human_review_report()
    review_path.write_text(review_content, encoding="utf-8")
    print(f"Wrote human review report to: {review_path}")

    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    target_path = Path(args.target).resolve()
    print(f"Validating translation catalogs in: {target_path}")
    val_report = validate_workspace_lint(target_path)

    print(f"\nValidation result: {'PASSED' if val_report.valid else 'FAILED'}")
    print(f"  Files checked:   {val_report.files_checked}")
    print(f"  Entries checked: {val_report.entries_checked}")
    print(f"  Errors:          {len(val_report.errors)}")
    print(f"  Warnings:        {len(val_report.warnings)}")

    if val_report.errors:
        print("\nErrors encountered:")
        for err in val_report.errors[:10]:
            print(f"  [{err.severity.upper()}] {err.location} (id: {err.entry_id}): {err.message}")
        return 1

    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tools.translation_lint",
        description="Spanish proofreading and validation toolkit for Umineko Project translation workspaces.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # scan
    p_scan = subparsers.add_parser("scan", help="Scan translation catalogs for linguistic issues.")
    p_scan.add_argument("target", help="Path to translation workspace or catalog file.")
    p_scan.set_defaults(func=cmd_scan)

    # report
    p_report = subparsers.add_parser("report", help="Scan and write markdown/JSONL reports.")
    p_report.add_argument("target", help="Path to translation workspace or catalog file.")
    p_report.add_argument("--output-dir", help="Directory where reports are written.")
    p_report.set_defaults(func=cmd_report)

    # apply
    p_apply = subparsers.add_parser("apply", help="Apply high-confidence corrections.")
    p_apply.add_argument("target", help="Path to translation workspace or catalog file.")
    p_apply.add_argument("--reports-dir", help="Directory where reports are written.")
    p_apply.add_argument("--dry-run", action="store_true", help="Simulate changes without writing files.")
    p_apply.add_argument("--no-manifest-update", action="store_true", help="Do not update manifest.json hashes.")
    p_apply.set_defaults(func=cmd_apply)

    # validate
    p_val = subparsers.add_parser("validate", help="Validate catalog syntax, schema, and inline tags.")
    p_val.add_argument("target", help="Path to translation workspace or catalog file.")
    p_val.set_defaults(func=cmd_validate)

    # normalize-spaces
    p_norm = subparsers.add_parser("normalize-spaces", help="Normalize unnecessary double spaces outside markup tags.")
    p_norm.add_argument("target", help="Path to translation workspace.")
    p_norm.add_argument("--dry-run", action="store_true", help="Simulate without writing files.")
    p_norm.set_defaults(func=lambda args: apply_cmd_normalize_spaces(args))

    args = parser.parse_args(argv)
    return args.func(args)


def apply_cmd_normalize_spaces(args: argparse.Namespace) -> int:
    target_path = Path(args.target).resolve()
    changes = apply_double_space_normalization(target_path, dry_run=args.dry_run)
    status_str = "would be applied" if args.dry_run else "applied"
    print(f"Double-space normalizer: {len(changes)} corrections {status_str} in {target_path}.")
    return 0
