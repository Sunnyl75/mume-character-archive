#!/usr/bin/env python3

import csv
from collections import defaultdict
from pathlib import Path


REPORTS = Path("reports")

DESCRIPTOR_REPORT = REPORTS / "whois_descriptor_classification_report.csv"
MENTIONS_REPORT = REPORTS / "whois_possible_character_mentions.csv"
GROUPS_REPORT = REPORTS / "whois_possible_guilds_clans.csv"
ASCII_REPORT = REPORTS / "whois_ascii_art_candidates.csv"

OUT_DESCRIPTOR = REPORTS / "review_pack_descriptor.md"
OUT_MENTIONS = REPORTS / "review_pack_mentions.md"
OUT_GROUPS = REPORTS / "review_pack_guilds_clans.md"
OUT_ASCII = REPORTS / "review_pack_ascii_art.md"


def clean(value):
    return (value or "").strip()


def read_csv(path):
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def md_escape(value):
    return clean(value).replace("\r\n", "\n").replace("\r", "\n")


def code_block(value):
    value = md_escape(value)
    if not value:
        return "_No excerpt available._"
    return "```text\n" + value.strip() + "\n```"


def first_n(rows, n):
    return rows[:n]


def write_descriptor_pack():
    rows = read_csv(DESCRIPTOR_REPORT)

    unknown_faction = [
        r for r in rows
        if clean(r.get("derived_faction")) == ""
        or clean(r.get("derived_faction")) == "(unknown)"
    ]

    parser_suspect = [
        r for r in rows
        if clean(r.get("classification_status")) == "parser_suspect_or_custom_descriptor"
    ]

    generic_no_class = [
        r for r in rows
        if clean(r.get("classification_status")) == "generic_title_no_class"
    ]

    classified_sample = [
        r for r in rows
        if clean(r.get("classification_status")) == "classified"
    ][:10]

    lines = []
    lines.append("# Review Pack: Descriptor Classification")
    lines.append("")
    lines.append("This is a small review pack. It is not intended to review every row.")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Unknown faction rows: {len(unknown_faction)}")
    lines.append(f"- Parser-suspect/custom descriptor rows: {len(parser_suspect)}")
    lines.append(f"- Generic title/no class rows: {len(generic_no_class)}")
    lines.append(f"- Classified sample rows shown: {len(classified_sample)}")
    lines.append("")

    def add_rows(title, selected):
        lines.append(f"## {title}")
        lines.append("")
        if not selected:
            lines.append("_None._")
            lines.append("")
            return

        for i, r in enumerate(selected, start=1):
            lines.append(f"### {i}. {clean(r.get('character_name')) or '(unknown character)'}")
            lines.append("")
            lines.append(f"- Whois ID: `{clean(r.get('whois_id'))}`")
            lines.append(f"- Descriptor: `{clean(r.get('descriptor'))}`")
            lines.append(f"- Status: `{clean(r.get('classification_status'))}`")
            lines.append(f"- Derived race: `{clean(r.get('derived_race'))}`")
            lines.append(f"- Derived subrace: `{clean(r.get('derived_subrace'))}`")
            lines.append(f"- Derived faction: `{clean(r.get('derived_faction'))}`")
            lines.append(f"- Derived class: `{clean(r.get('derived_base_class'))}`")
            lines.append(f"- Derived title: `{clean(r.get('derived_class_title'))}`")
            lines.append(f"- Derived gender: `{clean(r.get('derived_gender'))}`")
            lines.append(f"- Gender confidence: `{clean(r.get('derived_gender_confidence'))}`")
            lines.append(f"- Remainder: `{clean(r.get('unmatched_descriptor_remainder'))}`")
            lines.append(f"- Notes: `{clean(r.get('derived_parse_notes'))}`")
            lines.append("")

    add_rows("Unknown faction rows", unknown_faction)
    add_rows("Parser-suspect or custom descriptor rows", parser_suspect)
    add_rows("Generic title, no class rows — first 20", first_n(generic_no_class, 20))
    add_rows("Classified sample — first 10", classified_sample)

    OUT_DESCRIPTOR.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_mentions_pack():
    rows = read_csv(MENTIONS_REPORT)

    by_type = defaultdict(list)
    for r in rows:
        by_type[clean(r.get("mention_type"))].append(r)

    selected = []
    for mention_type in ["heading_name_list", "comma_name_list", "quoted_speaker"]:
        selected.extend(by_type.get(mention_type, [])[:10])

    lines = []
    lines.append("# Review Pack: Character Mention Candidates")
    lines.append("")
    lines.append("This pack shows up to 10 examples from each main mention type.")
    lines.append("")
    lines.append("## Counts")
    lines.append("")
    for mention_type, grouped in sorted(by_type.items()):
        lines.append(f"- {mention_type}: {len(grouped)}")
    lines.append("")

    for i, r in enumerate(selected, start=1):
        lines.append(f"## {i}. {clean(r.get('source_character_name'))} → {clean(r.get('mentioned_name'))}")
        lines.append("")
        lines.append(f"- Mention type: `{clean(r.get('mention_type'))}`")
        lines.append(f"- Heading: `{clean(r.get('heading'))}`")
        lines.append(f"- Confidence: `{clean(r.get('confidence'))}`")
        lines.append(f"- Matched known character: `{clean(r.get('matched_known_character'))}`")
        lines.append(f"- Source descriptor: `{clean(r.get('whois_descriptor'))}`")
        lines.append("")
        lines.append("Evidence line:")
        lines.append("")
        lines.append(code_block(r.get("evidence_excerpt")))
        lines.append("")
        lines.append("Whois context:")
        lines.append("")
        lines.append(code_block(r.get("whois_text_excerpt")))
        lines.append("")

    OUT_MENTIONS.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_groups_pack():
    rows = read_csv(GROUPS_REPORT)

    medium = [r for r in rows if clean(r.get("confidence")) == "medium"]
    low = [r for r in rows if clean(r.get("confidence")) == "low"]

    selected = medium[:15] + low[:10]

    lines = []
    lines.append("# Review Pack: Possible Guilds / Clans / Groups")
    lines.append("")
    lines.append("This report is expected to be noisy. Review for recurring patterns, not individual certainty.")
    lines.append("")
    lines.append("## Counts")
    lines.append("")
    lines.append(f"- Total rows: {len(rows)}")
    lines.append(f"- Medium confidence rows: {len(medium)}")
    lines.append(f"- Low confidence rows: {len(low)}")
    lines.append("")

    for i, r in enumerate(selected, start=1):
        lines.append(f"## {i}. {clean(r.get('source_character_name'))}")
        lines.append("")
        lines.append(f"- Evidence type: `{clean(r.get('evidence_type'))}`")
        lines.append(f"- Confidence: `{clean(r.get('confidence'))}`")
        lines.append(f"- Needs review: `{clean(r.get('needs_review'))}`")
        lines.append(f"- Source descriptor: `{clean(r.get('whois_descriptor'))}`")
        lines.append("")
        lines.append("Evidence line:")
        lines.append("")
        lines.append(code_block(r.get("evidence_excerpt")))
        lines.append("")
        lines.append("Whois context:")
        lines.append("")
        lines.append(code_block(r.get("whois_text_excerpt")))
        lines.append("")

    OUT_GROUPS.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_ascii_pack():
    rows = read_csv(ASCII_REPORT)

    def score(row):
        try:
            return float(clean(row.get("ascii_art_score")) or "0")
        except ValueError:
            return 0.0

    rows = sorted(rows, key=score, reverse=True)
    selected = rows[:25]

    lines = []
    lines.append("# Review Pack: ASCII Art Candidates")
    lines.append("")
    lines.append("This pack shows the top 25 ASCII-art candidates by score.")
    lines.append("")
    lines.append(f"Total ASCII candidates: {len(rows)}")
    lines.append("")

    for i, r in enumerate(selected, start=1):
        lines.append(f"## {i}. {clean(r.get('source_character_name'))}")
        lines.append("")
        lines.append(f"- Score: `{clean(r.get('ascii_art_score'))}`")
        lines.append(f"- Art-like line count: `{clean(r.get('ascii_art_line_count'))}`")
        lines.append(f"- Source descriptor: `{clean(r.get('whois_descriptor'))}`")
        lines.append("")
        lines.append("Detected ASCII block:")
        lines.append("")
        lines.append(code_block(r.get("ascii_art_excerpt")))
        lines.append("")
        lines.append("Whois context:")
        lines.append("")
        lines.append(code_block(r.get("whois_text_excerpt")))
        lines.append("")

    OUT_ASCII.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    REPORTS.mkdir(parents=True, exist_ok=True)

    write_descriptor_pack()
    write_mentions_pack()
    write_groups_pack()
    write_ascii_pack()

    print(f"Wrote {OUT_DESCRIPTOR}")
    print(f"Wrote {OUT_MENTIONS}")
    print(f"Wrote {OUT_GROUPS}")
    print(f"Wrote {OUT_ASCII}")


if __name__ == "__main__":
    main()
