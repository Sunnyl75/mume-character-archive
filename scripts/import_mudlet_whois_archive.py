#!/usr/bin/env python3
"""
Import Mudlet MUME whois archive JSON into the MUME Character Archive.

This script reads the JSON produced by the Mudlet whois archive script, such as:

    /Users/Lewis/.config/mudlet/profiles/Multi-Users in Middle-earth/mume_whois_archive.json

It updates these repository files:

    data/working/sources.csv
    data/working/characters.csv
    data/working/whois_records.csv
    data/working/whois_queue.csv

It preserves each capture as a row in whois_records.csv and uses each record's
latest parsed block to update the character summary fields.

Run from the repository root:

    python3 scripts/import_mudlet_whois_archive.py "/Users/Lewis/.config/mudlet/profiles/Multi-Users in Middle-earth/mume_whois_archive.json"

Useful options:

    --dry-run
        Show what would be imported without writing files.

    --source-id SOURCE_ID
        Override the source_id used in sources.csv.

    --source-title TITLE
        Override the source title used in sources.csv.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKING_DIR = REPO_ROOT / "data" / "working"

SOURCES_CSV = WORKING_DIR / "sources.csv"
CHARACTERS_CSV = WORKING_DIR / "characters.csv"
WHOIS_RECORDS_CSV = WORKING_DIR / "whois_records.csv"
WHOIS_QUEUE_CSV = WORKING_DIR / "whois_queue.csv"

DEFAULT_SOURCE_ID = "source_mudlet_whois_archive"
DEFAULT_SOURCE_TITLE = "Mudlet MUME whois archive export"

SOURCE_FIELDS = [
    "source_id",
    "title",
    "source_type",
    "url",
    "date_found",
    "reliability",
    "notes",
]

CHARACTER_FIELDS = [
    "character_id",
    "name",
    "race",
    "class",
    "level",
    "status",
    "first_seen",
    "last_seen",
    "whois_checked",
    "duplicate_count",
    "notes",
]

WHOIS_RECORD_FIELDS = [
    "whois_id",
    "character_id",
    "character_name",
    "captured_at",
    "raw_text",
    "parsed_level",
    "parsed_race",
    "parsed_class",
    "status",
    "parse_confidence",
    "notes",
]

WHOIS_QUEUE_FIELDS = [
    "character_name",
    "character_id",
    "already_checked",
    "priority",
    "notes",
]


def clean(value: object) -> str:
    if value is None:
        return ""

    return str(value).strip()


def slugify_name(name: str) -> str:
    slug = name.casefold()
    slug = slug.replace(" ", "_")
    slug = re.sub(r"[^a-z0-9_à-ž-]+", "", slug, flags=re.IGNORECASE)
    slug = slug.replace("-", "_")
    slug = re.sub(r"_+", "_", slug).strip("_")

    if not slug:
        slug = "unknown"

    return slug


def make_character_id(name: str, existing_ids: set[str]) -> str:
    base = f"char_{slugify_name(name)}"
    candidate = base
    counter = 2

    while candidate in existing_ids:
        candidate = f"{base}_{counter}"
        counter += 1

    existing_ids.add(candidate)
    return candidate


def make_whois_id(character_name: str, captured_epoch: str, index: int, existing_ids: set[str]) -> str:
    slug = slugify_name(character_name or "unknown")
    epoch = captured_epoch or f"capture_{index + 1:04d}"
    base = f"whois_{slug}_{epoch}"
    candidate = base
    counter = 2

    while candidate in existing_ids:
        candidate = f"{base}_{counter}"
        counter += 1

    existing_ids.add(candidate)
    return candidate


def read_csv(path: Path, fields: list[str]) -> list[dict[str, str]]:
    if not path.exists():
        return []

    with path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = []

        for row in reader:
            rows.append({field: clean(row.get(field)) for field in fields})

        return rows


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()

        for row in rows:
            writer.writerow({field: clean(row.get(field)) for field in fields})


def load_archive(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError("Mudlet whois archive JSON must contain a top-level object")

    if "captures" not in data:
        raise ValueError("Mudlet whois archive JSON is missing top-level 'captures'")

    if "records" not in data:
        raise ValueError("Mudlet whois archive JSON is missing top-level 'records'")

    return data


def is_not_found_capture(capture: dict[str, Any]) -> bool:
    raw = clean(capture.get("raw_text"))
    parsed = capture.get("parsed") if isinstance(capture.get("parsed"), dict) else {}
    header = clean(parsed.get("header"))

    return raw.casefold().startswith("no one by that name") or header.casefold().startswith("no one by that name")


def looks_corrupt(parsed: dict[str, Any], raw_text: str) -> bool:
    header = clean(parsed.get("header"))
    display_name = clean(parsed.get("display_name"))
    character_name = clean(parsed.get("character_name"))

    if "MUME.Client protocol error" in raw_text:
        return True

    if "MUME.Client protocol error" in header:
        return True

    if "MUME.Client protocol error" in display_name:
        return True

    if character_name.casefold() == "mume":
        return True

    return False


def best_character_name_from_capture(capture: dict[str, Any]) -> str:
    parsed = capture.get("parsed") if isinstance(capture.get("parsed"), dict) else {}

    if isinstance(parsed, dict):
        name = clean(parsed.get("character_name"))
        if name:
            return name

    return clean(capture.get("query_name"))


def best_captured_at(capture: dict[str, Any]) -> str:
    return (
        clean(capture.get("captured_at"))
        or clean(capture.get("captured_datetime"))
        or clean(capture.get("captured_date"))
    )


def merge_note(existing: str, addition: str) -> str:
    existing = clean(existing)
    addition = clean(addition)

    if not addition:
        return existing

    if not existing:
        return addition

    if addition in existing:
        return existing

    return f"{existing} | {addition}"


def upsert_source(rows: list[dict[str, str]], source_id: str, source_title: str, archive_path: Path) -> None:
    today = datetime.now().date().isoformat()

    for row in rows:
        if clean(row.get("source_id")) == source_id:
            row["title"] = row.get("title") or source_title
            row["source_type"] = row.get("source_type") or "whois_archive"
            row["date_found"] = row.get("date_found") or today
            row["reliability"] = row.get("reliability") or "direct_mudlet_capture"
            row["notes"] = merge_note(
                row.get("notes", ""),
                f"Imported from Mudlet whois archive JSON: {archive_path}",
            )
            return

    rows.append(
        {
            "source_id": source_id,
            "title": source_title,
            "source_type": "whois_archive",
            "url": "",
            "date_found": today,
            "reliability": "direct_mudlet_capture",
            "notes": f"Imported from Mudlet whois archive JSON: {archive_path}",
        }
    )


def import_captures(
    archive: dict[str, Any],
    characters: list[dict[str, str]],
    whois_records: list[dict[str, str]],
    whois_queue: list[dict[str, str]],
) -> dict[str, int]:
    existing_character_ids = {clean(row.get("character_id")) for row in characters if clean(row.get("character_id"))}
    character_by_name = {
        clean(row.get("name")).casefold(): row
        for row in characters
        if clean(row.get("name"))
    }

    existing_whois_ids = {clean(row.get("whois_id")) for row in whois_records if clean(row.get("whois_id"))}
    existing_capture_keys = {
        (
            clean(row.get("character_name")).casefold(),
            clean(row.get("captured_at")),
            clean(row.get("raw_text")),
        )
        for row in whois_records
    }

    queue_by_character_id = {
        clean(row.get("character_id")): row
        for row in whois_queue
        if clean(row.get("character_id"))
    }
    queue_by_name = {
        clean(row.get("character_name")).casefold(): row
        for row in whois_queue
        if clean(row.get("character_name"))
    }

    captures = archive.get("captures") or []
    records = archive.get("records") or {}

    added_whois_records = 0
    added_characters = 0
    updated_characters = 0
    marked_queue_checked = 0
    skipped_duplicate_captures = 0
    not_found_captures = 0
    corrupt_captures = 0

    # Import every capture as preserved whois evidence.
    for index, capture in enumerate(captures):
        if not isinstance(capture, dict):
            continue

        parsed = capture.get("parsed") if isinstance(capture.get("parsed"), dict) else {}
        raw_text = clean(capture.get("raw_text"))
        character_name = best_character_name_from_capture(capture)
        captured_at = best_captured_at(capture)

        duplicate_key = (character_name.casefold(), captured_at, raw_text)
        if duplicate_key in existing_capture_keys:
            skipped_duplicate_captures += 1
            continue

        not_found = is_not_found_capture(capture)
        corrupt = looks_corrupt(parsed, raw_text) if isinstance(parsed, dict) else False

        if not_found:
            not_found_captures += 1

        if corrupt:
            corrupt_captures += 1

        character_row = character_by_name.get(character_name.casefold())
        character_id = clean(character_row.get("character_id")) if character_row else ""

        parse_confidence = "medium"
        status = clean(parsed.get("status")) if isinstance(parsed, dict) else ""

        if not_found:
            parse_confidence = "high"
            status = "not_found"
        elif corrupt:
            parse_confidence = "low"

        notes = []
        query_name = clean(capture.get("query_name"))
        display_name = clean(parsed.get("display_name")) if isinstance(parsed, dict) else ""
        epithet = clean(parsed.get("epithet_or_title")) if isinstance(parsed, dict) else ""
        role = clean(parsed.get("role")) if isinstance(parsed, dict) else ""
        last_login = clean(parsed.get("last_login_text")) if isinstance(parsed, dict) else ""

        if query_name:
            notes.append(f"query_name={query_name}")
        if display_name:
            notes.append(f"display_name={display_name}")
        if epithet:
            notes.append(f"epithet_or_title={epithet}")
        if role:
            notes.append(f"role={role}")
        if last_login:
            notes.append(last_login)
        if not_found:
            notes.append("MUME returned: No one by that name.")
        if corrupt:
            notes.append("Capture appears to include protocol/output corruption; raw text preserved.")

        whois_id = make_whois_id(
            character_name=character_name,
            captured_epoch=clean(capture.get("captured_epoch")),
            index=index,
            existing_ids=existing_whois_ids,
        )

        whois_records.append(
            {
                "whois_id": whois_id,
                "character_id": character_id,
                "character_name": character_name,
                "captured_at": captured_at,
                "raw_text": raw_text,
                "parsed_level": clean(parsed.get("level")) if isinstance(parsed, dict) else "",
                "parsed_race": clean(parsed.get("race")) if isinstance(parsed, dict) else "",
                "parsed_class": clean(parsed.get("class")) if isinstance(parsed, dict) else "",
                "status": status,
                "parse_confidence": parse_confidence,
                "notes": " | ".join(notes),
            }
        )

        existing_capture_keys.add(duplicate_key)
        added_whois_records += 1

    # Use records.latest for current character summary updates.
    for _record_key, record in records.items():
        if not isinstance(record, dict):
            continue

        latest = record.get("latest")
        if not isinstance(latest, dict):
            continue

        raw_summary = clean(latest.get("header")) + "\n" + clean(latest.get("body_text"))
        if looks_corrupt(latest, raw_summary):
            continue

        character_name = clean(latest.get("character_name"))
        if not character_name:
            continue

        # Do not create character records for "No one by that name."
        if clean(latest.get("header")).casefold().startswith("no one by that name"):
            continue

        key = character_name.casefold()
        character_row = character_by_name.get(key)

        if character_row is None:
            character_id = make_character_id(character_name, existing_character_ids)
            character_row = {
                "character_id": character_id,
                "name": character_name,
                "race": "",
                "class": "",
                "level": "",
                "status": "",
                "first_seen": "",
                "last_seen": "",
                "whois_checked": "",
                "duplicate_count": "",
                "notes": "",
            }
            characters.append(character_row)
            character_by_name[key] = character_row
            added_characters += 1
        else:
            updated_characters += 1

        before = dict(character_row)

        character_row["race"] = clean(latest.get("race")) or character_row.get("race", "")
        character_row["class"] = clean(latest.get("class")) or character_row.get("class", "")
        character_row["level"] = clean(latest.get("level")) or character_row.get("level", "")
        character_row["status"] = clean(latest.get("status")) or character_row.get("status", "")
        character_row["whois_checked"] = "true"

        captured_date = clean(latest.get("captured_date"))
        last_login_date = clean(latest.get("last_login_estimated_date"))

        if last_login_date:
            if not clean(character_row.get("first_seen")):
                character_row["first_seen"] = last_login_date
            if not clean(character_row.get("last_seen")):
                character_row["last_seen"] = last_login_date

        note_bits = []
        display_name = clean(latest.get("display_name"))
        epithet = clean(latest.get("epithet_or_title"))
        descriptor = clean(latest.get("descriptor"))
        last_login_text = clean(latest.get("last_login_text"))

        if display_name and display_name != character_name:
            note_bits.append(f"whois display_name={display_name}")
        if epithet:
            note_bits.append(f"whois epithet_or_title={epithet}")
        if descriptor:
            note_bits.append(f"whois descriptor={descriptor}")
        if last_login_text:
            note_bits.append(last_login_text)
        if captured_date:
            note_bits.append(f"whois captured_date={captured_date}")

        for bit in note_bits:
            character_row["notes"] = merge_note(character_row.get("notes", ""), bit)

        character_id = clean(character_row.get("character_id"))
        queue_row = queue_by_character_id.get(character_id) or queue_by_name.get(character_name.casefold())
        if queue_row is not None and clean(queue_row.get("already_checked")).casefold() not in {"true", "yes", "1"}:
            queue_row["already_checked"] = "true"
            queue_row["notes"] = merge_note(queue_row.get("notes", ""), "whois imported from Mudlet archive")
            marked_queue_checked += 1

    return {
        "added_whois_records": added_whois_records,
        "added_characters": added_characters,
        "updated_characters": updated_characters,
        "marked_queue_checked": marked_queue_checked,
        "skipped_duplicate_captures": skipped_duplicate_captures,
        "not_found_captures": not_found_captures,
        "corrupt_captures": corrupt_captures,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import Mudlet mume_whois_archive.json into repository CSV files"
    )

    parser.add_argument(
        "archive_json",
        type=Path,
        help="Path to mume_whois_archive.json",
    )

    parser.add_argument(
        "--source-id",
        default=DEFAULT_SOURCE_ID,
        help=f"Source ID to add/use in sources.csv. Default: {DEFAULT_SOURCE_ID}",
    )

    parser.add_argument(
        "--source-title",
        default=DEFAULT_SOURCE_TITLE,
        help=f"Source title to add/use in sources.csv. Default: {DEFAULT_SOURCE_TITLE}",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Inspect and report changes without writing files.",
    )

    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    try:
        archive = load_archive(args.archive_json)

        sources = read_csv(SOURCES_CSV, SOURCE_FIELDS)
        characters = read_csv(CHARACTERS_CSV, CHARACTER_FIELDS)
        whois_records = read_csv(WHOIS_RECORDS_CSV, WHOIS_RECORD_FIELDS)
        whois_queue = read_csv(WHOIS_QUEUE_CSV, WHOIS_QUEUE_FIELDS)

        upsert_source(
            rows=sources,
            source_id=args.source_id,
            source_title=args.source_title,
            archive_path=args.archive_json,
        )

        summary = import_captures(
            archive=archive,
            characters=characters,
            whois_records=whois_records,
            whois_queue=whois_queue,
        )

        print("Mudlet whois archive import")
        print("=" * 32)
        print(f"Archive version:          {archive.get('version', '')}")
        print(f"Archive records:          {len(archive.get('records') or {})}")
        print(f"Archive captures:         {len(archive.get('captures') or [])}")
        print(f"Added whois records:      {summary['added_whois_records']}")
        print(f"Added characters:         {summary['added_characters']}")
        print(f"Updated characters:       {summary['updated_characters']}")
        print(f"Marked queue checked:     {summary['marked_queue_checked']}")
        print(f"Skipped duplicate caps:   {summary['skipped_duplicate_captures']}")
        print(f"Not-found captures:       {summary['not_found_captures']}")
        print(f"Corrupt/low-conf captures:{summary['corrupt_captures']}")

        if args.dry_run:
            print()
            print("Dry run only: no files written.")
            return 0

        write_csv(SOURCES_CSV, SOURCE_FIELDS, sources)
        write_csv(CHARACTERS_CSV, CHARACTER_FIELDS, characters)
        write_csv(WHOIS_RECORDS_CSV, WHOIS_RECORD_FIELDS, whois_records)
        write_csv(WHOIS_QUEUE_CSV, WHOIS_QUEUE_FIELDS, whois_queue)

        print()
        print("Updated:")
        print(f"  {SOURCES_CSV.relative_to(REPO_ROOT)}")
        print(f"  {CHARACTERS_CSV.relative_to(REPO_ROOT)}")
        print(f"  {WHOIS_RECORDS_CSV.relative_to(REPO_ROOT)}")
        print(f"  {WHOIS_QUEUE_CSV.relative_to(REPO_ROOT)}")

    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
