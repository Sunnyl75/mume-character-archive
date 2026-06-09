#!/usr/bin/env python3

import csv
import html
import re
from collections import Counter, defaultdict
from pathlib import Path


WORKING = Path("data/working")
REPORTS = Path("reports")

WHOIS_RECORDS = WORKING / "whois_records.csv"
CHARACTERS = WORKING / "characters.csv"

OUT_MENTIONS = REPORTS / "whois_possible_character_mentions.csv"
OUT_GROUPS = REPORTS / "whois_possible_guilds_clans.csv"
OUT_ASCII = REPORTS / "whois_ascii_art_candidates.csv"
OUT_SUMMARY = REPORTS / "whois_social_formatting_summary.md"


LIST_HEADINGS = {
    "pukes",
    "puke",
    "evil",
    "evils",
    "good",
    "goods",
    "darkies",
    "darkie",
    "freeps",
    "freepside",
    "orcs",
    "trolls",
    "friends",
    "friend",
    "enemies",
    "enemy",
    "mates",
    "legends",
    "heroes",
    "victims",
    "kills",
    "killed",
    "clan",
    "guild",
    "group",
    "team",
    "crew",
    "order",
    "house",
    "tribe",
    "warband",
    "company",
    "brotherhood",
    "sisterhood",
}

GROUP_KEYWORDS = {
    "guild",
    "clan",
    "tribe",
    "order",
    "house",
    "company",
    "brotherhood",
    "sisterhood",
    "warband",
    "crew",
    "team",
    "legion",
    "guard",
    "riders",
    "army",
    "servants",
    "followers",
    "circle",
}

COMMON_WORDS = {
    "A", "An", "And", "Are", "As", "At", "Be", "But", "By", "For", "From",
    "Good", "Evil", "Darkies", "Pukes", "Free", "The", "This", "That", "These",
    "Those", "To", "Of", "On", "Or", "In", "Into", "With", "Without", "Who",
    "What", "When", "Where", "Why", "How", "Level", "Legend", "Legends",
    "Warrior", "Mage", "Cleric", "Scout", "Orc", "Troll", "Elf", "Dwarf",
    "Man", "Hobbit", "Maia", "Vala", "Arata",
}


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


def normalise_name(value):
    value = clean(value)
    value = re.sub(r"^[^A-Za-zÀ-ÖØ-öø-ÿ]+", "", value)
    value = re.sub(r"[^A-Za-zÀ-ÖØ-öø-ÿ'’-]+$", "", value)
    return value


def is_name_like(value):
    name = normalise_name(value)

    if not (2 <= len(name) <= 24):
        return False

    if name in COMMON_WORDS:
        return False

    if not re.match(r"^[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’-]*$", name):
        return False

    # Avoid all-uppercase shouting/acronyms unless very short names are known later.
    if len(name) > 3 and name.isupper():
        return False

    return True


def split_name_candidates(text):
    text = clean(text)
    if not text:
        return []

    # Remove common trailing comments after obvious separators.
    text = re.sub(r"\s+[–—-]\s+.*$", "", text)

    if "," in text or ";" in text:
        raw_parts = re.split(r"[,;]", text)
    else:
        raw_parts = re.split(r"\s+", text)

    names = []
    for part in raw_parts:
        candidate = normalise_name(part)
        if is_name_like(candidate):
            names.append(candidate)

    return names


def strip_ansi(text):
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text or "")


def record_text(row):
    candidates = [
        row.get("raw_text"),
        row.get("raw_decho"),
        row.get("raw_html"),
        row.get("body"),
        row.get("text"),
        row.get("whois_text"),
    ]

    for value in candidates:
        value = clean(value)
        if value:
            value = html.unescape(value)
            value = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
            value = re.sub(r"<[^>]+>", "", value)
            return strip_ansi(value)

    return ""


def row_id(row):
    return clean(row.get("whois_id") or row.get("capture_id") or row.get("id"))


def character_id(row):
    return clean(row.get("character_id"))


def character_name(row):
    return clean(row.get("character_name") or row.get("parsed_character_name") or row.get("query_name"))


def whois_descriptor(row):
    parts = []
    race = clean(row.get("parsed_race"))
    cls = clean(row.get("parsed_class"))

    if race:
        parts.append(race)
    if cls and cls not in parts:
        parts.append(cls)

    return " ".join(parts).strip()


