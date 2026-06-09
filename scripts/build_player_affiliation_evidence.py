#!/usr/bin/env python3
"""
Build player-organised clan/guild/affiliation evidence from incoming source files.

This script intentionally keeps player-organised affiliations separate from built-in
MUME race, subrace, class, and faction classification.

Inputs:
  data/incoming/player_affiliations/2003_clans_webpage/player_affiliations.csv
  data/incoming/player_affiliations/2003_clans_webpage/player_affiliation_members.csv
  data/incoming/player_affiliations/2003_clans_webpage/player_affiliation_patterns.csv
  data/working/characters.csv
  data/working/whois_records.csv

Outputs:
  data/derived/character_player_affiliations.csv
  reports/player_affiliation_evidence_summary.md
  reports/queries/player_affiliation_candidates.csv
  reports/queries/player_affiliation_whois_queue_candidates.csv
  exports/mudlet/affiliation_whois_queue.txt
"""

from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "data" / "incoming" / "player_affiliations" / "2003_clans_webpage"
AFFILIATIONS_CSV = SOURCE_DIR / "player_affiliations.csv"
MEMBERS_CSV = SOURCE_DIR / "player_affiliation_members.csv"
PATTERNS_CSV = SOURCE_DIR / "player_affiliation_patterns.csv"
CHARACTERS_CSV = ROOT / "data" / "working" / "characters.csv"
WHOIS_CSV = ROOT / "data" / "working" / "whois_records.csv"

DERIVED_OUT = ROOT / "data" / "derived" / "character_player_affiliations.csv"
SUMMARY_OUT = ROOT / "reports" / "player_affiliation_evidence_summary.md"
QUERY_OUT = ROOT / "reports" / "queries" / "player_affiliation_candidates.csv"
QUEUE_CSV_OUT = ROOT / "reports" / "queries" / "player_affiliation_whois_queue_candidates.csv"
QUEUE_TXT_OUT = ROOT / "exports" / "mudlet" / "affiliation_whois_queue.txt"

OUTPUT_FIELDS = [
    "affiliation_id",
    "affiliation_name",
    "character_id",
    "character_key",
    "display_name",
    "name_suffix",
    "source_character_name",
    "role_title",
    "evidence_kind",
    "evidence_source",
    "source_whois_id",
    "evidence_excerpt",
    "confidence",
    "review_status",
    "notes",
]

QUEUE_FIELDS = [
    "character_key",
    "display_name",
    "name_suffix",
    "affiliation_id",
    "affiliation_name",
    "reason",
    "known_character_id",
    "whois_checked",
    "evidence_kind",
    "notes",
]


def read_csv(path: Path) -> List[dict]:
    if not path.exists():
        raise SystemExit(f"Missing required file: {path}")
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: Iterable[dict], fields: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def norm_name(value: str) -> str:
    return (value or "").strip().casefold()


def first_word(display_name: str) -> str:
    display_name = (display_name or "").strip()
    if not display_name:
        return ""
    return display_name.split()[0].strip(".,;:()[]{}\"'")


def truthy(value: str) -> bool:
    return (value or "").strip().casefold() in {"true", "yes", "1", "y"}


def confidence_for_member(kind: str) -> str:
    kind = (kind or "").strip().casefold()
    if kind in {"founder", "leader"}:
        return "medium_high"
    if kind in {"listed_member", "listed_contact"}:
        return "medium"
    if kind in {"alias_or_alternate_character"}:
        return "candidate"
    return "candidate"


def regex_for_pattern(pattern: str, pattern_type: str) -> Optional[re.Pattern]:
    pattern = (pattern or "").strip()
    if not pattern:
        return None
    escaped = re.escape(pattern)
    pattern_type = (pattern_type or "").strip().casefold()

    # Use loose non-word boundaries so apostrophes/accents/titles still work,
    # but avoid matching inside longer words.
    if pattern_type == "acronym":
        expr = rf"(?<![\w]){escaped}(?![\w])"
    elif len(pattern) <= 3:
        expr = rf"(?<![\w]){escaped}(?![\w])"
    else:
        expr = rf"(?<![\w]){escaped}(?![\w])"
    return re.compile(expr, re.IGNORECASE)


def excerpt(text: str, start: int, end: int, radius: int = 90) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    snippet = text[left:right].replace("\r", " ").replace("\n", " ")
    snippet = re.sub(r"\s+", " ", snippet).strip()
    if left > 0:
        snippet = "…" + snippet
    if right < len(text):
        snippet += "…"
    return snippet


