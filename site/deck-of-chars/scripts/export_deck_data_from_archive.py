#!/usr/bin/env python3
"""Export Deck of Chars web data from the MUME character archive.

This exporter deliberately matches the committed Deck of Chars data schema:

    window.DECK_CHARS = {
      "meta": {...},
      "characters": [...],
      "players": [...],
      "asciiRecords": [...]
    };

It reads the archive's derived manifest and evidence display files, but it does
not change raw evidence. Standalone whois HTML evidence pages are converted back
into the <pre>...</pre> fragment shape expected by the Deck UI.

Usage:
  python3 site/deck-of-chars/scripts/export_deck_data_from_archive.py \
    /path/to/mume-character-archive \
    site/deck-of-chars/assets/data/deck-data.js
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

IMMORTAL_RANK_WORDS = {
    "implementor", "implementors",
    "arata", "aratar",
    "vala", "valar",
    "maia", "maiar",
    "boardreader", "boardreaders",
    "true legend", "legend",
}

FACTION_MAP = {
    "free peoples": ("free", "Free Peoples"),
    "minions of sauron": ("evil", "Minions of Sauron"),
    "renegade zaugurz": ("renegade", "Renegade Zaugurz"),
    "immortals": ("immortal", "Immortals"),
    "immortal": ("immortal", "Immortals"),
}


def clean(value: Any) -> str:
    return str(value or "").strip()


def truthy(value: Any) -> bool:
    return clean(value).casefold() in {"yes", "true", "1", "y"}


def slugify(value: str) -> str:
    value = clean(value).casefold()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.replace("æ", "ae").replace("œ", "oe")
    value = value.replace("þ", "th").replace("ð", "d")
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")
    return value or "unknown"


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def read_text_if_file(root: Path, rel: str) -> str:
    rel = clean(rel)
    if not rel:
        return ""
    path = root / rel
    if not path.exists() or not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def extract_pre_fragment(full_html: str) -> str:
    """Return the Deck-compatible <pre>...</pre> fragment from evidence HTML.

    The evidence exporter writes complete standalone HTML documents. The Deck UI
    expects the committed deck-data.js shape: an HTML fragment, usually a <pre>
    containing colour spans. Never export <!doctype>, <html>, <head>, <body>, or
    page CSS into deck-data.js.
    """
    full_html = full_html or ""
    if not full_html.strip():
        return ""

    match = re.search(r"<pre\b[^>]*>.*?</pre>", full_html, flags=re.I | re.S)
    if match:
        fragment = match.group(0)
    else:
        # If a future evidence file is already a fragment, keep it only when it
        # does not look like a full document.
        if re.search(r"<!doctype|<html\b|<head\b|<body\b", full_html, flags=re.I):
            return ""
        fragment = full_html

    # Match the old committed data shape: leading/trailing newlines around the
    # fragment are harmless and preserve compatibility with the current page.
    return "\n" + fragment.strip() + "\n"


def int_or_none(value: Any) -> int | None:
    text = clean(value)
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def float_or_zero(value: Any) -> float:
    text = clean(value)
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def faction_pair(value: str) -> tuple[str, str]:
    key = clean(value).casefold()
    return FACTION_MAP.get(key, (slugify(value) if value else "unknown", clean(value) or "Unknown"))


def normalise_immortal_rank(value: str) -> str:
    value = clean(value)
    folded = value.casefold()
    if folded == "maiar":
        return "Maia"
    if folded == "valar":
        return "Vala"
    if folded == "aratar":
        return "Arata"
    if folded == "implementors":
        return "Implementor"
    if folded == "boardreaders":
        return "Boardreader"
    return value


def is_immortal_row(row: dict[str, str]) -> bool:
    return (
        clean(row.get("classification_status")).casefold() == "immortal"
        or clean(row.get("derived_faction")).casefold() == "immortals"
        or bool(clean(row.get("derived_immortal_rank")))
        or bool(clean(row.get("immortal_list_category")))
    )


def card_image_key(faction: str, race_raw: str, klass: str, gender: str) -> str:
    return "-".join(
        part for part in [slugify(faction), slugify(race_raw), slugify(klass), slugify(gender or "unknown")]
        if part and part != "unknown"
    ) or "unknown"


def display_active(row: dict[str, str], working: dict[str, str]) -> str:
    for value in [working.get("first_seen"), working.get("last_seen")]:
        value = clean(value)
        if re.match(r"^\d{4}", value):
            return f"c. {value[:4]}"
    return "unknown"


def build_character(row: dict[str, str], working: dict[str, str], affiliation_by_character: dict[str, str], root: Path) -> dict[str, Any]:
    character_id = clean(row.get("character_id")) or f"char_{slugify(row.get('character_name', 'unknown'))}"
    name = clean(row.get("character_name")) or clean(working.get("name")) or character_id
    immortal = is_immortal_row(row)

    derived_race = clean(row.get("derived_race")) or clean(working.get("race"))
    derived_subrace = clean(row.get("derived_subrace"))
    derived_faction = clean(row.get("derived_faction"))

    derived_rank = normalise_immortal_rank(row.get("derived_immortal_rank") or row.get("immortal_list_category") or "")
    derived_role = clean(row.get("derived_immortal_role"))
    if derived_role.casefold() in IMMORTAL_RANK_WORDS:
        derived_role = ""

    if immortal:
        faction, faction_label = "immortal", "Immortals"
        race_raw = derived_rank or normalise_immortal_rank(derived_race) or "Immortal"
        race_display = race_raw
        subrace = derived_role
        klass = ""
        class_raw = ""
        level = None
        level_label = ""
    else:
        faction, faction_label = faction_pair(derived_faction)
        race_raw = derived_race or clean(working.get("race")) or "Unknown"
        subrace = derived_subrace
        race_display = f"{race_raw} ({subrace})" if race_raw and subrace else race_raw

        class_title = clean(row.get("derived_class_title"))
        base_class = clean(row.get("derived_base_class"))
        working_class = clean(working.get("class"))
        # Prefer broad class when it is meaningful; otherwise use the title.
        if base_class and base_class.casefold() not in {"general", "unknown"}:
            klass = base_class
        else:
            klass = class_title or working_class or "Unknown"
        class_raw = klass
        level = int_or_none(working.get("level"))
        level_label = f"Level {level}" if level is not None else "Level ?"

    whois_text_path = clean(row.get("whois_display_text_path"))
    whois_html_path = clean(row.get("whois_display_html_path"))
    whois_text = read_text_if_file(root, whois_text_path)
    whois_html = extract_pre_fragment(read_text_if_file(root, whois_html_path))

    player = clean(row.get("player_known_by")) or clean(row.get("player_main_handle")) or "Unknown"
    player_id = clean(row.get("player_id")) or "unknown"

    sources: list[str] = []
    if clean(row.get("player_link_evidence_id")):
        sources.append(f"Player link evidence: {clean(row.get('player_link_evidence_id'))}")
    if clean(row.get("whois_capture_id")):
        sources.append(f"Whois capture: {clean(row.get('whois_capture_id'))}")
    if whois_text_path:
        sources.append(f"Whois text: {whois_text_path}")
    if whois_html_path:
        sources.append(f"Whois HTML: {whois_html_path}")
    if clean(row.get("immortal_list_evidence_id")):
        sources.append(f"Immortal list evidence: {clean(row.get('immortal_list_evidence_id'))}")

    return {
        "id": character_id,
        "name": name,
        "slug": clean(row.get("page_slug")) or slugify(name),
        "playerId": player_id,
        "player": player,
        "playerMain": clean(row.get("player_main_handle")) or player,
        "playerConfidence": clean(row.get("player_link_confidence")) or "unknown",
        "race": race_display,
        "raceRaw": race_raw,
        "subrace": subrace,
        "klass": klass,
        "classRaw": class_raw,
        "level": level,
        "levelLabel": level_label,
        "faction": faction,
        "factionLabel": faction_label,
        "gender": clean(row.get("derived_gender")) or "unknown",
        "active": display_active(row, working),
        "clan": affiliation_by_character.get(character_id, ""),
        "hasWhois": truthy(row.get("has_whois_display")) or bool(whois_text or whois_html),
        "hasColourWhois": truthy(row.get("has_colour_whois")) and bool(whois_html),
        "hasAscii": truthy(row.get("has_ascii_art")),
        "asciiScore": float_or_zero(row.get("best_ascii_art_score")),
        "whoisText": whois_text,
        "whoisTextPath": whois_text_path,
        "whoisHtml": whois_html,
        "whoisHtmlPath": whois_html_path,
        "captureQuality": clean(row.get("whois_capture_quality")) or "",
        "mentionCount": int_or_none(row.get("mention_count")) or 0,
        "groupCandidateCount": int_or_none(row.get("group_candidate_count")) or 0,
        "reviewNeeded": truthy(row.get("classification_review_needed")) or truthy(row.get("page_review_needed")),
        "classificationStatus": clean(row.get("classification_status")) or "unknown",
        "cardImageKey": card_image_key(faction, race_raw, klass, clean(row.get("derived_gender")) or "unknown"),
        "sources": sources,
        "playerRealFirstName": "",
        "playerCardFaction": faction if faction in {"free", "evil", "renegade", "immortal"} else "free",
        # Extra fields are appended conservatively. Existing UI ignores them;
        # future UI/reporting can use them without reparsing deck-data.js.
        "derivedImmortalRank": derived_rank,
        "derivedImmortalRole": derived_role,
        "immortalListStatus": clean(row.get("immortal_list_status")),
        "immortalListCategory": clean(row.get("immortal_list_category")),
        "isMaiarMuddler": clean(row.get("is_maiar_muddler")),
        "honoraryImmortal": clean(row.get("honorary_immortal")),
    }


PRONUNCIATION_MARK_TRANSLATION = str.maketrans({
    "Æ": "AE", "æ": "ae", "Œ": "OE", "œ": "oe",
    "Ð": "D", "ð": "d", "Đ": "D", "đ": "d",
    "Þ": "TH", "þ": "th", "Ø": "O", "ø": "o",
    "Ł": "L", "ł": "l", "ß": "ss",
})


def strip_pronunciation_marks(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", clean(value))
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).translate(PRONUNCIATION_MARK_TRANSLATION)


def accentless_name_key(value: str) -> str:
    return strip_pronunciation_marks(value).casefold()


def has_pronunciation_mark(value: str) -> bool:
    value = clean(value)
    return value != strip_pronunciation_marks(value)


def character_record_quality(character: dict[str, Any]) -> int:
    return (
        (100_000 if character.get("hasWhois") else 0)
        + (10_000 if isinstance(character.get("level"), int) else 0)
        + int(character.get("mentionCount") or 0)
        + len(character.get("sources") or [])
    )


def deduplicate_accented_characters(characters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for character in characters:
        groups[accentless_name_key(character.get("name", ""))].append(character)

    results: list[dict[str, Any]] = []
    for group in groups.values():
        if len({clean(character.get("name")) for character in group}) < 2:
            results.extend(group)
            continue
        preferred = max(
            group,
            key=lambda character: (
                has_pronunciation_mark(character.get("name", "")),
                character_record_quality(character),
            ),
        )
        results.append(preferred)
    return results


def build_players(characters: list[dict[str, Any]], players_csv: list[dict[str, str]]) -> list[dict[str, Any]]:
    by_player: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for c in characters:
        by_player[c.get("playerId") or "unknown"].append(c)

    player_rows_by_id = {clean(row.get("player_id")): row for row in players_csv}
    results = []
    for player_id, chars in sorted(by_player.items(), key=lambda item: (item[1][0].get("player") or "").casefold()):
        prow = player_rows_by_id.get(player_id, {})
        name = clean(prow.get("known_by")) or clean(prow.get("main_handle")) or chars[0].get("player") or "Unknown"
        numeric_levels = [c["level"] for c in chars if isinstance(c.get("level"), int)]
        highest = max(numeric_levels) if numeric_levels else None
        highest_names = [c["name"] for c in chars if c.get("level") == highest] if highest is not None else []
        factions = sorted({c.get("factionLabel") for c in chars if c.get("factionLabel")})
        real_name = clean(prow.get("real_name"))
        real_first = real_name.split()[0] if real_name else ""
        results.append({
            "playerId": player_id,
            "name": name,
            "mainHandle": clean(prow.get("main_handle")) or name,
            "realFirstName": real_first,
            "characterCount": len(chars),
            "knownWhoisCount": sum(1 for c in chars if c.get("hasWhois")),
            "highestLevel": highest,
            "highestLevelCharacters": highest_names,
            "factions": factions,
            "activeSummary": "unknown",
        })
    return results


def build_affiliation_lookup(root: Path) -> dict[str, str]:
    rows = read_csv(root / "data/derived/character_player_affiliations.csv")
    by_character: dict[str, str] = {}
    for row in rows:
        cid = clean(row.get("character_id"))
        aff = clean(row.get("affiliation_name"))
        if cid and aff and cid not in by_character:
            by_character[cid] = aff
    return by_character


def build_ascii_records(characters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records = []
    for c in characters:
        if not c.get("hasAscii"):
            continue
        if not (c.get("whoisText") or c.get("whoisHtml")):
            continue
        records.append({
            "characterId": c["id"],
            "characterName": c["name"],
            "playerId": c.get("playerId") or "unknown",
            "player": c.get("player") or "Unknown",
            "score": c.get("asciiScore") or 0.0,
            "text": c.get("whoisText") or "",
            "html": c.get("whoisHtml") or "",
        })
    records.sort(key=lambda r: (-float(r.get("score") or 0), str(r.get("characterName") or "").casefold()))
    return records


def build_portrait_file_manifest(root: Path) -> list[str]:
    cards_dir = root / "site/deck-of-chars/assets/cards"
    if not cards_dir.exists():
        return []
    canonical_name = re.compile(r"^[A-Z][A-Za-z0-9_]*(?:-[A-Z][A-Za-z0-9_]*)*\.png$")
    return sorted(
        path.name for path in cards_dir.glob("*.png")
        if canonical_name.fullmatch(path.name)
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive_root", help="Path to mume-character-archive repo root")
    parser.add_argument("output", help="Output JS file, relative to archive root or absolute")
    args = parser.parse_args()

    root = Path(args.archive_root).expanduser().resolve()
    output = Path(args.output)
    if not output.is_absolute():
        output = root / output

    manifest = read_csv(root / "data/derived/character_pages_manifest.csv")
    working_rows = read_csv(root / "data/working/characters.csv")
    players_rows = read_csv(root / "data/working/players.csv")

    working_by_id = {clean(row.get("character_id")): row for row in working_rows}
    affiliation_by_character = build_affiliation_lookup(root)

    characters = [
        build_character(row, working_by_id.get(clean(row.get("character_id")), {}), affiliation_by_character, root)
        for row in manifest
    ]
    characters = deduplicate_accented_characters(characters)
    characters.sort(key=lambda c: str(c.get("name") or "").casefold())

    players = build_players(characters, players_rows)
    ascii_records = build_ascii_records(characters)
    portrait_files = build_portrait_file_manifest(root)

    data = {
        "meta": {
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "source": "mume-character-archive",
            "schema": "deck-of-chars-alpha-compatible",
            "characterCount": len(characters),
            "playerCount": len(players),
            "asciiRecordCount": len(ascii_records),
            "portraitFileCount": len(portrait_files),
        },
        "portraitFiles": portrait_files,
        "characters": characters,
        "players": players,
        "asciiRecords": ascii_records,
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    output.write_text(f"window.DECK_CHARS = {payload};\n", encoding="utf-8")

    print(f"Wrote {output}")
    print(f"Characters: {len(characters)}")
    print(f"Players: {len(players)}")
    print(f"ASCII records: {len(ascii_records)}")
    print(f"Portrait files: {len(portrait_files)}")
    print("Immortal characters:", sum(1 for c in characters if c.get("faction") == "immortal"))


if __name__ == "__main__":
    main()