def compact_text_excerpt(text, needle="", max_chars=900):
    """Return a review-friendly excerpt from the whois text.

    If needle is present, centre the excerpt around the first occurrence.
    Otherwise return the start of the whois text.
    """
    text = re.sub(r"\n{3,}", "\n\n", text or "").strip()
    if not text:
        return ""

    if needle and needle in text:
        pos = text.find(needle)
        start = max(0, pos - 350)
        end = min(len(text), pos + len(needle) + 350)
        excerpt = text[start:end].strip()

        if start > 0:
            excerpt = "…\n" + excerpt
        if end < len(text):
            excerpt = excerpt + "\n…"

        return excerpt[:max_chars]

    return text[:max_chars]


def load_known_names():
    names = set()

    for row in read_csv(CHARACTERS):
        name = clean(row.get("character_name") or row.get("name"))
        if name:
            names.add(name.casefold())

    for row in read_csv(WHOIS_RECORDS):
        name = character_name(row)
        if name:
            names.add(name.casefold())

    return names


def confidence_for_name(name, known_names, base="medium"):
    if name.casefold() in known_names:
        return "high"

    return base


def extract_heading_name_lists(lines, row, known_names):
    rows = []
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        m = re.match(r"^([A-Za-z][A-Za-z /_-]{1,32})\s*:\s*(.*)$", line)
        if not m:
            i += 1
            continue

        heading = clean(m.group(1))
        heading_key = heading.casefold().strip()
        rest = clean(m.group(2))

        if heading_key not in LIST_HEADINGS:
            i += 1
            continue

        evidence_lines = [line]
        candidate_text = rest

        # Handle:
        # Pukes:
        #   Name
        #   Name
        if not candidate_text:
            j = i + 1
            continuation = []
            while j < len(lines):
                next_line = lines[j].strip()
                if not next_line:
                    break
                if re.match(r"^[A-Za-z][A-Za-z /_-]{1,32}\s*:", next_line):
                    break
                if len(continuation) >= 8:
                    break
                continuation.append(next_line)
                evidence_lines.append(lines[j])
                j += 1
            candidate_text = ", ".join(continuation)

        for name in split_name_candidates(candidate_text):
            rows.append({
                "source_whois_id": row_id(row),
                "source_character_id": character_id(row),
                "source_character_name": character_name(row),
                "whois_descriptor": whois_descriptor(row),
                "whois_text_excerpt": compact_text_excerpt(record_text(row), " / ".join(evidence_lines)),
                "mentioned_name": name,
                "mention_type": "heading_name_list",
                "heading": heading,
                "evidence_excerpt": " / ".join(evidence_lines)[:500],
                "confidence": confidence_for_name(name, known_names, "medium"),
                "matched_known_character": "yes" if name.casefold() in known_names else "no",
            })

        i += 1

    return rows


def extract_comma_name_lists(lines, row, known_names):
    rows = []

    for line in lines:
        stripped = line.strip()

        # Avoid normal prose. We want compact list-like lines.
        if "," not in stripped:
            continue
        if len(stripped) > 180:
            continue

        names = split_name_candidates(stripped)
        if len(names) < 3:
            continue

        for name in names:
            rows.append({
                "source_whois_id": row_id(row),
                "source_character_id": character_id(row),
                "source_character_name": character_name(row),
                "whois_descriptor": whois_descriptor(row),
                "whois_text_excerpt": compact_text_excerpt(record_text(row), stripped),
                "mentioned_name": name,
                "mention_type": "comma_name_list",
                "heading": "",
                "evidence_excerpt": stripped[:500],
                "confidence": confidence_for_name(name, known_names, "low"),
                "matched_known_character": "yes" if name.casefold() in known_names else "no",
            })

    return rows


def extract_quoted_speakers(lines, row, known_names):
    rows = []

    patterns = [
        (r"^([A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’-]{1,24})\s+(?:tells you|told you|narrates|says|said|asks|asked|shouts|shouted|sings|sang)\b", "quoted_speaker"),
        (r"^<[^>]+>\s*([A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’-]{1,24})\s+(?:tells you|narrates|says|asks|shouts)\b", "quoted_speaker"),
    ]

    for line in lines:
        stripped = line.strip()
        for pattern, mention_type in patterns:
            m = re.search(pattern, stripped)
            if not m:
                continue

            name = normalise_name(m.group(1))
            if not is_name_like(name):
                continue

            rows.append({
                "source_whois_id": row_id(row),
                "source_character_id": character_id(row),
                "source_character_name": character_name(row),
                "whois_descriptor": whois_descriptor(row),
                "whois_text_excerpt": compact_text_excerpt(record_text(row), stripped),
                "mentioned_name": name,
                "mention_type": mention_type,
                "heading": "",
                "evidence_excerpt": stripped[:500],
                "confidence": confidence_for_name(name, known_names, "medium"),
                "matched_known_character": "yes" if name.casefold() in known_names else "no",
            })

    return rows


