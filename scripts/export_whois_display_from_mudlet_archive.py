#!/usr/bin/env python3

import csv
import html
import json
import re
from collections import defaultdict, Counter
from pathlib import Path


WORKING = Path("data/working")
EVIDENCE = Path("data/evidence/whois_display")

ARCHIVE_CANDIDATES = [
    Path("/Users/Lewis/.config/mudlet/profiles/Multi-Users in Middle-earth/mume_whois_archive.import_cleaned.json"),
    Path("/Users/Lewis/.config/mudlet/profiles/Multi-Users in Middle-earth/mume_whois_archive.json"),
]

CHARACTERS = WORKING / "characters.csv"

TEXT_DIR = EVIDENCE / "text"
HTML_DIR = EVIDENCE / "html"
INDEX_CSV = EVIDENCE / "index.csv"


def clean(value):
    return (value or "").strip()


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


def archive_path():
    for path in ARCHIVE_CANDIDATES:
        if path.exists():
            return path
    raise FileNotFoundError("No Mudlet whois archive JSON found.")


def character_lookup():
    by_name = {}
    for row in read_csv(CHARACTERS):
        name = clean(row.get("name") or row.get("character_name"))
        cid = clean(row.get("character_id"))
        if name and cid:
            by_name[name.casefold()] = cid
    return by_name


def capture_name(capture):
    parsed = capture.get("parsed") or {}

    for value in [
        parsed.get("character_name"),
        parsed.get("display_name"),
        capture.get("query_name"),
        parsed.get("query_name"),
    ]:
        value = clean(value)
        if value:
            return value

    return "unknown"


def capture_descriptor(capture):
    parsed = capture.get("parsed") or {}

    race = clean(parsed.get("race"))
    cls = clean(parsed.get("class"))

    if race and cls and cls != race:
        return f"{race} {cls}"

    return race or cls


def capture_sort_key(capture):
    """Prefer final clean, useful display captures.

    Strongly prefer captures that include colour/display fields. Some early
    imported captures have only raw_text and blank capture metadata.
    """

    quality = clean(capture.get("capture_quality"))
    quality_rank = {
        "high": 4,
        "medium": 3,
        "": 2,
        "low": 1,
    }.get(quality, 0)

    raw_html_rank = 3 if clean(capture.get("raw_html")) else 0
    raw_decho_rank = 2 if clean(capture.get("raw_decho")) else 0
    raw_colour_rank = 1 if clean(capture.get("raw_colour_format")) else 0

    source_queue = capture.get("source_queue") or {}
    sent_at = clean(source_queue.get("sent_at"))
    capture_id = clean(capture.get("capture_id"))

    # Capture ids include timestamps in our current Mudlet format.
    timestamp_match = re.search(r":(\d{10,}):", capture_id)
    capture_ts = timestamp_match.group(1) if timestamp_match else ""

    return (
        quality_rank,
        raw_html_rank,
        raw_decho_rank,
        raw_colour_rank,
        sent_at,
        capture_ts,
        capture_id,
    )


def choose_best_captures(captures):
    grouped = defaultdict(list)

    for cap in captures:
        quality = clean(cap.get("capture_quality"))

        if quality == "not_found":
            continue

        # Low captures are usually superseded or contaminated in the cleaned file.
        if quality == "low":
            continue

        if not clean(cap.get("raw_text")) and not clean(cap.get("raw_html")):
            continue

        name = capture_name(cap)
        grouped[name.casefold()].append(cap)

    chosen = []
    for _name_key, group in grouped.items():
        chosen.append(sorted(group, key=capture_sort_key, reverse=True)[0])

    return sorted(chosen, key=lambda cap: capture_name(cap).casefold())


def sanitise_mudlet_html_fragment(fragment):
    """Keep Mudlet foreground colour/display HTML, but remove risky or ugly parts.

    Mudlet's raw_html often includes both foreground and background colour:
        color: rgb(...); background: rgb(0,0,0);

    The foreground colour is useful. The per-span black background creates
    blocky rectangles on the website, so strip background declarations while
    preserving foreground colour.
    """

    fragment = fragment or ""

    fragment = re.sub(r"(?is)<script\b.*?</script>", "", fragment)
    fragment = re.sub(r"(?is)<iframe\b.*?</iframe>", "", fragment)
    fragment = re.sub(r"(?is)<object\b.*?</object>", "", fragment)
    fragment = re.sub(r"(?is)<embed\b.*?>", "", fragment)
    fragment = re.sub(r"(?i)\s+on[a-z]+\s*=\s*(['\"]).*?\1", "", fragment)
    fragment = re.sub(r"(?i)\s+on[a-z]+\s*=\s*[^\s>]+", "", fragment)
    fragment = re.sub(r"(?i)javascript:", "", fragment)

    # Remove only default/near-default black terminal backgrounds.
    # Preserve non-black backgrounds, because they may be meaningful ASCII art
    # such as flags, banners, or deliberate block-colour designs.
    fragment = re.sub(
        r"(?i)background(?:-color)?\s*:\s*rgb\(\s*0\s*,\s*0\s*,\s*0\s*\)\s*;?",
        "",
        fragment,
    )
    fragment = re.sub(
        r"(?i)background(?:-color)?\s*:\s*#(?:000|000000|000000ff)\s*;?",
        "",
        fragment,
    )
    fragment = re.sub(
        r"(?i)background(?:-color)?\s*:\s*black\s*;?",
        "",
        fragment,
    )

    # Tidy style attributes after removals.
    fragment = re.sub(r"style=(['\"])\s*;?\s*\1", "", fragment)
    fragment = re.sub(r"style=(['\"])\s+", r"style=\1", fragment)
    fragment = re.sub(r";\s*(['\"])", r"\1", fragment)

    return fragment


