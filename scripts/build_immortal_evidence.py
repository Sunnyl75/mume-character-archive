#!/usr/bin/env python3
"""
Build structured immortal-list evidence from incoming immortal source files.

Inputs:
  data/incoming/immortals/*/source_metadata.csv
  data/incoming/immortals/*/*immortals*.csv
  data/working/characters.csv
  data/working/whois_records.csv

Outputs:
  data/derived/character_immortal_evidence.csv
  reports/immortal_evidence_summary.md
  reports/queries/immortal_evidence_candidates.csv
  reports/queries/immortal_whois_queue_candidates.csv
  exports/mudlet/immortal_whois_queue.txt

This script records source-list evidence separately from whois-derived immortal
classification. A character can be listed as a current/retired/honorary immortal
without the parser having inferred the same thing from their whois text.
"""

from __future__ import annotations

import csv
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
INCOMING_ROOT = ROOT / "data" / "incoming" / "immortals"
CHARACTERS_CSV = ROOT / "data" / "working" / "characters.csv"
WHOIS_CSV = ROOT / "data" / "working" / "whois_records.csv"
SOURCES_CSV = ROOT / "data" / "working" / "sources.csv"
EVIDENCE_CSV = ROOT / "data" / "working" / "evidence.csv"

DERIVED_OUT = ROOT / "data" / "derived" / "character_immortal_evidence.csv"
SUMMARY_OUT = ROOT / "reports" / "immortal_evidence_summary.md"
QUERY_OUT = ROOT / "reports" / "queries" / "immortal_evidence_candidates.csv"
QUEUE_CSV_OUT = ROOT / "reports" / "queries" / "immortal_whois_queue_candidates.csv"
QUEUE_TXT_OUT = ROOT / "exports" / "mudlet" / "immortal_whois_queue.txt"

SOURCE_FIELDS = ["source_id", "title", "source_type", "url", "date_found", "reliability", "notes"]
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

OUTPUT_FIELDS = [
    "immortal_evidence_id",
    "character_id",
    "character_key",
    "display_name",
    "source_character_name",
    "immortal_status",
    "immortal_category",
    "is_maiar_muddler",
    "honorary_immortal",
    "evidence_kind",
    "source_id",
    "source_name",
    "source_type",
    "source_url",
    "source_command",
    "source_date_context",
    "source_order",
    "evidence_excerpt",
    "confidence",
    "review_status",
    "notes",
]

QUEUE_FIELDS = [
    "character_key",
    "display_name",
    "immortal_status",
    "immortal_category",
    "is_maiar_muddler",
    "honorary_immortal",
    "known_character_id",
    "whois_checked",
    "reason",
    "source_id",
    "source_name",
    "source_date_context",
    "notes",
]

CATEGORY_CANONICAL = {
    "implementors": "Implementor",
    "implementor": "Implementor",
    "aratar": "Aratar",
    "valar": "Vala",
    "vala": "Vala",
    "maiar": "Maia",
    "maia": "Maia",
    "boardreaders": "Boardreader",
    "boardreader": "Boardreader",
    "true legend": "True Legend",
}

STATUS_PRIORITY = {
    "current": 30,
    "honorary": 25,
    "retired": 20,
    "former": 20,
    "unknown": 0,
}

CATEGORY_PRIORITY = {
    "Implementor": 70,
    "Aratar": 60,
    "Vala": 50,
    "Maia": 40,
    "Boardreader": 30,
    "True Legend": 20,
    "": 0,
}


def clean(value: object) -> str:
    return str(value or "").strip()


def yes(value: object) -> bool:
    return clean(value).casefold() in {"yes", "true", "1", "y"}


def strip_accents(value: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", value) if not unicodedata.combining(ch))


def norm_name(value: str) -> str:
    return strip_accents(clean(value)).casefold()


def slug(value: str) -> str:
    value = strip_accents(clean(value)).casefold()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = value.strip("_")
    return value or "immortal"


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def read_csv_required(path: Path) -> list[dict[str, str]]:
    rows = read_csv(path)
    if not path.exists():
        raise SystemExit(f"Missing required file: {path}")
    return rows


def fieldnames_for(path: Path, fallback: list[str]) -> list[str]:
    if not path.exists():
        return list(fallback)
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or fallback)