def extract_group_candidates(lines, row):
    rows = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        lower = stripped.casefold()
        if not any(keyword in lower for keyword in GROUP_KEYWORDS):
            continue

        confidence = "low"

        if re.search(r"\b(guild|clan|tribe|order|house|company|brotherhood|sisterhood)\b", lower):
            confidence = "medium"

        if re.search(r"\b(member|leader|lord|lady|master|mistress|servant|follower|captain|founder)\b", lower):
            confidence = "medium"

        rows.append({
            "source_whois_id": row_id(row),
            "source_character_id": character_id(row),
            "source_character_name": character_name(row),
            "whois_descriptor": whois_descriptor(row),
            "whois_text_excerpt": compact_text_excerpt(record_text(row), stripped),
            "possible_guild_or_clan": "",
            "evidence_type": "group_keyword_line",
            "evidence_excerpt": stripped[:500],
            "confidence": confidence,
            "needs_review": "yes",
        })

    return rows


def ascii_line_score(line):
    if not line:
        return 0.0

    stripped = line.rstrip("\n")
    content = stripped.strip()

    if not content:
        return 0.0

    # Exclude common non-art fragments from MUME output.
    if re.match(r"^!?#?\s*[A-Z]{0,4}\s*>$", content):
        return 0.0

    if re.match(r"^[\d\s/]+(?:\([^)]+\))?$", content):
        return 0.0

    if re.search(r"\b(pkills|pkdeaths|mobdeaths|deaths|warpoints|login|retired|level)\b", content, re.I):
        return 0.0

    # Quote prose often has punctuation, but should not count as ASCII art.
    letters = sum(1 for ch in content if ch.isalpha())
    symbols = sum(1 for ch in content if ch in r"/\|_-+=*#~`'.:;^<>[]{}()")
    non_space = sum(1 for ch in content if not ch.isspace())
    spaces = sum(1 for ch in stripped if ch.isspace())

    if non_space == 0:
        return 0.0

    letter_ratio = letters / non_space
    symbol_ratio = symbols / non_space
    spacing_ratio = spaces / max(len(stripped), 1)

    score = 0.0

    # ASCII art is usually symbol-heavy, not prose-heavy.
    if symbol_ratio >= 0.55:
        score += 2.0
    elif symbol_ratio >= 0.40:
        score += 1.0

    if letter_ratio <= 0.35 and len(content) >= 8:
        score += 1.0

    if re.search(r"([_/\\|*#=~.-])\1{2,}", content):
        score += 1.0

    if spacing_ratio >= 0.35 and len(stripped) >= 12:
        score += 0.5

    if re.search(r"[/\\][ _./\\|'-]{3,}[/\\|]", content):
        score += 1.0

    # Short lines are only useful as part of a larger cluster.
    if len(content) <= 5:
        score -= 1.0

    return max(score, 0.0)


def detect_ascii_art(lines, row):
    scored = [(idx, line, ascii_line_score(line)) for idx, line in enumerate(lines)]
    interesting = [(idx, line, score) for idx, line, score in scored if score >= 1.5]

    if not interesting:
        return None

    clusters = []
    current = []
    last_idx = None

    for idx, line, score in interesting:
        if last_idx is None or idx <= last_idx + 2:
            current.append((idx, line, score))
        else:
            clusters.append(current)
            current = [(idx, line, score)]
        last_idx = idx

    if current:
        clusters.append(current)

    best = max(clusters, key=lambda cluster: (len(cluster), sum(item[2] for item in cluster)))
    line_count = len(best)
    score = round(sum(item[2] for item in best), 2)

    # Avoid quote/stat/prompt false positives.
    if line_count < 3 and score < 5.0:
        return None

    excerpt = "\n".join(item[1] for item in best[:16])

    return {
        "source_whois_id": row_id(row),
        "source_character_id": character_id(row),
        "source_character_name": character_name(row),
        "whois_descriptor": whois_descriptor(row),
        "whois_text_excerpt": compact_text_excerpt("\n".join(lines), excerpt),
        "has_ascii_art": "yes",
        "ascii_art_score": str(score),
        "ascii_art_line_count": str(line_count),
        "ascii_art_excerpt": excerpt[:1000],
    }


