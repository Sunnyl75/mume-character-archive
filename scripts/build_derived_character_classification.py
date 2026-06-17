#!/usr/bin/env python3

import csv
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path


WORKING = Path("data/working")
REPORTS = Path("reports")

CHARACTERS = WORKING / "characters.csv"
PLAYERS = WORKING / "players.csv"
PLAYER_CHARACTER_LINKS = WORKING / "player_character_links.csv"
CLASSIFICATION_REPORT = REPORTS / "whois_descriptor_classification_report.csv"
IMMORTAL_EVIDENCE = Path("data/derived/character_immortal_evidence.csv")

OUT_CSV = REPORTS / "derived_character_classification.csv"
OUT_SUMMARY = REPORTS / "derived_character_classification_summary.md"


def clean(value):
    return (value or "").strip()


def strip_accents(value):
    return "".join(ch for ch in unicodedata.normalize("NFKD", clean(value)) if not unicodedata.combining(ch))


def norm_name(value):
    return strip_accents(value).casefold()


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
            by_character_name[norm_name(character_name)].append(link)

    return players_by_id, by_character_id, by_character_name


def build_immortal_lookup(rows):
    by_character_id = defaultdict(list)
    by_name = defaultdict(list)

    for row in rows:
        cid = clean(row.get("character_id"))
        name = clean(row.get("character_key") or row.get("display_name"))
        if cid:
            by_character_id[cid].append(row)
        if name:
            by_name[norm_name(name)].append(row)

    return by_character_id, by_name


def choose_immortal_evidence(rows):
    if not rows:
        return None

    status_rank = {"current": 30, "honorary": 25, "retired": 20, "former": 20}
    category_rank = {
        "Implementor": 70,
        "Aratar": 60,
        "Vala": 50,
        "Maia": 40,
        "Boardreader": 30,
        "True Legend": 20,
    }

    def score(row):
        return (
            status_rank.get(clean(row.get("immortal_status")).casefold(), 0)
            + category_rank.get(clean(row.get("immortal_category")), 0)
            + (5 if clean(row.get("is_maiar_muddler")) == "yes" else 0)
            + (3 if clean(row.get("honorary_immortal")) == "yes" else 0)
        )

    return sorted(rows, key=score, reverse=True)[0]


def immortal_fields_for_character(character_id, character_name, by_id, by_name):
    rows = []
    if character_id:
        rows.extend(by_id.get(character_id, []))
    if not rows and character_name:
        rows.extend(by_name.get(character_name.casefold(), []))

    best = choose_immortal_evidence(rows)
    if not best:
        return {
            "immortal_list_status": "",
            "immortal_list_category": "",
            "is_maiar_muddler": "",
            "honorary_immortal": "",
            "immortal_list_source_id": "",
            "immortal_list_source_name": "",
            "immortal_list_source_date_context": "",
            "immortal_list_evidence_id": "",
            "immortal_list_review_status": "",
            "immortal_list_notes": "",
        }

    return {
        "immortal_list_status": clean(best.get("immortal_status")),
        "immortal_list_category": clean(best.get("immortal_category")),
        "is_maiar_muddler": clean(best.get("is_maiar_muddler")),
        "honorary_immortal": clean(best.get("honorary_immortal")),
        "immortal_list_source_id": clean(best.get("source_id")),
        "immortal_list_source_name": clean(best.get("source_name")),
        "immortal_list_source_date_context": clean(best.get("source_date_context")),
        "immortal_list_evidence_id": clean(best.get("immortal_evidence_id")),
        "immortal_list_review_status": clean(best.get("review_status")),
        "immortal_list_notes": clean(best.get("notes")),
    }


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
        links.extend(links_by_character_name.get(norm_name(character_name), []))

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




def immortal_category_as_identity(value):
    value = clean(value)
    # Source-list headings are fallback race/rank evidence, not class evidence.
    # Preserve the list wording where that is the evidence we have.
    mapping = {
        "Maiar": "Maia",
        "Maia": "Maia",
        "Valar": "Valar",
        "Vala": "Vala",
        "Aratar": "Aratar",
        "Arata": "Arata",
        "Implementors": "Implementor",
        "Implementor": "Implementor",
        "Boardreaders": "Boardreader",
        "Boardreader": "Boardreader",
        "True Legend": "True Legend",
    }
    return mapping.get(value, value)


def immortal_identity_token(value):
    value = clean(value).casefold()
    mapping = {
        "implementors": "implementor",
        "implementor": "implementor",
        "aratar": "aratar",
        "arata": "arata",
        "valar": "valar",
        "vala": "vala",
        "maiar": "maia",
        "maia": "maia",
        "boardreaders": "boardreader",
        "boardreader": "boardreader",
        "immortals": "immortal",
        "immortal": "immortal",
        "true legend": "true legend",
    }
    return mapping.get(value, value)


def is_immortal_rank_word(value):
    return immortal_identity_token(value) in {
        "implementor", "aratar", "arata", "valar", "vala",
        "maia", "boardreader", "immortal", "true legend",
    }