def write_csv(path: Path, rows: Iterable[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def canonical_category(value: str) -> str:
    return CATEGORY_CANONICAL.get(clean(value).casefold(), clean(value))


def date_from_context(value: str) -> str:
    text = clean(value)
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    return match.group(1) + "-" + match.group(2) + "-" + match.group(3) if match else ""


def metadata_by_source() -> dict[str, dict[str, str]]:
    meta: dict[str, dict[str, str]] = {}
    if not INCOMING_ROOT.exists():
        return meta
    for path in sorted(INCOMING_ROOT.glob("*/source_metadata.csv")):
        for row in read_csv(path):
            sid = clean(row.get("source_id"))
            if not sid:
                continue
            meta[sid] = {
                "source_id": sid,
                "source_name": clean(row.get("source_name") or row.get("title")),
                "source_type": clean(row.get("source_type")),
                "source_url": clean(row.get("source_url") or row.get("url")),
                "source_command": clean(row.get("source_command")),
                "source_date_context": clean(row.get("source_date_context")),
                "notes": clean(row.get("notes") or row.get("source_notes")),
            }
    return meta


def upsert_sources(metadata: dict[str, dict[str, str]]) -> None:
    existing = read_csv(SOURCES_CSV)
    fields = fieldnames_for(SOURCES_CSV, SOURCE_FIELDS)
    for field in SOURCE_FIELDS:
        if field not in fields:
            fields.append(field)

    by_id = {clean(row.get("source_id")): row for row in existing if clean(row.get("source_id"))}
    order = [clean(row.get("source_id")) for row in existing if clean(row.get("source_id"))]

    for sid, meta in sorted(metadata.items()):
        source_notes = clean(meta.get("notes"))
        if meta.get("source_command"):
            source_notes = (source_notes + f" | source_command={meta['source_command']}").strip(" |")
        if meta.get("source_date_context"):
            source_notes = (source_notes + f" | source_date_context={meta['source_date_context']}").strip(" |")
        row = {
            "source_id": sid,
            "title": meta.get("source_name") or sid,
            "source_type": meta.get("source_type", "immortal_list"),
            "url": meta.get("source_url", ""),
            "date_found": date_from_context(meta.get("source_date_context", "")),
            "reliability": "direct_game_list_copy",
            "notes": source_notes,
        }
        if sid in by_id:
            merged = dict(by_id[sid])
            for key, value in row.items():
                if clean(value):
                    merged[key] = value
            by_id[sid] = merged
        else:
            by_id[sid] = row
            order.append(sid)

    write_csv(SOURCES_CSV, [by_id[sid] for sid in order if sid in by_id], fields)


def append_working_evidence(rows: list[dict[str, str]]) -> None:
    existing = read_csv(EVIDENCE_CSV)
    fields = fieldnames_for(EVIDENCE_CSV, EVIDENCE_FIELDS)
    for field in EVIDENCE_FIELDS:
        if field not in fields:
            fields.append(field)

    by_id = {clean(row.get("evidence_id")): row for row in existing if clean(row.get("evidence_id"))}
    order = [clean(row.get("evidence_id")) for row in existing if clean(row.get("evidence_id"))]

    for row in rows:
        evidence_id = clean(row.get("evidence_id"))
        if not evidence_id:
            continue
        if evidence_id not in by_id:
            order.append(evidence_id)
        by_id[evidence_id] = row

    write_csv(EVIDENCE_CSV, [by_id[eid] for eid in order if eid in by_id], fields)


def incoming_immortal_files() -> list[Path]:
    if not INCOMING_ROOT.exists():
        return []
    out = []
    for path in sorted(INCOMING_ROOT.glob("*/*.csv")):
        if path.name == "source_metadata.csv":
            continue
        name = path.name.casefold()
        if "queue" in name or "candidate" in name or "summary" in name:
            continue
        if "immortal" in name:
            out.append(path)
    return out


def evidence_id_for(row: dict[str, str]) -> str:
    sid = slug(row.get("source_id", ""))
    key = slug(row.get("character_key", ""))
    order = slug(row.get("source_order", ""))
    kind = slug(row.get("evidence_kind", ""))
    return f"immortal_{sid}_{key}_{order}_{kind}".strip("_")


def claim_for(row: dict[str, str]) -> str:
    name = clean(row.get("display_name") or row.get("character_key"))
    status = clean(row.get("immortal_status"))
    category = canonical_category(row.get("immortal_category", ""))
    parts = [f"{name} is listed"]
    if status:
        parts.append(f"as {status}")
    if category:
        article = "an" if category[:1].lower() in {"a", "i"} else "a"
        parts.append(f"{article} {category}")
    text = " ".join(parts) + "."
    extras = []
    if yes(row.get("is_maiar_muddler")):
        extras.append("Maiar Muddler / code contributor marker present")
    if yes(row.get("honorary_immortal")):
        extras.append("honorary immortal marker present")
    if extras:
        text += " " + "; ".join(extras) + "."
    return text


def row_priority(row: dict[str, str]) -> int:
    return STATUS_PRIORITY.get(clean(row.get("immortal_status")).casefold(), 0) + CATEGORY_PRIORITY.get(clean(row.get("immortal_category")), 0)



def ensure_character_rows(source_rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], dict[str, dict[str, str]]]:
    """Ensure every immortal-list name has a character row.

    Whois evidence remains stronger, but list-only names such as Eru/Manwë
    still need a character shell so the Deck of Chars export can show them and
    attach weaker source-list evidence while awaiting/repairing whois capture.
    """
    characters = read_csv_required(CHARACTERS_CSV)
    fields = fieldnames_for(CHARACTERS_CSV, [
        "character_id", "name", "race", "class", "level", "status",
        "first_seen", "last_seen", "whois_checked", "duplicate_count", "notes",
    ])
    for field in ["character_id", "name", "race", "class", "level", "status", "first_seen", "last_seen", "whois_checked", "duplicate_count", "notes"]:
        if field not in fields:
            fields.append(field)

    by_norm = {norm_name(row.get("name", "")): row for row in characters if clean(row.get("name"))}
    existing_ids = {clean(row.get("character_id")) for row in characters if clean(row.get("character_id"))}
    added = 0

    for row in source_rows:
        key = clean(row.get("character_key") or row.get("display_name"))
        if not key:
            continue
        nkey = norm_name(key)
        if nkey in by_norm:
            continue

        base_id = "char_" + slug(key)
        cid = base_id
        counter = 2
        while cid in existing_ids:
            cid = f"{base_id}_{counter}"
            counter += 1

        notes = "created from immortal list evidence; awaiting/using whois import where available"
        new_row = {
            "character_id": cid,
            "name": clean(row.get("display_name") or key),
            "race": "",
            "class": "",
            "level": "",
            "status": clean(row.get("immortal_status")),
            "first_seen": "",
            "last_seen": "",
            "whois_checked": "false",
            "duplicate_count": "0",
            "notes": notes,
        }
        characters.append(new_row)
        by_norm[nkey] = new_row
        existing_ids.add(cid)
        added += 1

    if added:
        write_csv(CHARACTERS_CSV, characters, fields)

    return characters, by_norm


def main() -> None:
    metadata = metadata_by_source()
    if metadata:
        upsert_sources(metadata)

    source_rows_for_characters: list[dict[str, str]] = []
    for path in incoming_immortal_files():
        source_rows_for_characters.extend({k: clean(v) for k, v in row.items()} for row in read_csv(path))

    characters, char_by_name = ensure_character_rows(source_rows_for_characters)
    whois_rows = read_csv_required(WHOIS_CSV)
    whois_checked_names = {norm_name(row.get("character_name", "")) for row in whois_rows if clean(row.get("character_name"))}

    evidence_rows: list[dict[str, str]] = []
    working_evidence_rows: list[dict[str, str]] = []
    queue_by_key: dict[str, dict[str, str]] = {}

    for path in incoming_immortal_files():
        for row_number, row in enumerate(read_csv(path), start=2):
            row = {k: clean(v) for k, v in row.items()}
            key = clean(row.get("character_key") or row.get("display_name"))
            if not key:
                continue
            display = clean(row.get("display_name") or key)
            sid = clean(row.get("source_id"))
            meta = metadata.get(sid, {})
            char = char_by_name.get(norm_name(key), {})
            category = canonical_category(row.get("immortal_category", ""))
            evidence_id = evidence_id_for(row)
            confidence = "medium"
            if yes(row.get("honorary_immortal")):
                confidence = "medium"
            excerpt = claim_for({**row, "immortal_category": category})

            out = {
                "immortal_evidence_id": evidence_id,
                "character_id": clean(char.get("character_id")),
                "character_key": key,
                "display_name": display,
                "source_character_name": clean(char.get("name")),
                "immortal_status": clean(row.get("immortal_status")),
                "immortal_category": category,
                "is_maiar_muddler": "yes" if yes(row.get("is_maiar_muddler")) else "no",
                "honorary_immortal": "yes" if yes(row.get("honorary_immortal")) else "no",
                "evidence_kind": clean(row.get("evidence_kind")),
                "source_id": sid,
                "source_name": clean(meta.get("source_name")),
                "source_type": clean(meta.get("source_type")),
                "source_url": clean(meta.get("source_url")),
                "source_command": clean(meta.get("source_command")),
                "source_date_context": clean(meta.get("source_date_context")),
                "source_order": clean(row.get("source_order")),
                "evidence_excerpt": excerpt,
                "confidence": confidence,
                "review_status": clean(row.get("review_status") or "candidate"),
                "notes": clean(row.get("notes") or meta.get("notes")),
            }
            evidence_rows.append(out)

            date_observed = date_from_context(meta.get("source_date_context", ""))
            working_evidence_rows.append({
                "evidence_id": evidence_id,
                "source_id": sid,
                "evidence_type": "immortal_list_status",
                "subject_type": "character",
                "subject_id_or_name": key,
                "claim": excerpt,
                "raw_text": " | ".join(
                    f"{col}={row.get(col, '')}" for col in [
                        "display_name",
                        "immortal_status",
                        "immortal_category",
                        "is_maiar_muddler",
                        "honorary_immortal",
                        "evidence_kind",
                        "notes",
                    ] if row.get(col, "")
                ),
                "location_in_source": f"{path.relative_to(ROOT)} row {row_number}; source_order={row.get('source_order', '')}",
                "date_observed": date_observed,
                "date_range_start": date_observed,
                "date_range_end": "",
                "date_confidence": "exact" if date_observed else "unknown",
                "confidence": confidence,
                "notes": out["notes"],
            })

            queue_reason = "immortal source row"
            if not char:
                queue_reason += "; not yet in characters.csv"
            if norm_name(key) not in whois_checked_names:
                queue_reason += "; no imported whois record found"

            if norm_name(key) not in whois_checked_names:
                queue_row = {
                    "character_key": key,
                    "display_name": display,
                    "immortal_status": out["immortal_status"],
                    "immortal_category": out["immortal_category"],
                    "is_maiar_muddler": out["is_maiar_muddler"],
                    "honorary_immortal": out["honorary_immortal"],
                    "known_character_id": out["character_id"],
                    "whois_checked": "yes" if out["character_id"] else "no",
                    "reason": queue_reason,
                    "source_id": sid,
                    "source_name": out["source_name"],
                    "source_date_context": out["source_date_context"],
                    "notes": out["notes"],
                }
                old = queue_by_key.get(norm_name(key))
                if old is None or row_priority(queue_row) > row_priority(old):
                    queue_by_key[norm_name(key)] = queue_row

    evidence_rows = sorted(evidence_rows, key=lambda r: (norm_name(r["character_key"]), -row_priority(r), r["source_id"], r["source_order"]))
    write_csv(DERIVED_OUT, evidence_rows, OUTPUT_FIELDS)
    write_csv(QUERY_OUT, evidence_rows, OUTPUT_FIELDS)
    write_csv(QUEUE_CSV_OUT, sorted(queue_by_key.values(), key=lambda r: norm_name(r["character_key"])), QUEUE_FIELDS)

    QUEUE_TXT_OUT.parent.mkdir(parents=True, exist_ok=True)
    QUEUE_TXT_OUT.write_text("\n".join(r["character_key"] for r in sorted(queue_by_key.values(), key=lambda r: norm_name(r["character_key"]))) + ("\n" if queue_by_key else ""), encoding="utf-8")

    if working_evidence_rows:
        append_working_evidence(working_evidence_rows)

    counts_status = Counter(r["immortal_status"] or "(blank)" for r in evidence_rows)
    counts_category = Counter(r["immortal_category"] or "(blank)" for r in evidence_rows)
    counts_source = Counter(r["source_id"] or "(blank)" for r in evidence_rows)
    linked = sum(1 for r in evidence_rows if r["character_id"])
    muddler = sum(1 for r in evidence_rows if r["is_maiar_muddler"] == "yes")
    honorary = sum(1 for r in evidence_rows if r["honorary_immortal"] == "yes")

    lines = [
        "# Immortal Evidence Summary",
        "",
        f"Incoming immortal evidence rows: {len(evidence_rows)}",
        f"Rows linked to characters.csv: {linked}",
        f"Rows not yet linked to characters.csv: {len(evidence_rows) - linked}",
        f"Maiar Muddler markers: {muddler}",
        f"Honorary immortal markers: {honorary}",
        f"Mudlet queue candidates still without imported whois: {len(queue_by_key)}",
        "",
        "## Status counts",
        "",
    ]
    for value, count in counts_status.most_common():
        lines.append(f"- {value}: {count}")
    lines.extend(["", "## Category counts", ""])
    for value, count in counts_category.most_common():
        lines.append(f"- {value}: {count}")
    lines.extend(["", "## Source counts", ""])
    for value, count in counts_source.most_common():
        lines.append(f"- {value}: {count}")

    SUMMARY_OUT.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote {DERIVED_OUT.relative_to(ROOT)}")
    print(f"Wrote {SUMMARY_OUT.relative_to(ROOT)}")
    print(f"Wrote {QUERY_OUT.relative_to(ROOT)}")
    print(f"Wrote {QUEUE_CSV_OUT.relative_to(ROOT)}")
    print(f"Wrote {QUEUE_TXT_OUT.relative_to(ROOT)}")
    print(f"Incoming immortal evidence rows: {len(evidence_rows)}")
    print(f"Rows linked to characters.csv: {linked}")
    print(f"Mudlet queue candidates still without imported whois: {len(queue_by_key)}")


if __name__ == "__main__":
    main()
