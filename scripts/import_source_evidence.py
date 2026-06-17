#!/usr/bin/env python3
"""
Register an ad hoc source and optionally import rows from a CSV as evidence.

This is intended for historical MUME evidence that does not yet deserve a
special-purpose parser, but still needs to be recorded with source metadata.

Examples:

  python3 scripts/import_source_evidence.py \
    --source-id 2026_06_16_current_immortals \
    --title "MUME current immortal list" \
    --source-type in_game_immortal_list \
    --source-command "view wizlist" \
    --date-observed 2026-06-16 \
    --notes "Copied by Lewis; (+m) means Maiar Muddler." \
    --input data/incoming/immortals/2026_06_16/current_immortals_2026_06_16.csv \
    --evidence-type immortal_status \
    --subject-type character \
    --subject-column character_key \
    --claim-template "{display_name} is listed as a {immortal_category} in the current MUME immortal list." \
    --location-template "row {row_number}; source_order={source_order}" \
    --raw-columns display_name,immortal_status,immortal_category,is_maiar_muddler,honorary_immortal,evidence_kind,notes \
    --confidence medium \
    --date-confidence exact

The script upserts data/working/sources.csv by source_id and appends/updates
matching rows in data/working/evidence.csv using deterministic evidence IDs.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
from datetime import date
from pathlib import Path
from string import Formatter
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKING = REPO_ROOT / "data" / "working"
SOURCES_CSV = WORKING / "sources.csv"
EVIDENCE_CSV = WORKING / "evidence.csv"

SOURCE_FIELDS = [
    "source_id",
    "title",
    "source_type",
    "url",
    "date_found",
    "reliability",
    "notes",
]

EVIDENCE_FIELDS = [
    "evidence_id",
    "source_id",
    "evidence_type",
    "subject_type",
    "subject_id_or_name",
    "claim",
    "raw_text",
    "location_in_source",
    "date_observed",
    "date_range_start",
    "date_range_end",
    "date_confidence",
    "confidence",
    "notes",
]


def clean(value: object) -> str:
    return str(value or "").strip()


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def fieldnames_for(path: Path, fallback: list[str]) -> list[str]:
    if not path.exists():
        return list(fallback)
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or fallback)


def write_csv(path: Path, rows: Iterable[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: clean(row.get(field)) for field in fieldnames})


def parse_csv_list(value: str) -> list[str]:
    return [item.strip() for item in clean(value).split(",") if item.strip()]


def slug(value: str) -> str:
    value = clean(value).casefold()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = value.strip("_")
    return value or "source"


def stable_evidence_id(source_id: str, evidence_type: str, subject: str, location: str, claim: str) -> str:
    base = "|".join([source_id, evidence_type, subject, location, claim])
    digest = hashlib.sha1(base.encode("utf-8")).hexdigest()[:12]
    return f"evidence_{slug(source_id)}_{digest}"


def today_iso() -> str:
    return date.today().isoformat()


def validate_template(template: str, available: set[str], label: str) -> None:
    for _, field_name, _, _ in Formatter().parse(template):
        if not field_name:
            continue
        root = field_name.split(".")[0].split("[")[0]
        if root not in available:
            raise SystemExit(f"{label} references unknown field {{{field_name}}}. Available fields include: {', '.join(sorted(available))}")


def format_template(template: str, row: dict[str, str]) -> str:
    try:
        return template.format(**row)
    except KeyError as exc:
        raise SystemExit(f"Template references missing field: {exc}") from exc


def upsert_source(args: argparse.Namespace) -> None:
    sources = read_csv(SOURCES_CSV)
    fields = fieldnames_for(SOURCES_CSV, SOURCE_FIELDS)
    for field in SOURCE_FIELDS:
        if field not in fields:
            fields.append(field)

    source_row = {
        "source_id": args.source_id,
        "title": args.title or args.source_name or args.source_id,
        "source_type": args.source_type,
        "url": args.url,
        "date_found": args.date_found or args.date_observed or today_iso(),
        "reliability": args.reliability,
        "notes": args.notes,
    }

    if args.source_command:
        extra = f"source_command={args.source_command}"
        source_row["notes"] = (source_row["notes"] + " | " + extra).strip(" |")
    if args.source_date_context:
        extra = f"source_date_context={args.source_date_context}"
        source_row["notes"] = (source_row["notes"] + " | " + extra).strip(" |")

    replaced = False
    out = []
    for row in sources:
        if clean(row.get("source_id")) == args.source_id:
            merged = dict(row)
            for key, value in source_row.items():
                if clean(value):
                    merged[key] = value
            out.append(merged)
            replaced = True
        else:
            out.append(row)
    if not replaced:
        out.append(source_row)

    write_csv(SOURCES_CSV, out, fields)
    action = "Updated" if replaced else "Added"
    print(f"{action} source {args.source_id} in {rel(SOURCES_CSV)}")


def import_evidence(args: argparse.Namespace) -> None:
    input_path = (REPO_ROOT / args.input).resolve() if args.input else None
    if not input_path or not input_path.exists():
        raise SystemExit(f"Missing input CSV: {args.input}")

    with input_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        input_fields = list(reader.fieldnames or [])
        input_rows = list(reader)

    if args.subject_column not in input_fields:
        raise SystemExit(f"Subject column '{args.subject_column}' not found in {rel(input_path)}")

    available = set(input_fields) | {"row_number"}
    validate_template(args.claim_template, available, "--claim-template")
    if args.location_template:
        validate_template(args.location_template, available, "--location-template")

    raw_columns = parse_csv_list(args.raw_columns)
    for col in raw_columns:
        if col not in input_fields:
            raise SystemExit(f"Raw column '{col}' not found in {rel(input_path)}")

    evidence_rows = read_csv(EVIDENCE_CSV)
    fields = fieldnames_for(EVIDENCE_CSV, EVIDENCE_FIELDS)
    for field in EVIDENCE_FIELDS:
        if field not in fields:
            fields.append(field)

    by_id = {clean(row.get("evidence_id")): row for row in evidence_rows if clean(row.get("evidence_id"))}
    ordered_ids = [clean(row.get("evidence_id")) for row in evidence_rows if clean(row.get("evidence_id"))]

    imported = 0
    updated = 0
    skipped = 0

    for idx, row in enumerate(input_rows, start=2):
        row = {k: clean(v) for k, v in row.items()}
        row["row_number"] = str(idx)
        subject = clean(row.get(args.subject_column))
        if not subject:
            skipped += 1
            continue

        claim = format_template(args.claim_template, row)
        location = format_template(args.location_template, row) if args.location_template else f"{rel(input_path)} row {idx}"
        raw_text = " | ".join(f"{col}={row.get(col, '')}" for col in raw_columns) if raw_columns else ", ".join(f"{k}={v}" for k, v in row.items() if v)

        evidence_id = stable_evidence_id(args.source_id, args.evidence_type, subject, location, claim)
        evidence_row = {
            "evidence_id": evidence_id,
            "source_id": args.source_id,
            "evidence_type": args.evidence_type,
            "subject_type": args.subject_type,
            "subject_id_or_name": subject,
            "claim": claim,
            "raw_text": raw_text,
            "location_in_source": location,
            "date_observed": args.date_observed,
            "date_range_start": args.date_range_start,
            "date_range_end": args.date_range_end,
            "date_confidence": args.date_confidence,
            "confidence": args.confidence,
            "notes": args.evidence_notes or row.get("notes", ""),
        }

        if evidence_id in by_id:
            by_id[evidence_id].update({k: v for k, v in evidence_row.items() if k in fields})
            updated += 1
        else:
            by_id[evidence_id] = evidence_row
            ordered_ids.append(evidence_id)
            imported += 1

    write_csv(EVIDENCE_CSV, [by_id[eid] for eid in ordered_ids if eid in by_id], fields)
    print(f"Imported evidence from {rel(input_path)} into {rel(EVIDENCE_CSV)}")
    print(f"  added: {imported}")
    print(f"  updated: {updated}")
    print(f"  skipped blank subject: {skipped}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Register an ad hoc MUME source and optionally import CSV rows as evidence.")
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--title", default="")
    parser.add_argument("--source-name", default="")
    parser.add_argument("--source-type", required=True)
    parser.add_argument("--url", default="")
    parser.add_argument("--source-command", default="")
    parser.add_argument("--source-date-context", default="")
    parser.add_argument("--date-found", default="")
    parser.add_argument("--reliability", default="candidate_source")
    parser.add_argument("--notes", default="")

    parser.add_argument("--input", default="", help="Optional CSV to import as evidence.")
    parser.add_argument("--evidence-type", default="source_row")
    parser.add_argument("--subject-type", default="character")
    parser.add_argument("--subject-column", default="character_key")
    parser.add_argument("--claim-template", default="{character_key} is mentioned in this source.")
    parser.add_argument("--location-template", default="row {row_number}")
    parser.add_argument("--raw-columns", default="")
    parser.add_argument("--date-observed", default="")
    parser.add_argument("--date-range-start", default="")
    parser.add_argument("--date-range-end", default="")
    parser.add_argument("--date-confidence", default="unknown")
    parser.add_argument("--confidence", default="medium")
    parser.add_argument("--evidence-notes", default="")
    parser.add_argument("--register-only", action="store_true")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    upsert_source(args)
    if args.register_only or not args.input:
        return
    import_evidence(args)


if __name__ == "__main__":
    main()
