#!/usr/bin/env python3

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path


REPORTS = Path("reports")
DERIVED = Path("data/derived")
EVIDENCE = Path("data/evidence")

CLASSIFICATION = REPORTS / "derived_character_classification.csv"
WHOIS_DISPLAY_INDEX = EVIDENCE / "whois_display/index.csv"
MENTIONS = REPORTS / "whois_possible_character_mentions.csv"
ASCII_ART = REPORTS / "whois_ascii_art_candidates.csv"
GROUPS = REPORTS / "whois_possible_guilds_clans.csv"

OUT_MANIFEST = DERIVED / "character_pages_manifest.csv"
OUT_SUMMARY = REPORTS / "character_pages_manifest_summary.md"


def clean(value):
    return (value or "").strip()


def read_csv(path):
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def slugify(value):
    value = clean(value).casefold()
    value = value.replace("æ", "ae").replace("œ", "oe")
    value = value.replace("þ", "th").replace("ð", "d")
    value = re.sub(r"[àáâãäåāăą]", "a", value)
    value = re.sub(r"[èéêëēĕėęě]", "e", value)
    value = re.sub(r"[ìíîïīĭįı]", "i", value)
    value = re.sub(r"[òóôõöøōŏő]", "o", value)
    value = re.sub(r"[ùúûüūŭůűų]", "u", value)
    value = re.sub(r"[çćĉċč]", "c", value)
    value = re.sub(r"[ñńņň]", "n", value)
    value = re.sub(r"[śŝşš]", "s", value)
    value = re.sub(r"[ýÿŷ]", "y", value)
    value = re.sub(r"[žźż]", "z", value)
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")
    return value or "unknown"


def build_whois_lookup(rows):
    by_character_id = {}
    by_name = {}

    def quality_score(row):
        score = 0
        if clean(row.get("has_raw_html")) == "yes":
            score += 100
        if clean(row.get("has_raw_decho")) == "yes":
            score += 50
        if clean(row.get("capture_quality")) == "high":
            score += 20
        elif clean(row.get("capture_quality")) == "medium":
            score += 10
        if clean(row.get("html_path")):
            score += 5
        return score

    grouped_by_id = defaultdict(list)
    grouped_by_name = defaultdict(list)

    for row in rows:
        cid = clean(row.get("character_id"))
        name = clean(row.get("character_name"))

        if cid:
            grouped_by_id[cid].append(row)
        if name:
            grouped_by_name[name.casefold()].append(row)

    for cid, grouped in grouped_by_id.items():
        by_character_id[cid] = sorted(grouped, key=quality_score, reverse=True)[0]

    for name_key, grouped in grouped_by_name.items():
        by_name[name_key] = sorted(grouped, key=quality_score, reverse=True)[0]

    return by_character_id, by_name


def build_mentions_lookup(rows):
    by_source_id = defaultdict(list)
    by_source_name = defaultdict(list)

    for row in rows:
        cid = clean(row.get("source_character_id"))
        name = clean(row.get("source_character_name"))

        if cid:
            by_source_id[cid].append(row)
        if name:
            by_source_name[name.casefold()].append(row)

    return by_source_id, by_source_name


def count_mentions(rows):
    total = len(rows)
    high = sum(1 for r in rows if clean(r.get("confidence")) == "high")
    matched = sum(1 for r in rows if clean(r.get("matched_known_character")) == "yes")

    heading = Counter(clean(r.get("mention_type")) for r in rows)
    type_summary = "; ".join(f"{k}:{v}" for k, v in heading.most_common() if k)

    # Keep a compact preview for later review.
    preview_names = []
    seen = set()
    for row in rows:
        name = clean(row.get("mentioned_name"))
        if not name:
            continue
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        preview_names.append(name)
        if len(preview_names) >= 12:
            break

    return {
        "mention_count": str(total),
        "mention_high_confidence_count": str(high),
        "mention_matched_known_count": str(matched),
        "mention_type_summary": type_summary,
        "mention_preview": "; ".join(preview_names),
    }


