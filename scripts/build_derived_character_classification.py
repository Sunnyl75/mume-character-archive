#!/usr/bin/env python3

import csv
from collections import Counter, defaultdict
from pathlib import Path


WORKING = Path("data/working")
REPORTS = Path("reports")

CHARACTERS = WORKING / "characters.csv"
PLAYERS = WORKING / "players.csv"
PLAYER_CHARACTER_LINKS = WORKING / "player_character_links.csv"
CLASSIFICATION_REPORT = REPORTS / "whois_descriptor_classification_report.csv"

OUT_CSV = REPORTS / "derived_character_classification.csv"
OUT_SUMMARY = REPORTS / "derived_character_classification_summary.md"


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


def confidence_rank(value):
    ranks = {
        "": 0,
        "low": 1,
        "medium": 2,
        "high": 3,
    }
    return ranks.get(clean(value).casefold(), 0)


def status_rank(value):
    ranks = {
        "classified": 6,
        "immortal": 6,
        "generic_title_no_class": 5,
        "race_only": 4,
        "parser_suspect_or_custom_descriptor": 3,
        "custom_descriptor_unclassified": 2,
        "no_descriptor": 1,
        "needs_review": 1,
    }
    return ranks.get(clean(value), 0)


def choose_best(rows):
    """Choose the best derived classification row for one character.

    This is deliberately conservative:
    - Prefer classified/immortal rows.
    - Prefer rows with faction/race.
    - Prefer rows with specific class/title.
    - Prefer higher confidence gender/faction.
    """

    def score(row):
        s = 0
        s += status_rank(row.get("classification_status")) * 100

        if clean(row.get("derived_faction")):
            s += 30
        if clean(row.get("derived_race")):
            s += 30
        if clean(row.get("derived_subrace")):
            s += 10
        if clean(row.get("derived_base_class")):
            s += 20
        if clean(row.get("derived_who_class_group")):
            s += 5
        if clean(row.get("derived_class_title")):
            s += 10
        if clean(row.get("derived_class_confidence")) == "high":
            s += 3
        elif clean(row.get("derived_class_confidence")) == "medium":
            s += 2
        elif clean(row.get("derived_class_confidence")) == "low":
            s += 1
        if clean(row.get("derived_immortal_rank")):
            s += 20
        if clean(row.get("derived_gender")):
            s += 5 + confidence_rank(row.get("derived_gender_confidence"))

        # Avoid making parser-suspect rows win merely because they have many fields.
        if clean(row.get("classification_status")) == "parser_suspect_or_custom_descriptor":
            s -= 20

        return s

    if not rows:
        return None

    return sorted(rows, key=score, reverse=True)[0]


def build_player_lookup(players, links):
    players_by_id = {
        clean(row.get("player_id")): row
        for row in players
        if clean(row.get("player_id"))
    }

    by_character_id = defaultdict(list)
    by_character_name = defaultdict(list)

    for link in links:
        if clean(link.get("status")) and clean(link.get("status")) != "accepted":
            continue

        character_id = clean(link.get("character_id"))
        character_name = clean(link.get("character_name"))

        if character_id:
            by_character_id[character_id].append(link)
        if character_name:
            by_character_name[character_name.casefold()].append(link)

    return players_by_id, by_character_id, by_character_name


def choose_player_link(links):
    """Choose the strongest player-character link for display.

    At present most imported PLAYERS.TXT links are accepted/medium.
    If future evidence adds high-confidence or manual links, this function
    will prefer them.
    """
    if not links:
        return None

    def score(link):
        s = 0

        if clean(link.get("status")) == "accepted":
            s += 100

        confidence = clean(link.get("confidence")).casefold()
        if confidence == "high":
            s += 30
        elif confidence == "medium":
            s += 20
        elif confidence == "low":
            s += 10

        if clean(link.get("link_type")) == "listed_same_player":
            s += 5

        return s

    return sorted(links, key=score, reverse=True)[0]