def html_document(title, raw_html, raw_text):
    title_escaped = html.escape(title)

    if clean(raw_html):
        body = sanitise_mudlet_html_fragment(raw_html)
    else:
        body = html.escape(raw_text or "")

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title_escaped} — MUME whois display evidence</title>
<style>
body {{
  margin: 0;
  padding: 1.5rem;
  background: #111;
  color: #ddd;
}}
.mume-whois-display {{
  white-space: pre-wrap;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
  font-size: 0.95rem;
  line-height: 1.35;
}}
</style>
</head>
<body>
<pre class="mume-whois-display">{body}</pre>
</body>
</html>
"""


def write_text(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text((value or "").rstrip() + "\n", encoding="utf-8")


def main():
    source = archive_path()
    data = json.loads(source.read_text(encoding="utf-8"))

    captures = data.get("captures", [])
    name_to_character_id = character_lookup()

    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    HTML_DIR.mkdir(parents=True, exist_ok=True)

    chosen = choose_best_captures(captures)

    index_rows = []
    used_slugs = Counter()

    for cap in chosen:
        name = capture_name(cap)
        name_key = name.casefold()
        cid = name_to_character_id.get(name_key, "")

        base_slug = slugify(name)
        used_slugs[base_slug] += 1
        slug = base_slug if used_slugs[base_slug] == 1 else f"{base_slug}-{used_slugs[base_slug]}"

        text_path = TEXT_DIR / f"{slug}.txt"
        html_path = HTML_DIR / f"{slug}.html"

        raw_text = cap.get("raw_text") or ""
        raw_html = cap.get("raw_html") or ""
        raw_decho = cap.get("raw_decho") or ""

        write_text(text_path, raw_text)
        write_text(html_path, html_document(name, raw_html, raw_text))

        index_rows.append({
            "character_id": cid,
            "character_name": name,
            "query_name": clean(cap.get("query_name")),
            "capture_id": clean(cap.get("capture_id")),
            "capture_quality": clean(cap.get("capture_quality")),
            "descriptor": capture_descriptor(cap),
            "slug": slug,
            "text_path": str(text_path),
            "html_path": str(html_path),
            "has_raw_text": "yes" if clean(raw_text) else "no",
            "has_raw_decho": "yes" if clean(raw_decho) else "no",
            "has_raw_html": "yes" if clean(raw_html) else "no",
            "raw_colour_format": clean(cap.get("raw_colour_format")),
            "source_archive": str(source),
        })

    fieldnames = [
        "character_id",
        "character_name",
        "query_name",
        "capture_id",
        "capture_quality",
        "descriptor",
        "slug",
        "text_path",
        "html_path",
        "has_raw_text",
        "has_raw_decho",
        "has_raw_html",
        "raw_colour_format",
        "source_archive",
    ]

    write_csv(INDEX_CSV, fieldnames, index_rows)

    quality_counts = Counter(clean(c.get("capture_quality")) or "(blank)" for c in captures)
    exported_quality_counts = Counter(row["capture_quality"] or "(blank)" for row in index_rows)
    raw_html_count = sum(1 for row in index_rows if row["has_raw_html"] == "yes")

    print(f"Source archive: {source}")
    print(f"Total captures: {len(captures)}")
    print(f"Exported display whois files: {len(index_rows)}")
    print(f"Exported with raw_html: {raw_html_count}")
    print(f"Wrote {INDEX_CSV}")
    print()
    print("Archive capture quality counts:")
    for value, count in quality_counts.most_common():
        print(f"  {value}: {count}")
    print()
    print("Exported quality counts:")
    for value, count in exported_quality_counts.most_common():
        print(f"  {value}: {count}")


if __name__ == "__main__":
    main()