def build_ascii_lookup(rows):
    by_source_id = defaultdict(list)
    by_source_name = defaultdict(list)

    for row in rows:
        cid = clean(row.get("source_character_id"))
        name = clean(row.get("source_character_name"))

        if cid:
            by_source_id[cid].append(row)
        if name:
            by_source_name[name.casefold()].append(row)

    return by_source_id, by_source_name


def ascii_summary(rows):
    if not rows:
        return {
            "has_ascii_art": "no",
            "ascii_art_count": "0",
            "best_ascii_art_score": "",
        }

    def score(row):
        try:
            return float(clean(row.get("ascii_art_score")) or "0")
        except ValueError:
            return 0.0

    best = sorted(rows, key=score, reverse=True)[0]

    return {
        "has_ascii_art": "yes",
        "ascii_art_count": str(len(rows)),
        "best_ascii_art_score": clean(best.get("ascii_art_score")),
    }


def build_group_lookup(rows):
    by_source_id = defaultdict(list)
    by_source_name = defaultdict(list)

    for row in rows:
        cid = clean(row.get("source_character_id"))
        name = clean(row.get("source_character_name"))

        if cid:
            by_source_id[cid].append(row)
        if name:
            by_source_name[name.casefold()].append(row)

    return by_source_id, by_source_name


def group_summary(rows):
    if not rows:
        return {
            "group_candidate_count": "0",
            "group_candidate_confidence_summary": "",
        }

    counts = Counter(clean(r.get("confidence")) or "(blank)" for r in rows)
    return {
        "group_candidate_count": str(len(rows)),
        "group_candidate_confidence_summary": "; ".join(f"{k}:{v}" for k, v in counts.most_common()),
    }


def get_by_character(by_id, by_name, character_id, character_name):
    if character_id and character_id in by_id:
        return by_id[character_id]
    if character_name and character_name.casefold() in by_name:
        return by_name[character_name.casefold()]
    return None


def get_list_by_character(by_id, by_name, character_id, character_name):
    if character_id and character_id in by_id:
        return by_id[character_id]
    if character_name and character_name.casefold() in by_name:
        return by_name[character_name.casefold()]
    return []