def player_fields_for_character(character_id, character_name, players_by_id, links_by_character_id, links_by_character_name):
    links = []

    if character_id:
        links.extend(links_by_character_id.get(character_id, []))

    if not links and character_name:
        links.extend(links_by_character_name.get(character_name.casefold(), []))

    link = choose_player_link(links)

    if not link:
        return {
            "player_id": "",
            "player_main_handle": "",
            "player_known_by": "",
            "player_real_name": "",
            "player_link_type": "",
            "player_link_status": "",
            "player_link_confidence": "",
            "player_link_evidence_id": "",
            "player_link_notes": "",
        }

    player_id = clean(link.get("player_id"))
    player = players_by_id.get(player_id, {})

    return {
        "player_id": player_id,
        "player_main_handle": clean(player.get("main_handle") or link.get("main_handle")),
        "player_known_by": clean(player.get("known_by") or player.get("main_handle") or link.get("main_handle")),
        "player_real_name": clean(player.get("real_name")),
        "player_link_type": clean(link.get("link_type")),
        "player_link_status": clean(link.get("status")),
        "player_link_confidence": clean(link.get("confidence")),
        "player_link_evidence_id": clean(link.get("primary_evidence_id")),
        "player_link_notes": clean(link.get("notes")),
    }



def main():
    REPORTS.mkdir(parents=True, exist_ok=True)

    characters = read_csv(CHARACTERS)
    players = read_csv(PLAYERS)
    player_links = read_csv(PLAYER_CHARACTER_LINKS)
    classifications = read_csv(CLASSIFICATION_REPORT)

    players_by_id, links_by_character_id, links_by_character_name = build_player_lookup(players, player_links)

    by_character_id = defaultdict(list)
    by_character_name = defaultdict(list)

    for row in classifications:
        character_id = clean(row.get("character_id"))
        character_name = clean(row.get("character_name"))

        if character_id:
            by_character_id[character_id].append(row)
        elif character_name:
            by_character_name[character_name.casefold()].append(row)

    out_rows = []

    for char in characters:
        character_id = clean(char.get("character_id"))
        character_name = clean(char.get("character_name") or char.get("name"))

        candidates = []
        if character_id:
            candidates.extend(by_character_id.get(character_id, []))
        if not candidates and character_name:
            candidates.extend(by_character_name.get(character_name.casefold(), []))

        best = choose_best(candidates)
        player_fields = player_fields_for_character(
            character_id,
            character_name,
            players_by_id,
            links_by_character_id,
            links_by_character_name,
        )

        if best:
            out_rows.append({
                "character_id": character_id,
                "character_name": character_name,
                **player_fields,
                "source_whois_id": clean(best.get("whois_id")),
                "source_descriptor": clean(best.get("descriptor")),
                "derived_race": clean(best.get("derived_race")),
                "derived_subrace": clean(best.get("derived_subrace")),
                "derived_faction": clean(best.get("derived_faction")),
                "derived_faction_confidence": clean(best.get("derived_faction_confidence")),
                "derived_base_class": clean(best.get("derived_base_class")),
                "derived_who_class_group": clean(best.get("derived_who_class_group")),
                "derived_class_title": clean(best.get("derived_class_title")),
                "derived_class_confidence": clean(best.get("derived_class_confidence")),
                "derived_class_skill_notes": clean(best.get("derived_class_skill_notes")),
                "derived_class_level_restriction_notes": clean(best.get("derived_class_level_restriction_notes")),
                "derived_class_race_restriction_notes": clean(best.get("derived_class_race_restriction_notes")),
                "derived_class_alignment_restriction_notes": clean(best.get("derived_class_alignment_restriction_notes")),
                "derived_gender": clean(best.get("derived_gender")),
                "derived_gender_confidence": clean(best.get("derived_gender_confidence")),
                "derived_immortal_rank": clean(best.get("derived_immortal_rank")),
                "derived_immortal_code": clean(best.get("derived_immortal_code")),
                "derived_immortal_role": clean(best.get("derived_immortal_role")),
                "classification_status": clean(best.get("classification_status")),
                "classification_notes": clean(best.get("derived_parse_notes")),
                "candidate_whois_rows": str(len(candidates)),
                "review_needed": "yes" if clean(best.get("classification_status")) in {
                    "parser_suspect_or_custom_descriptor",
                    "custom_descriptor_unclassified",
                    "no_descriptor",
                    "needs_review",
                } else "no",
            })
        else:
            out_rows.append({
                "character_id": character_id,
                "character_name": character_name,
                **player_fields,
                "source_whois_id": "",
                "source_descriptor": "",
                "derived_race": "",
                "derived_subrace": "",
                "derived_faction": "",
                "derived_faction_confidence": "",
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
                "derived_immortal_rank": "",
                "derived_immortal_code": "",
                "derived_immortal_role": "",
                "classification_status": "no_whois_classification",
                "classification_notes": "No classification row found",
                "candidate_whois_rows": "0",
                "review_needed": "yes",
            })

    fieldnames = [
        "character_id",
        "character_name",
        "player_id",
        "player_main_handle",
        "player_known_by",
        "player_real_name",
        "player_link_type",
        "player_link_status",
        "player_link_confidence",
        "player_link_evidence_id",
        "player_link_notes",
        "source_whois_id",
        "source_descriptor",
        "derived_race",
        "derived_subrace",
        "derived_faction",
        "derived_faction_confidence",
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
        "derived_immortal_rank",
        "derived_immortal_code",
        "derived_immortal_role",
        "classification_status",
        "classification_notes",
        "candidate_whois_rows",
        "review_needed",
    ]

    write_csv(OUT_CSV, fieldnames, out_rows)

    race_counts = Counter(row["derived_race"] or "(unknown)" for row in out_rows)
    faction_counts = Counter(row["derived_faction"] or "(unknown)" for row in out_rows)
    class_counts = Counter(row["derived_base_class"] or "(unknown)" for row in out_rows)
    who_class_group_counts = Counter(row.get("derived_who_class_group") or "(unknown)" for row in out_rows)
    gender_counts = Counter(row["derived_gender"] or "(unknown)" for row in out_rows)
    status_counts = Counter(row["classification_status"] or "(unknown)" for row in out_rows)
    review_counts = Counter(row["review_needed"] for row in out_rows)
    player_link_counts = Counter("yes" if row["player_id"] else "no" for row in out_rows)
    player_confidence_counts = Counter(row["player_link_confidence"] or "(none)" for row in out_rows)

    lines = []
    lines.append("# Derived Character Classification Summary")
    lines.append("")
    lines.append(f"Characters processed: {len(out_rows)}")
    lines.append("")
    lines.append("## Review-needed counts")
    lines.append("")
    for value, count in review_counts.most_common():
        lines.append(f"- {value}: {count}")
    lines.append("")
    lines.append("## Player-link counts")
    lines.append("")
    for value, count in player_link_counts.most_common():
        lines.append(f"- {value}: {count}")
    lines.append("")
    lines.append("## Player-link confidence counts")
    lines.append("")
    for value, count in player_confidence_counts.most_common():
        lines.append(f"- {value}: {count}")
    lines.append("")
    lines.append("## Race counts")
    lines.append("")
    for value, count in race_counts.most_common():
        lines.append(f"- {value}: {count}")
    lines.append("")
    lines.append("## Faction counts")
    lines.append("")
    for value, count in faction_counts.most_common():
        lines.append(f"- {value}: {count}")
    lines.append("")
    lines.append("## Base class counts")
    lines.append("")
    for value, count in class_counts.most_common():
        lines.append(f"- {value}: {count}")
    lines.append("")
    lines.append("## Who-class group counts")
    lines.append("")
    for value, count in who_class_group_counts.most_common():
        lines.append(f"- {value}: {count}")
    lines.append("")
    lines.append("## Gender counts")
    lines.append("")
    for value, count in gender_counts.most_common():
        lines.append(f"- {value}: {count}")
    lines.append("")
    lines.append("## Classification status counts")
    lines.append("")
    for value, count in status_counts.most_common():
        lines.append(f"- {value}: {count}")

    OUT_SUMMARY.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote {OUT_CSV}")
    print(f"Wrote {OUT_SUMMARY}")
    print()
    print(f"Characters processed: {len(out_rows)}")
    print("Review-needed counts:")
    for value, count in review_counts.most_common():
        print(f"  {value}: {count}")
    print()
    print("Player-link counts:")
    for value, count in player_link_counts.most_common():
        print(f"  {value}: {count}")
    print()
    print("Faction counts:")
    for value, count in faction_counts.most_common():
        print(f"  {value}: {count}")


if __name__ == "__main__":
    main()
