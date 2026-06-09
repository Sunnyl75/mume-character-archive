#!/usr/bin/env python3

import csv
import re
from collections import Counter
from pathlib import Path


WORKING = Path("data/working")
REFERENCE = Path("data/reference")
REPORTS = Path("reports")

WHOIS_RECORDS = WORKING / "whois_records.csv"
RACE_TERMS = REFERENCE / "race_terms.csv"
CLASS_TITLES = REFERENCE / "class_titles.csv"
IMMORTAL_RANKS = REFERENCE / "immortal_ranks.csv"

OUT_CSV = REPORTS / "whois_descriptor_classification_report.csv"
OUT_UNKNOWN = REPORTS / "whois_descriptor_unknown_terms.md"


def clean(value):
    return (value or "").strip()


def norm(value):
    value = clean(value).casefold()
    replacements = {
        "ú": "u", "û": "u",
        "ó": "o", "ö": "o",
        "á": "a", "ä": "a",
        "é": "e", "ë": "e",
        "í": "i", "ï": "i",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    value = re.sub(r"\s+", " ", value)
    return value


def normalise_base_class(value):
    value = clean(value)
    if value.casefold() == "unknown":
        return ""
    return value


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def term_pattern(term):
    return r"(?<!\w)" + re.escape(norm(term)) + r"(?!\w)"


def longest_term_match(text, rows, term_field):
    text_norm = norm(text)
    candidates = []

    for row in rows:
        term = clean(row.get(term_field))
        if not term:
            continue

        term_norm = norm(term)
        if re.search(term_pattern(term), text_norm):
            candidates.append((len(term_norm), term_norm, row))

    if not candidates:
        return None

    candidates.sort(reverse=True, key=lambda item: item[0])
    return candidates[0][2]


def all_term_matches(text, rows, term_field):
    text_norm = norm(text)
    matches = []

    for row in rows:
        term = clean(row.get(term_field))
        if not term:
            continue

        if re.search(term_pattern(term), text_norm):
            matches.append((len(norm(term)), row))

    matches.sort(reverse=True, key=lambda item: item[0])
    return [row for _length, row in matches]


def remove_term(text, term):
    if not term:
        return text

    pattern = re.compile(r"(?<!\w)" + re.escape(term) + r"(?!\w)", re.IGNORECASE)
    return re.sub(r"\s+", " ", pattern.sub(" ", text)).strip()


def remove_equivalent_race_terms(text, race_terms, derived_race, derived_subrace):
    remainder = text

    for row in race_terms:
        if clean(row.get("race")) != derived_race:
            continue

        row_subrace = clean(row.get("subrace"))

        # If we matched a specific subrace, do not remove other subrace terms.
        if derived_subrace and row_subrace and row_subrace != derived_subrace:
            continue

        remainder = remove_term(remainder, clean(row.get("term")))

    return remainder.strip(" ,;:-")


def looks_parser_suspect(text):
    value = norm(text)
    suspect_bits = [
        " is a ",
        " is an ",
        " level ",
        " level",
    ]
    return any(bit in value for bit in suspect_bits)


def descriptor_from_row(row):
    parts = []

    race = clean(row.get("parsed_race"))
    cls = clean(row.get("parsed_class"))

    if race:
        parts.append(race)
    if cls and cls not in parts:
        parts.append(cls)

    return " ".join(parts).strip()


def derive_from_descriptor(descriptor, race_terms, class_titles, immortal_ranks):
    notes = []

    result = {
        "derived_race": "",
        "derived_subrace": "",
        "derived_base_class": "",
        "derived_who_class_group": "",
        "derived_class_title": "",
        "derived_class_confidence": "",
        "derived_class_skill_notes": "",
        "derived_class_level_restriction_notes": "",
        "derived_class_race_restriction_notes": "",
        "derived_class_alignment_restriction_notes": "",
        "derived_gender": "",
        "derived_gender_confidence": "",
        "derived_faction": "",
        "derived_faction_confidence": "",
        "derived_immortal_rank": "",
        "derived_immortal_code": "",
        "derived_immortal_role": "",
        "classification_status": "",
        "derived_parse_notes": "",
        "unmatched_descriptor_remainder": "",
    }

    desc = clean(descriptor)
    if not desc:
        result["classification_status"] = "no_descriptor"
        result["derived_parse_notes"] = "No descriptor"
        return result

    remainder = desc

    # Immortal handling first. Prefer the highest-ranked immortal term.
    immortal_matches = []
    for row in immortal_ranks:
        term = clean(row.get("term"))
        if not term:
            continue

        if re.search(term_pattern(term), norm(desc)):
            try:
                rank_order = int(clean(row.get("rank_order")) or "999")
            except ValueError:
                rank_order = 999
            immortal_matches.append((rank_order, len(norm(term)), row))

    if immortal_matches:
        immortal_matches.sort(key=lambda item: (item[0], -item[1]))
        immortal = immortal_matches[0][2]

        result["derived_immortal_rank"] = clean(immortal.get("immortal_rank"))
        result["derived_immortal_code"] = clean(immortal.get("immortal_code"))
        result["derived_immortal_role"] = clean(immortal.get("immortal_role"))
        result["derived_faction"] = "Immortals"
        result["derived_faction_confidence"] = "high"

        rank = clean(immortal.get("immortal_rank"))
        if rank in {"Maia", "Vala", "Arata"}:
            result["derived_race"] = rank
        else:
            result["derived_race"] = "Ainu"

        notes.append(f"immortal_term={clean(immortal.get('term'))}")

        for _rank_order, _length, row in immortal_matches:
            remainder = remove_term(remainder, clean(row.get("term")))

        remainder = remainder.strip(" ,;:-")

    race = longest_term_match(desc, race_terms, "term")

    if race:
        result["derived_race"] = clean(race.get("race"))
        result["derived_subrace"] = clean(race.get("subrace"))
        remainder = remove_term(remainder, clean(race.get("term")))
        remainder = remove_equivalent_race_terms(
            remainder,
            race_terms,
            result["derived_race"],
            result["derived_subrace"],
        )
        notes.append(f"race_term={clean(race.get('term'))}")

    cls = longest_term_match(remainder or desc, class_titles, "title")
    class_title_matched = False
    class_title_has_specific_class = False

    if cls:
        class_title_matched = True
        base_class = normalise_base_class(cls.get("base_class"))

        who_class_group = clean(cls.get("who_class_group")) or base_class

        result["derived_base_class"] = base_class
        result["derived_who_class_group"] = who_class_group
        result["derived_class_title"] = clean(cls.get("title"))
        result["derived_class_confidence"] = clean(cls.get("classification_confidence") or cls.get("confidence"))
        result["derived_class_skill_notes"] = clean(cls.get("skill_requirement_notes"))
        result["derived_class_level_restriction_notes"] = clean(cls.get("level_restriction_notes"))
        result["derived_class_race_restriction_notes"] = clean(cls.get("race_restriction_notes"))
        result["derived_class_alignment_restriction_notes"] = clean(cls.get("alignment_restriction_notes"))

        if base_class:
            class_title_has_specific_class = True

        gender = clean(cls.get("gender"))
        if gender and gender != "unknown":
            result["derived_gender"] = gender
            result["derived_gender_confidence"] = clean(cls.get("gender_confidence"))

        remainder = remove_term(remainder, clean(cls.get("title")))
        notes.append(f"class_title={clean(cls.get('title'))}")
        if result["derived_who_class_group"]:
            notes.append(f"who_class_group={result['derived_who_class_group']}")
        if result["derived_class_confidence"]:
            notes.append(f"class_confidence={result['derived_class_confidence']}")
        if result["derived_class_skill_notes"]:
            notes.append(f"skill_notes={result['derived_class_skill_notes']}")
        if result["derived_class_race_restriction_notes"]:
            notes.append(f"race_restriction={result['derived_class_race_restriction_notes']}")
        if result["derived_class_alignment_restriction_notes"]:
            notes.append(f"alignment_restriction={result['derived_class_alignment_restriction_notes']}")

    remainder = remainder.strip(" ,;:-")

    # Faction inference. Immortals override mortal faction.
    if result["derived_faction"] != "Immortals":
        race_value = result["derived_race"]
        subrace_value = result["derived_subrace"]

        if race_value == "Orc" and subrace_value == "Zaugurz":
            result["derived_faction"] = "Renegade Zaugurz"
            result["derived_faction_confidence"] = "high"
        elif race_value in {"Orc", "Troll"}:
            result["derived_faction"] = "Minions of Sauron"
            result["derived_faction_confidence"] = "high"
        elif subrace_value == "Black Númenórean":
            result["derived_faction"] = "Minions of Sauron"
            result["derived_faction_confidence"] = "high"
        elif race_value:
            result["derived_faction"] = "Free Peoples"
            result["derived_faction_confidence"] = "medium"

    result["unmatched_descriptor_remainder"] = remainder

    # Cautious status: custom descriptors are valid evidence, not parser failure.
    if result["derived_faction"] == "Immortals":
        result["classification_status"] = "immortal"
    elif looks_parser_suspect(remainder):
        result["classification_status"] = "parser_suspect_or_custom_descriptor"
    elif result["derived_race"] and class_title_has_specific_class:
        result["classification_status"] = "classified"
    elif result["derived_race"] and class_title_matched and not class_title_has_specific_class:
        result["classification_status"] = "generic_title_no_class"
    elif result["derived_race"] and not result["derived_base_class"]:
        result["classification_status"] = "race_only"
    elif not result["derived_race"] and remainder:
        result["classification_status"] = "custom_descriptor_unclassified"
    else:
        result["classification_status"] = "needs_review"

    if remainder:
        notes.append(f"unmatched={remainder}")

    if not result["derived_race"]:
        notes.append("race_unknown")
    if not result["derived_base_class"] and result["derived_race"] not in {"Maia", "Vala", "Arata", "Ainu"}:
        notes.append("base_class_unknown")

    result["derived_parse_notes"] = " | ".join(notes)
    return result


def main():
    REPORTS.mkdir(parents=True, exist_ok=True)

    whois = read_csv(WHOIS_RECORDS)
    race_terms = read_csv(RACE_TERMS)
    class_titles = read_csv(CLASS_TITLES)
    immortal_ranks = read_csv(IMMORTAL_RANKS)

    report_rows = []
    unknown_counter = Counter()
    descriptor_counter = Counter()
    faction_counter = Counter()
    race_counter = Counter()
    class_counter = Counter()
    status_counter = Counter()

    for row in whois:
        status = clean(row.get("status"))
        if status == "not_found":
            continue

        descriptor = descriptor_from_row(row)
        derived = derive_from_descriptor(descriptor, race_terms, class_titles, immortal_ranks)

        out = {
            "whois_id": clean(row.get("whois_id")),
            "character_id": clean(row.get("character_id")),
            "character_name": clean(row.get("character_name")),
            "descriptor": descriptor,
            "parsed_race": clean(row.get("parsed_race")),
            "parsed_class": clean(row.get("parsed_class")),
            **derived,
            "status": status,
            "parse_confidence": clean(row.get("parse_confidence")),
            "notes": clean(row.get("notes")),
        }

        report_rows.append(out)

        descriptor_counter[descriptor] += 1
        if derived["unmatched_descriptor_remainder"]:
            unknown_counter[derived["unmatched_descriptor_remainder"]] += 1

        race_counter[derived["derived_race"] or "(unknown)"] += 1
        class_counter[normalise_base_class(derived["derived_base_class"]) or "(unknown)"] += 1
        faction_counter[derived["derived_faction"] or "(unknown)"] += 1
        status_counter[derived["classification_status"] or "(unknown)"] += 1

    fieldnames = [
        "whois_id",
        "character_id",
        "character_name",
        "descriptor",
        "parsed_race",
        "parsed_class",
        "derived_race",
        "derived_subrace",
        "derived_base_class",
        "derived_who_class_group",
        "derived_class_title",
        "derived_class_confidence",
        "derived_class_skill_notes",
        "derived_class_level_restriction_notes",
        "derived_class_race_restriction_notes",
        "derived_class_alignment_restriction_notes",
        "derived_gender",
        "derived_gender_confidence",
        "derived_faction",
        "derived_faction_confidence",
        "derived_immortal_rank",
        "derived_immortal_code",
        "derived_immortal_role",
        "classification_status",
        "unmatched_descriptor_remainder",
        "derived_parse_notes",
        "status",
        "parse_confidence",
        "notes",
    ]

    write_csv(OUT_CSV, fieldnames, report_rows)

    lines = []
    lines.append("# Whois Descriptor Classification: Unknown / Review Terms")
    lines.append("")
    lines.append(f"Rows analysed: {len(report_rows)}")
    lines.append("")

    lines.append("## Derived race counts")
    lines.append("")
    for value, count in race_counter.most_common():
        lines.append(f"- {value}: {count}")
    lines.append("")

    lines.append("## Derived base class counts")
    lines.append("")
    for value, count in class_counter.most_common():
        lines.append(f"- {value}: {count}")
    lines.append("")

    lines.append("## Derived faction counts")
    lines.append("")
    for value, count in faction_counter.most_common():
        lines.append(f"- {value}: {count}")
    lines.append("")

    lines.append("## Classification status counts")
    lines.append("")
    for value, count in status_counter.most_common():
        lines.append(f"- {value}: {count}")
    lines.append("")

    lines.append("## Unmatched descriptor remainders")
    lines.append("")
    if unknown_counter:
        for value, count in unknown_counter.most_common(100):
            lines.append(f"- `{value}`: {count}")
    else:
        lines.append("No unmatched descriptor remainders.")
    lines.append("")

    lines.append("## Most common raw descriptors")
    lines.append("")
    for value, count in descriptor_counter.most_common(100):
        lines.append(f"- `{value}`: {count}")

    OUT_UNKNOWN.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote {OUT_CSV}")
    print(f"Wrote {OUT_UNKNOWN}")
    print()
    print("Faction counts:")
    for value, count in faction_counter.most_common():
        print(f"  {value}: {count}")
    print()
    print("Classification status counts:")
    for value, count in status_counter.most_common():
        print(f"  {value}: {count}")
    print()
    print("Unknown remainders:")
    for value, count in unknown_counter.most_common(20):
        print(f"  {value}: {count}")


if __name__ == "__main__":
    main()