def main():
    classification_rows = read_csv(CLASSIFICATION)
    whois_rows = read_csv(WHOIS_DISPLAY_INDEX)
    mention_rows = read_csv(MENTIONS)
    ascii_rows = read_csv(ASCII_ART)
    group_rows = read_csv(GROUPS)

    whois_by_id, whois_by_name = build_whois_lookup(whois_rows)
    mentions_by_id, mentions_by_name = build_mentions_lookup(mention_rows)
    ascii_by_id, ascii_by_name = build_ascii_lookup(ascii_rows)
    groups_by_id, groups_by_name = build_group_lookup(group_rows)

    manifest_rows = []

    for row in classification_rows:
        cid = clean(row.get("character_id"))
        name = clean(row.get("character_name"))
        page_slug = slugify(name)

        whois = get_by_character(whois_by_id, whois_by_name, cid, name)
        mentions = get_list_by_character(mentions_by_id, mentions_by_name, cid, name)
        ascii_matches = get_list_by_character(ascii_by_id, ascii_by_name, cid, name)
        group_matches = get_list_by_character(groups_by_id, groups_by_name, cid, name)

        mention_info = count_mentions(mentions)
        ascii_info = ascii_summary(ascii_matches)
        group_info = group_summary(group_matches)

        has_whois_display = "yes" if whois and clean(whois.get("html_path")) else "no"
        has_colour_whois = "yes" if whois and clean(whois.get("has_raw_html")) == "yes" else "no"

        page_review_needed = "no"

        if clean(row.get("review_needed")) == "yes":
            page_review_needed = "yes"
        if group_matches:
            page_review_needed = "yes"
        if clean(mention_info["mention_count"]) != "0":
            # Mentions are candidate evidence, so page has reviewable social data.
            page_review_needed = "yes"

        manifest_rows.append({
            "character_id": cid,
            "character_name": name,
            "page_slug": page_slug,

            "player_id": clean(row.get("player_id")),
            "player_main_handle": clean(row.get("player_main_handle")),
            "player_known_by": clean(row.get("player_known_by")),
            "player_link_confidence": clean(row.get("player_link_confidence")),
            "player_link_evidence_id": clean(row.get("player_link_evidence_id")),

            "derived_race": clean(row.get("derived_race")),
            "derived_subrace": clean(row.get("derived_subrace")),
            "derived_faction": clean(row.get("derived_faction")),
            "derived_faction_confidence": clean(row.get("derived_faction_confidence")),
            "derived_base_class": clean(row.get("derived_base_class")),
            "derived_class_title": clean(row.get("derived_class_title")),
            "derived_gender": clean(row.get("derived_gender")),
            "derived_gender_confidence": clean(row.get("derived_gender_confidence")),
            "derived_immortal_rank": clean(row.get("derived_immortal_rank")),
            "derived_immortal_code": clean(row.get("derived_immortal_code")),
            "derived_immortal_role": clean(row.get("derived_immortal_role")),
            "classification_status": clean(row.get("classification_status")),

            "has_whois_display": has_whois_display,
            "has_colour_whois": has_colour_whois,
            "whois_display_html_path": clean(whois.get("html_path")) if whois else "",
            "whois_display_text_path": clean(whois.get("text_path")) if whois else "",
            "whois_capture_id": clean(whois.get("capture_id")) if whois else "",
            "whois_capture_quality": clean(whois.get("capture_quality")) if whois else "",

            **mention_info,
            **ascii_info,
            **group_info,

            "classification_review_needed": clean(row.get("review_needed")),
            "page_review_needed": page_review_needed,
        })

    fieldnames = [
        "character_id",
        "character_name",
        "page_slug",

        "player_id",
        "player_main_handle",
        "player_known_by",
        "player_link_confidence",
        "player_link_evidence_id",

        "derived_race",
        "derived_subrace",
        "derived_faction",
        "derived_faction_confidence",
        "derived_base_class",
        "derived_class_title",
        "derived_gender",
        "derived_gender_confidence",
        "derived_immortal_rank",
        "derived_immortal_code",
        "derived_immortal_role",
        "classification_status",

        "has_whois_display",
        "has_colour_whois",
        "whois_display_html_path",
        "whois_display_text_path",
        "whois_capture_id",
        "whois_capture_quality",

        "mention_count",
        "mention_high_confidence_count",
        "mention_matched_known_count",
        "mention_type_summary",
        "mention_preview",

        "has_ascii_art",
        "ascii_art_count",
        "best_ascii_art_score",

        "group_candidate_count",
        "group_candidate_confidence_summary",

        "classification_review_needed",
        "page_review_needed",
    ]

    write_csv(OUT_MANIFEST, fieldnames, manifest_rows)

    counts = {
        "characters": len(manifest_rows),
        "with_player_link": sum(1 for r in manifest_rows if r["player_id"]),
        "with_whois_display": sum(1 for r in manifest_rows if r["has_whois_display"] == "yes"),
        "with_colour_whois": sum(1 for r in manifest_rows if r["has_colour_whois"] == "yes"),
        "with_mentions": sum(1 for r in manifest_rows if r["mention_count"] != "0"),
        "with_ascii_art": sum(1 for r in manifest_rows if r["has_ascii_art"] == "yes"),
        "with_group_candidates": sum(1 for r in manifest_rows if r["group_candidate_count"] != "0"),
        "page_review_needed": sum(1 for r in manifest_rows if r["page_review_needed"] == "yes"),
    }

    faction_counts = Counter(r["derived_faction"] or "(unknown)" for r in manifest_rows)
    classification_counts = Counter(r["classification_status"] or "(unknown)" for r in manifest_rows)

    lines = []
    lines.append("# Character Pages Manifest Summary")
    lines.append("")
    lines.append("## Core counts")
    lines.append("")
    for key, value in counts.items():
        lines.append(f"- {key}: {value}")
    lines.append("")
    lines.append("## Faction counts")
    lines.append("")
    for value, count in faction_counts.most_common():
        lines.append(f"- {value}: {count}")
    lines.append("")
    lines.append("## Classification status counts")
    lines.append("")
    for value, count in classification_counts.most_common():
        lines.append(f"- {value}: {count}")

    OUT_SUMMARY.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote {OUT_MANIFEST}")
    print(f"Wrote {OUT_SUMMARY}")
    print()
    for key, value in counts.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