def main() -> None:
    affiliations = read_csv(AFFILIATIONS_CSV)
    members = read_csv(MEMBERS_CSV)
    patterns = read_csv(PATTERNS_CSV)
    characters = read_csv(CHARACTERS_CSV)
    whois_records = read_csv(WHOIS_CSV)

    char_by_name: Dict[str, dict] = {norm_name(row.get("name", "")): row for row in characters if row.get("name")}
    char_by_id: Dict[str, dict] = {row.get("character_id", ""): row for row in characters if row.get("character_id")}
    aff_by_id: Dict[str, dict] = {row.get("affiliation_id", ""): row for row in affiliations}

    rows: List[dict] = []
    queue_rows_by_key: Dict[str, dict] = {}

    # 1. Direct historical evidence from the 2003 webpage member/contact lists.
    for member in members:
        key = (member.get("character_key") or first_word(member.get("display_name", ""))).strip()
        if not key:
            continue
        char = char_by_name.get(norm_name(key), {})
        aff_id = member.get("affiliation_id", "")
        aff = aff_by_id.get(aff_id, {})
        evidence_kind = member.get("evidence_kind", "listed_member")
        row = {
            "affiliation_id": aff_id,
            "affiliation_name": member.get("affiliation_name", ""),
            "character_id": char.get("character_id", ""),
            "character_key": key,
            "display_name": member.get("display_name", key),
            "name_suffix": member.get("name_suffix", ""),
            "source_character_name": char.get("name", ""),
            "role_title": member.get("role_title", ""),
            "evidence_kind": evidence_kind,
            "evidence_source": "2003_clans_webpage_member_list",
            "source_whois_id": "",
            "evidence_excerpt": aff.get("description_notes", ""),
            "confidence": confidence_for_member(evidence_kind),
            "review_status": member.get("review_status", "candidate") or "candidate",
            "notes": member.get("notes", ""),
        }
        rows.append(row)

        whois_checked = char.get("whois_checked", "")
        should_queue = not char or not truthy(whois_checked)
        if should_queue:
            reason = "not_in_characters" if not char else "known_character_without_whois"
            # Keep one queue row per searchable key, but retain the first provenance.
            queue_rows_by_key.setdefault(norm_name(key), {
                "character_key": key,
                "display_name": member.get("display_name", key),
                "name_suffix": member.get("name_suffix", ""),
                "affiliation_id": aff_id,
                "affiliation_name": member.get("affiliation_name", ""),
                "reason": reason,
                "known_character_id": char.get("character_id", ""),
                "whois_checked": whois_checked,
                "evidence_kind": evidence_kind,
                "notes": member.get("notes", ""),
            })

    # 2. Candidate evidence from matching known affiliation/title patterns in whois text.
    compiled_patterns = []
    for pattern_row in patterns:
        compiled = regex_for_pattern(pattern_row.get("pattern", ""), pattern_row.get("pattern_type", ""))
        if compiled is None:
            continue
        compiled_patterns.append((pattern_row, compiled))

    seen_pattern_hits = set()
    for whois in whois_records:
        raw_text = whois.get("raw_text", "") or ""
        if not raw_text.strip():
            continue
        character_name = whois.get("character_name", "")
        char_id = whois.get("character_id", "")
        char = char_by_id.get(char_id, {}) or char_by_name.get(norm_name(character_name), {})
        for pattern_row, compiled in compiled_patterns:
            match = compiled.search(raw_text)
            if not match:
                continue
            sig = (
                whois.get("whois_id", ""),
                pattern_row.get("affiliation_id", ""),
                pattern_row.get("pattern", ""),
            )
            if sig in seen_pattern_hits:
                continue
            seen_pattern_hits.add(sig)
            rows.append({
                "affiliation_id": pattern_row.get("affiliation_id", ""),
                "affiliation_name": pattern_row.get("affiliation_name", ""),
                "character_id": char_id or char.get("character_id", ""),
                "character_key": character_name or char.get("name", ""),
                "display_name": character_name or char.get("name", ""),
                "name_suffix": "",
                "source_character_name": character_name,
                "role_title": "",
                "evidence_kind": f"whois_{pattern_row.get('pattern_type', 'pattern')}_match",
                "evidence_source": "whois_records_raw_text",
                "source_whois_id": whois.get("whois_id", ""),
                "evidence_excerpt": excerpt(raw_text, match.start(), match.end()),
                "confidence": pattern_row.get("confidence_default", "candidate") or "candidate",
                "review_status": "candidate",
                "notes": pattern_row.get("notes", ""),
            })

    # Sort for stable diffs.
    rows.sort(key=lambda r: (
        r.get("affiliation_name", "").casefold(),
        r.get("character_key", "").casefold(),
        r.get("evidence_source", ""),
        r.get("source_whois_id", ""),
    ))
    queue_rows = sorted(queue_rows_by_key.values(), key=lambda r: r.get("character_key", "").casefold())

    write_csv(DERIVED_OUT, rows, OUTPUT_FIELDS)
    write_csv(QUERY_OUT, rows, OUTPUT_FIELDS)
    write_csv(QUEUE_CSV_OUT, queue_rows, QUEUE_FIELDS)

    QUEUE_TXT_OUT.parent.mkdir(parents=True, exist_ok=True)
    QUEUE_TXT_OUT.write_text("\n".join(row["character_key"] for row in queue_rows) + ("\n" if queue_rows else ""), encoding="utf-8")

    by_source = Counter(row.get("evidence_source", "") for row in rows)
    by_aff = Counter(row.get("affiliation_name", "") for row in rows)
    by_review = Counter(row.get("review_status", "") for row in rows)
    by_conf = Counter(row.get("confidence", "") for row in rows)
    queue_reason = Counter(row.get("reason", "") for row in queue_rows)

    top_aff = "\n".join(
        f"- {name}: {count}" for name, count in by_aff.most_common(20)
    )
    summary = f"""# Player affiliation evidence summary

Inputs:

- `{AFFILIATIONS_CSV.relative_to(ROOT)}`
- `{MEMBERS_CSV.relative_to(ROOT)}`
- `{PATTERNS_CSV.relative_to(ROOT)}`

Outputs:

- `{DERIVED_OUT.relative_to(ROOT)}`
- `{QUERY_OUT.relative_to(ROOT)}`
- `{QUEUE_CSV_OUT.relative_to(ROOT)}`
- `{QUEUE_TXT_OUT.relative_to(ROOT)}`

## Counts

- Affiliation source rows: {len(affiliations)}
- Listed member/contact source rows: {len(members)}
- Pattern source rows: {len(patterns)}
- Derived affiliation evidence rows: {len(rows)}
- Whois queue names: {len(queue_rows)}

## Evidence source counts

"""
    for source, count in by_source.most_common():
        summary += f"- {source}: {count}\n"
    summary += "\n## Review status counts\n\n"
    for status, count in by_review.most_common():
        summary += f"- {status}: {count}\n"
    summary += "\n## Confidence counts\n\n"
    for conf, count in by_conf.most_common():
        summary += f"- {conf}: {count}\n"
    summary += "\n## Whois queue reason counts\n\n"
    for reason, count in queue_reason.most_common():
        summary += f"- {reason}: {count}\n"
    summary += "\n## Top affiliation evidence counts\n\n"
    summary += top_aff + "\n"
    summary += """
## Interpretation notes

- These are player-organised or socially meaningful affiliations, not built-in race/subrace/faction classifications.
- Direct membership/contact rows from the 2003 webpage are historical evidence even when a current whois does not mention the group.
- Pattern matches from whois text are candidates and should be reviewed before public display as accepted affiliation.
- `character_key` is the official searchable MUME name, taken as the first word of a listed display name.
- `display_name` preserves surnames/titles from the source webpage for later public display.
- `affiliation_whois_queue.txt` contains searchable first-word character names from the affiliation source that are missing current whois evidence or are not yet in the character table.
"""
    SUMMARY_OUT.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_OUT.write_text(summary, encoding="utf-8")

    print(f"Wrote {DERIVED_OUT.relative_to(ROOT)} ({len(rows)} rows)")
    print(f"Wrote {SUMMARY_OUT.relative_to(ROOT)}")
    print(f"Wrote {QUERY_OUT.relative_to(ROOT)}")
    print(f"Wrote {QUEUE_CSV_OUT.relative_to(ROOT)} ({len(queue_rows)} rows)")
    print(f"Wrote {QUEUE_TXT_OUT.relative_to(ROOT)} ({len(queue_rows)} names)")


if __name__ == "__main__":
    main()