def main():
    REPORTS.mkdir(parents=True, exist_ok=True)

    rows = read_csv(WHOIS_RECORDS)
    known_names = load_known_names()

    mention_rows = []
    group_rows = []
    ascii_rows = []

    empty_text_count = 0

    for row in rows:
        status = clean(row.get("status"))
        if status == "not_found":
            continue

        text = record_text(row)
        if not text:
            empty_text_count += 1
            continue

        lines = text.splitlines()

        mention_rows.extend(extract_heading_name_lists(lines, row, known_names))
        mention_rows.extend(extract_comma_name_lists(lines, row, known_names))
        mention_rows.extend(extract_quoted_speakers(lines, row, known_names))
        group_rows.extend(extract_group_candidates(lines, row))

        ascii_candidate = detect_ascii_art(lines, row)
        if ascii_candidate:
            ascii_rows.append(ascii_candidate)

    mention_fields = [
        "source_whois_id",
        "source_character_id",
        "source_character_name",
        "whois_descriptor",
        "whois_text_excerpt",
        "mentioned_name",
        "mention_type",
        "heading",
        "evidence_excerpt",
        "confidence",
        "matched_known_character",
    ]

    group_fields = [
        "source_whois_id",
        "source_character_id",
        "source_character_name",
        "whois_descriptor",
        "whois_text_excerpt",
        "possible_guild_or_clan",
        "evidence_type",
        "evidence_excerpt",
        "confidence",
        "needs_review",
    ]

    ascii_fields = [
        "source_whois_id",
        "source_character_id",
        "source_character_name",
        "whois_descriptor",
        "whois_text_excerpt",
        "has_ascii_art",
        "ascii_art_score",
        "ascii_art_line_count",
        "ascii_art_excerpt",
    ]

    write_csv(OUT_MENTIONS, mention_fields, mention_rows)
    write_csv(OUT_GROUPS, group_fields, group_rows)
    write_csv(OUT_ASCII, ascii_fields, ascii_rows)

    mention_type_counts = Counter(row["mention_type"] for row in mention_rows)
    mention_heading_counts = Counter(row["heading"] for row in mention_rows if row["heading"])
    matched_counts = Counter(row["matched_known_character"] for row in mention_rows)

    summary = []
    summary.append("# Whois Social and Formatting Report")
    summary.append("")
    summary.append(f"Whois rows scanned: {len(rows)}")
    summary.append(f"Rows with no usable raw text: {empty_text_count}")
    summary.append("")
    summary.append("## Output files")
    summary.append("")
    summary.append(f"- `{OUT_MENTIONS}`")
    summary.append(f"- `{OUT_GROUPS}`")
    summary.append(f"- `{OUT_ASCII}`")
    summary.append("")
    summary.append("## Mention candidates")
    summary.append("")
    summary.append(f"Total mention rows: {len(mention_rows)}")
    summary.append("")
    summary.append("### Mention type counts")
    summary.append("")
    for value, count in mention_type_counts.most_common():
        summary.append(f"- {value}: {count}")
    summary.append("")
    summary.append("### Heading counts")
    summary.append("")
    for value, count in mention_heading_counts.most_common(30):
        summary.append(f"- {value}: {count}")
    summary.append("")
    summary.append("### Matched known character counts")
    summary.append("")
    for value, count in matched_counts.most_common():
        summary.append(f"- {value}: {count}")
    summary.append("")
    summary.append("## Group/guild/clan candidates")
    summary.append("")
    summary.append(f"Total group rows: {len(group_rows)}")
    summary.append("")
    summary.append("## ASCII art candidates")
    summary.append("")
    summary.append(f"Total ASCII art candidate rows: {len(ascii_rows)}")
    summary.append("")
    summary.append("Top ASCII candidates:")
    summary.append("")
    for row in sorted(ascii_rows, key=lambda r: float(r["ascii_art_score"]), reverse=True)[:20]:
        summary.append(
            f"- {row['source_character_name']}: score {row['ascii_art_score']}, "
            f"{row['ascii_art_line_count']} line(s)"
        )

    OUT_SUMMARY.write_text("\n".join(summary) + "\n", encoding="utf-8")

    print(f"Wrote {OUT_MENTIONS}")
    print(f"Wrote {OUT_GROUPS}")
    print(f"Wrote {OUT_ASCII}")
    print(f"Wrote {OUT_SUMMARY}")
    print()
    print(f"Mention rows: {len(mention_rows)}")
    print(f"Group rows: {len(group_rows)}")
    print(f"ASCII art candidates: {len(ascii_rows)}")
    print(f"Rows with no usable raw text: {empty_text_count}")


if __name__ == "__main__":
    main()