def apply_immortal_identity_fallback(row):
    """Put immortal evidence into the normal race/class display fields.

    Whois-derived immortal rank/role is strongest.  Source-list heading evidence
    is weaker and only fills blanks.
    """
    rank = clean(row.get("derived_immortal_rank"))
    role = clean(row.get("derived_immortal_role"))
    list_rank = immortal_category_as_identity(row.get("immortal_list_category"))

    # A broad immortal rank is not a class/role.  In early reference data,
    # Implementor was mistakenly stored as both rank and role, which produced
    # card identities like "Implementor / Implementor".  Only parenthetical or
    # specific whois roles such as Cartographer, Wright, Shaper, Architect,
    # Mudller, Building, Code, etc. should fill class/title fields.
    if role and (immortal_identity_token(role) == immortal_identity_token(rank) or is_immortal_rank_word(role)):
        role = ""
        row["derived_immortal_role"] = ""

    if clean(row.get("derived_faction")) == "Immortals" or rank or list_rank:
        if not clean(row.get("derived_faction")):
            row["derived_faction"] = "Immortals"
            row["derived_faction_confidence"] = "medium"
        if not clean(row.get("derived_race")) or clean(row.get("derived_race")) == "Ainu":
            row["derived_race"] = rank or list_rank
        if role:
            # The role in e.g. ``Maia (Cartographer)`` is the class/title for
            # display purposes, and should outrank the broad list heading.
            if not clean(row.get("derived_class_title")) or clean(row.get("derived_class_title")) == clean(row.get("derived_race")):
                row["derived_class_title"] = role
            if not clean(row.get("derived_base_class")) or clean(row.get("derived_base_class")) == clean(row.get("derived_race")):
                row["derived_base_class"] = role
            if not clean(row.get("derived_who_class_group")) or clean(row.get("derived_who_class_group")) == clean(row.get("derived_race")):
                row["derived_who_class_group"] = role
            if not clean(row.get("derived_class_confidence")):
                row["derived_class_confidence"] = "high"
        else:
            # Without a whois-derived role/type, headings such as Implementor,
            # Aratar, Valar, Maia, and Boardreader are race/rank descriptions.
            # They must not leak into class fields.
            for field in ["derived_class_title", "derived_base_class", "derived_who_class_group"]:
                if is_immortal_rank_word(row.get(field)) or immortal_identity_token(row.get(field)) == immortal_identity_token(row.get("derived_race")):
                    row[field] = ""
        if not clean(row.get("classification_status")) or row.get("classification_status") == "no_whois_classification":
            row["classification_status"] = "immortal_list_only" if list_rank and not rank else "immortal"
    return row


def main():
    REPORTS.mkdir(parents=True, exist_ok=True)

    characters = read_csv(CHARACTERS)
    players = read_csv(PLAYERS)
    player_links = read_csv(PLAYER_CHARACTER_LINKS)
    classifications = read_csv(CLASSIFICATION_REPORT)
    immortal_evidence = read_csv(IMMORTAL_EVIDENCE)

    players_by_id, links_by_character_id, links_by_character_name = build_player_lookup(players, player_links)
    immortal_by_id, immortal_by_name = build_immortal_lookup(immortal_evidence)

    by_character_id = defaultdict(list)
    by_character_name = defaultdict(list)

    for row in classifications:
        character_id = clean(row.get("character_id"))
        character_name = clean(row.get("character_name"))

        if character_id:
            by_character_id[character_id].append(row)
        elif character_name:
            by_character_name[norm_name(character_name)].append(row)

    out_rows = []

    for char in characters:
        character_id = clean(char.get("character_id"))
        character_name = clean(char.get("character_name") or char.get("name"))

        candidates = []
        if character_id:
            candidates.extend(by_character_id.get(character_id, []))
        if not candidates and character_name:
            candidates.extend(by_character_name.get(norm_name(character_name), []))

        best = choose_best(candidates)
        player_fields = player_fields_for_character(
            character_id,
            character_name,
            players_by_id,
            links_by_character_id,
            links_by_character_name,
        )
        immortal_list_fields = immortal_fields_for_character(
            character_id,
            character_name,
            immortal_by_id,
            immortal_by_name,
        )

        if best:
            out_row = {
                "character_id": character_id,
                "character_name": character_name,
                **player_fields,
                **immortal_list_fields,
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
            }
            out_rows.append(apply_immortal_identity_fallback(out_row))
        else:
            out_row = {
                "character_id": character_id,
                "character_name": character_name,
                **player_fields,
                **immortal_list_fields,
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
            }
            out_rows.append(apply_immortal_identity_fallback(out_row))

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
        "immortal_list_status",
        "immortal_list_category",
        "is_maiar_muddler",
        "honorary_immortal",
        "immortal_list_source_id",
        "immortal_list_source_name",
        "immortal_list_source_date_context",
        "immortal_list_evidence_id",
        "immortal_list_review_status",
        "immortal_list_notes",
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
    immortal_list_status_counts = Counter(row.get("immortal_list_status") or "(none)" for row in out_rows)
    immortal_list_category_counts = Counter(row.get("immortal_list_category") or "(none)" for row in out_rows)
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
    lines.append("## Immortal-list status counts")
    lines.append("")
    for value, count in immortal_list_status_counts.most_common():
        lines.append(f"- {value}: {count}")
    lines.append("")
    lines.append("## Immortal-list category counts")
    lines.append("")
    for value, count in immortal_list_category_counts.most_common():
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
