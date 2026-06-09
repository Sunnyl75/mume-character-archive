#!/usr/bin/env python3
"""
Query helper for the MUME Character Archive.

Run from the repository root, for example:

    python3 scripts/query_character_archive.py summary
    python3 scripts/query_character_archive.py clans
    python3 scripts/query_character_archive.py gender-review
    python3 scripts/query_character_archive.py females
    python3 scripts/query_character_archive.py uncertain-gender
    python3 scripts/query_character_archive.py review-needed
    python3 scripts/query_character_archive.py no-whois
    python3 scripts/query_character_archive.py mentions Rik
    python3 scripts/query_character_archive.py player Burb

Reports are written to reports/queries/.
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
REPORTS = REPO_ROOT / "reports"
DERIVED = REPO_ROOT / "data" / "derived"
WORKING = REPO_ROOT / "data" / "working"
QUERY_OUT = REPORTS / "queries"

MANIFEST = DERIVED / "character_pages_manifest.csv"
CLASSIFICATION = REPORTS / "derived_character_classification.csv"
MENTIONS = REPORTS / "whois_possible_character_mentions.csv"
GROUPS = REPORTS / "whois_possible_guilds_clans.csv"
PLAYERS = WORKING / "players.csv"
PLAYER_LINKS = WORKING / "player_character_links.csv"


def clean(value: object) -> str:
    return str(value or "").strip()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise SystemExit(f"Missing required file: {path.relative_to(REPO_ROOT)}")

    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    if fieldnames is None:
        fieldnames = []
        seen: set[str] = set()
        for row in rows:
            for key in row.keys():
                if key not in seen:
                    seen.add(key)
                    fieldnames.append(key)

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def yes(value: object) -> bool:
    return clean(value).casefold() == "yes"


def no(value: object) -> bool:
    return clean(value).casefold() == "no"


def contains_ci(haystack: object, needle: str) -> bool:
    return needle.casefold() in clean(haystack).casefold()


def character_key(row: dict[str, str]) -> str:
    return clean(row.get("character_name") or row.get("name")).casefold()


def rows_matching_name(rows: Iterable[dict[str, str]], name_column: str, query: str) -> list[dict[str, str]]:
    q = query.casefold()
    return [row for row in rows if q in clean(row.get(name_column)).casefold()]


def print_written(paths: Iterable[Path]) -> None:
    for path in paths:
        print(f"Wrote {path.relative_to(REPO_ROOT)}")


def command_summary(_: argparse.Namespace) -> None:
    manifest = read_csv(MANIFEST)
    classification = read_csv(CLASSIFICATION)
    groups = read_csv(GROUPS)
    mentions = read_csv(MENTIONS)
    player_links = read_csv(PLAYER_LINKS)

    faction_counts = Counter(clean(r.get("derived_faction")) or "unknown" for r in manifest)
    race_counts = Counter(clean(r.get("derived_race")) or "unknown" for r in manifest)
    class_counts = Counter(clean(r.get("derived_base_class")) or "unknown" for r in manifest)
    gender_counts = Counter(clean(r.get("derived_gender")) or "unknown" for r in manifest)
    status_counts = Counter(clean(r.get("classification_status")) or "unknown" for r in manifest)

    lines = [
        "# MUME Character Archive query summary",
        "",
        f"Characters in manifest: {len(manifest)}",
        f"Classification rows: {len(classification)}",
        f"Player-character links: {len(player_links)}",
        f"Possible clan/guild/group rows: {len(groups)}",
        f"Possible character mention rows: {len(mentions)}",
        "",
        f"With player link: {sum(1 for r in manifest if clean(r.get('player_id')))}",
        f"With whois display: {sum(1 for r in manifest if yes(r.get('has_whois_display')))}",
        f"With colour whois: {sum(1 for r in manifest if yes(r.get('has_colour_whois')))}",
        f"Review needed: {sum(1 for r in manifest if yes(r.get('page_review_needed')))}",
        "",
        "## Faction counts",
        *counter_lines(faction_counts),
        "",
        "## Race counts",
        *counter_lines(race_counts),
        "",
        "## Base class counts",
        *counter_lines(class_counts),
        "",
        "## Gender counts",
        *counter_lines(gender_counts),
        "",
        "## Classification status counts",
        *counter_lines(status_counts),
        "",
    ]

    out = QUERY_OUT / "summary.md"
    write_markdown(out, "\n".join(lines))
    print("\n".join(lines))
    print_written([out])


def counter_lines(counter: Counter[str]) -> list[str]:
    return [f"- {key}: {value}" for key, value in counter.most_common()]


def command_clans(_: argparse.Namespace) -> None:
    rows = read_csv(GROUPS)

    output = []
    for row in rows:
        output.append({
            "character_id": clean(row.get("source_character_id")),
            "character_name": clean(row.get("source_character_name")),
            "candidate_affiliation": clean(row.get("possible_guild_or_clan")),
            "evidence_type": clean(row.get("evidence_type")),
            "confidence": clean(row.get("confidence")),
            "needs_review": clean(row.get("needs_review")),
            "source_whois_id": clean(row.get("source_whois_id")),
            "descriptor": clean(row.get("whois_descriptor")),
            "evidence_excerpt": clean(row.get("evidence_excerpt")),
        })

    output.sort(key=lambda r: (
        clean(r.get("needs_review")) != "yes",
        clean(r.get("confidence")),
        clean(r.get("candidate_affiliation")).casefold(),
        clean(r.get("character_name")).casefold(),
    ))

    out_csv = QUERY_OUT / "clan_affiliation_candidates.csv"
    out_md = QUERY_OUT / "clan_affiliation_candidates_summary.md"

    counts = Counter(clean(r.get("confidence")) or "unknown" for r in output)
    lines = [
        "# Clan/guild/group affiliation candidates",
        "",
        "These are review candidates, not confirmed affiliations.",
        "",
        f"Rows: {len(output)}",
        "",
        "## Confidence counts",
        *counter_lines(counts),
        "",
        "## Top candidates",
    ]

    for row in output[:50]:
        lines.append(
            f"- {row['character_name']}: {row['candidate_affiliation']} "
            f"({row['confidence']}; {row['evidence_type']})"
        )

    write_csv(out_csv, output)
    write_markdown(out_md, "\n".join(lines) + "\n")
    print_written([out_csv, out_md])


def command_gender_review(_: argparse.Namespace) -> None:
    rows = read_csv(CLASSIFICATION)

    output = []
    for row in rows:
        gender = clean(row.get("derived_gender")) or "unknown"
        confidence = clean(row.get("derived_gender_confidence"))
        review = yes(row.get("review_needed"))
        status = clean(row.get("classification_status"))

        if gender != "unknown" or confidence or review or status in {
            "parser_suspect_or_custom_descriptor",
            "custom_descriptor_unclassified",
            "generic_title_no_class",
        }:
            output.append({
                "character_id": clean(row.get("character_id")),
                "character_name": clean(row.get("character_name")),
                "derived_gender": gender,
                "derived_gender_confidence": confidence,
                "source_descriptor": clean(row.get("source_descriptor")),
                "derived_race": clean(row.get("derived_race")),
                "derived_faction": clean(row.get("derived_faction")),
                "derived_base_class": clean(row.get("derived_base_class")),
                "derived_class_title": clean(row.get("derived_class_title")),
                "classification_status": status,
                "classification_notes": clean(row.get("classification_notes")),
                "review_needed": clean(row.get("review_needed")),
            })

    output.sort(key=lambda r: (
        clean(r.get("derived_gender")) == "unknown",
        clean(r.get("derived_gender_confidence")),
        clean(r.get("character_name")).casefold(),
    ))

    out = QUERY_OUT / "gender_review.csv"
    write_csv(out, output)
    print_written([out])


def command_females(_: argparse.Namespace) -> None:
    rows = read_csv(CLASSIFICATION)
    output = [gender_row(row) for row in rows if clean(row.get("derived_gender")) == "female"]
    output.sort(key=lambda r: clean(r.get("character_name")).casefold())
    out = QUERY_OUT / "female_characters.csv"
    write_csv(out, output)
    print_written([out])


def command_uncertain_gender(_: argparse.Namespace) -> None:
    rows = read_csv(CLASSIFICATION)
    output = []
    for row in rows:
        gender = clean(row.get("derived_gender"))
        confidence = clean(row.get("derived_gender_confidence"))
        if gender and gender != "unknown" and confidence not in {"high", "strong"}:
            output.append(gender_row(row))
        elif not gender or gender == "unknown":
            descriptor = clean(row.get("source_descriptor"))
            if descriptor and any(term in descriptor.casefold() for term in ["ess", "queen", "lady", "mistress", "matriarch", "heroine"]):
                output.append(gender_row(row))

    output.sort(key=lambda r: clean(r.get("character_name")).casefold())
    out = QUERY_OUT / "uncertain_gender.csv"
    write_csv(out, output)
    print_written([out])


def gender_row(row: dict[str, str]) -> dict[str, str]:
    return {
        "character_id": clean(row.get("character_id")),
        "character_name": clean(row.get("character_name")),
        "derived_gender": clean(row.get("derived_gender")) or "unknown",
        "derived_gender_confidence": clean(row.get("derived_gender_confidence")),
        "source_descriptor": clean(row.get("source_descriptor")),
        "derived_race": clean(row.get("derived_race")),
        "derived_faction": clean(row.get("derived_faction")),
        "derived_base_class": clean(row.get("derived_base_class")),
        "derived_class_title": clean(row.get("derived_class_title")),
        "classification_status": clean(row.get("classification_status")),
        "classification_notes": clean(row.get("classification_notes")),
        "review_needed": clean(row.get("review_needed")),
    }


def command_review_needed(_: argparse.Namespace) -> None:
    rows = read_csv(MANIFEST)
    output = [review_row(row) for row in rows if yes(row.get("page_review_needed")) or yes(row.get("classification_review_needed"))]
    output.sort(key=lambda r: (clean(r.get("classification_status")), clean(r.get("character_name")).casefold()))
    out = QUERY_OUT / "review_needed_pages.csv"
    write_csv(out, output)
    print_written([out])


def command_no_whois(_: argparse.Namespace) -> None:
    rows = read_csv(MANIFEST)
    output = [review_row(row) for row in rows if clean(row.get("classification_status")) == "no_whois_classification"]
    output.sort(key=lambda r: clean(r.get("character_name")).casefold())
    out = QUERY_OUT / "no_whois_classification.csv"
    write_csv(out, output)
    print_written([out])


def review_row(row: dict[str, str]) -> dict[str, str]:
    return {
        "character_id": clean(row.get("character_id")),
        "character_name": clean(row.get("character_name")),
        "player_main_handle": clean(row.get("player_main_handle")),
        "player_known_by": clean(row.get("player_known_by")),
        "derived_race": clean(row.get("derived_race")),
        "derived_faction": clean(row.get("derived_faction")),
        "derived_base_class": clean(row.get("derived_base_class")),
        "derived_gender": clean(row.get("derived_gender")),
        "classification_status": clean(row.get("classification_status")),
        "has_whois_display": clean(row.get("has_whois_display")),
        "has_colour_whois": clean(row.get("has_colour_whois")),
        "mention_count": clean(row.get("mention_count")),
        "group_candidate_count": clean(row.get("group_candidate_count")),
        "classification_review_needed": clean(row.get("classification_review_needed")),
        "page_review_needed": clean(row.get("page_review_needed")),
        "page_slug": clean(row.get("page_slug")),
    }


def command_mentions(args: argparse.Namespace) -> None:
    query = clean(args.name)
    if not query:
        raise SystemExit("Please provide a character name, for example: python3 scripts/query_character_archive.py mentions Rik")

    rows = read_csv(MENTIONS)
    output = []

    for row in rows:
        source_match = contains_ci(row.get("source_character_name"), query)
        mentioned_match = contains_ci(row.get("mentioned_name"), query)
        if source_match or mentioned_match:
            output.append({
                "match_side": "source" if source_match else "mentioned",
                "source_character_id": clean(row.get("source_character_id")),
                "source_character_name": clean(row.get("source_character_name")),
                "mentioned_name": clean(row.get("mentioned_name")),
                "mention_type": clean(row.get("mention_type")),
                "heading": clean(row.get("heading")),
                "confidence": clean(row.get("confidence")),
                "matched_known_character": clean(row.get("matched_known_character")),
                "source_whois_id": clean(row.get("source_whois_id")),
                "evidence_excerpt": clean(row.get("evidence_excerpt")),
            })

    safe = safe_filename(query)
    out = QUERY_OUT / f"mentions_{safe}.csv"
    write_csv(out, output)
    print(f"Matches: {len(output)}")
    print_written([out])


def command_player(args: argparse.Namespace) -> None:
    query = clean(args.name)
    if not query:
        raise SystemExit("Please provide a player handle/name, for example: python3 scripts/query_character_archive.py player Burb")

    players = read_csv(PLAYERS)
    links = read_csv(PLAYER_LINKS)
    manifest = read_csv(MANIFEST)

    player_matches = []
    for player in players:
        searchable = " ".join([
            clean(player.get("player_id")),
            clean(player.get("main_handle")),
            clean(player.get("known_by")),
            clean(player.get("real_name")),
            clean(player.get("raw_entry")),
        ])
        if query.casefold() in searchable.casefold():
            player_matches.append(player)

    matched_player_ids = {clean(p.get("player_id")) for p in player_matches if clean(p.get("player_id"))}

    link_matches = []
    for link in links:
        if clean(link.get("player_id")) in matched_player_ids or contains_ci(link.get("main_handle"), query):
            link_matches.append(link)

    manifest_by_id = {clean(r.get("character_id")): r for r in manifest}

    output = []
    for link in link_matches:
        char_id = clean(link.get("character_id"))
        page = manifest_by_id.get(char_id, {})
        output.append({
            "player_id": clean(link.get("player_id")),
            "main_handle": clean(link.get("main_handle")),
            "character_id": char_id,
            "character_name": clean(link.get("character_name")),
            "link_type": clean(link.get("link_type")),
            "status": clean(link.get("status")),
            "confidence": clean(link.get("confidence")),
            "primary_evidence_id": clean(link.get("primary_evidence_id")),
            "derived_race": clean(page.get("derived_race")),
            "derived_faction": clean(page.get("derived_faction")),
            "derived_base_class": clean(page.get("derived_base_class")),
            "classification_status": clean(page.get("classification_status")),
            "page_slug": clean(page.get("page_slug")),
            "notes": clean(link.get("notes")),
        })

    output.sort(key=lambda r: clean(r.get("character_name")).casefold())

    safe = safe_filename(query)
    out = QUERY_OUT / f"player_{safe}.csv"
    write_csv(out, output)

    print(f"Player matches: {len(player_matches)}")
    for player in player_matches[:20]:
        print(f"- {clean(player.get('player_id'))}: {clean(player.get('main_handle'))} / {clean(player.get('known_by'))}")
    print(f"Linked characters: {len(output)}")
    print_written([out])


def safe_filename(value: str) -> str:
    safe = "".join(ch.lower() if ch.isalnum() else "_" for ch in value.strip())
    safe = "_".join(part for part in safe.split("_") if part)
    return safe or "query"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Query the MUME Character Archive CSV outputs.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("summary", help="Write a compact archive summary.").set_defaults(func=command_summary)
    sub.add_parser("clans", help="Write clan/guild/group candidate reports.").set_defaults(func=command_clans)
    sub.add_parser("gender-review", help="Write a gender review CSV.").set_defaults(func=command_gender_review)
    sub.add_parser("females", help="Write a CSV of female-inferred characters.").set_defaults(func=command_females)
    sub.add_parser("uncertain-gender", help="Write a CSV of lower-confidence gender cases.").set_defaults(func=command_uncertain_gender)
    sub.add_parser("review-needed", help="Write a CSV of pages/characters needing review.").set_defaults(func=command_review_needed)
    sub.add_parser("no-whois", help="Write a CSV of characters without whois classification.").set_defaults(func=command_no_whois)

    mentions = sub.add_parser("mentions", help="Find mention rows involving a character name.")
    mentions.add_argument("name")
    mentions.set_defaults(func=command_mentions)

    player = sub.add_parser("player", help="Find player records and linked characters.")
    player.add_argument("name")
    player.set_defaults(func=command_player)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
