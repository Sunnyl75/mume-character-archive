#!/usr/bin/env python3

import csv
import html
import re
from pathlib import Path


WORKING = Path("data/working")
EVIDENCE = Path("data/evidence/whois")

WHOIS_RECORDS = WORKING / "whois_records.csv"

TEXT_DIR = EVIDENCE / "text"
HTML_DIR = EVIDENCE / "html"
INDEX_CSV = EVIDENCE / "index.csv"


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


def strip_ansi(text):
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text or "")


def html_to_plain(value):
    value = clean(value)
    if not value:
        return ""

    value = html.unescape(value)
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    value = re.sub(r"</p\s*>", "\n", value, flags=re.I)
    value = re.sub(r"<[^>]+>", "", value)
    return strip_ansi(value).strip()


def best_plain_text(row):
    for field in ["raw_text", "plain_text", "text", "body", "whois_text"]:
        value = clean(row.get(field))
        if value:
            return strip_ansi(value).strip()

    raw_html = clean(row.get("raw_html"))
    if raw_html:
        return html_to_plain(raw_html)

    raw_decho = clean(row.get("raw_decho"))
    if raw_decho:
        return strip_ansi(raw_decho).strip()

    return ""


def best_html_body(row):
    raw_html = clean(row.get("raw_html"))
    if raw_html:
        # Preserve existing HTML-ish colour formatting, but wrap it.
        # This assumes the Mudlet export already produced display HTML.
        return raw_html

    plain = best_plain_text(row)
    if plain:
        return html.escape(plain)

    return ""


def character_name(row):
    return clean(
        row.get("character_name")
        or row.get("parsed_character_name")
        or row.get("query_name")
        or "unknown"
    )


def character_id(row):
    return clean(row.get("character_id"))


def whois_id(row):
    return clean(row.get("whois_id") or row.get("capture_id") or row.get("id"))


def descriptor(row):
    race = clean(row.get("parsed_race"))
    cls = clean(row.get("parsed_class"))

    if race and cls and cls != race:
        return f"{race} {cls}"
    return race or cls


def write_text_file(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def write_html_file(path, title, html_body):
    path.parent.mkdir(parents=True, exist_ok=True)

    title_escaped = html.escape(title)
    document = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title_escaped} — MUME whois evidence</title>
<style>
body {{
  margin: 0;
  padding: 1.5rem;
  background: #111;
  color: #ddd;
}}
.mume-whois-block {{
  white-space: pre-wrap;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
  font-size: 0.95rem;
  line-height: 1.35;
}}
</style>
</head>
<body>
<pre class="mume-whois-block">{html_body}</pre>
</body>
</html>
"""
    path.write_text(document, encoding="utf-8")


def main():
    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    HTML_DIR.mkdir(parents=True, exist_ok=True)

    rows = read_csv(WHOIS_RECORDS)
    index_rows = []
    used_slugs = {}

    exported = 0
    skipped = 0

    for row in rows:
        status = clean(row.get("status"))
        if status == "not_found":
            skipped += 1
            continue

        name = character_name(row)
        cid = character_id(row)
        wid = whois_id(row)

        plain = best_plain_text(row)
        html_body = best_html_body(row)

        if not plain and not html_body:
            skipped += 1
            continue

        base_slug = slugify(name)
        slug = base_slug

        # If duplicate names/captures exist, preserve each evidence file distinctly.
        if slug in used_slugs:
            used_slugs[slug] += 1
            slug = f"{base_slug}-{used_slugs[base_slug]}"
        else:
            used_slugs[slug] = 1

        text_rel = Path("data/evidence/whois/text") / f"{slug}.txt"
        html_rel = Path("data/evidence/whois/html") / f"{slug}.html"

        write_text_file(text_rel, plain)
        write_html_file(html_rel, name, html_body)

        index_rows.append({
            "whois_id": wid,
            "character_id": cid,
            "character_name": name,
            "slug": slug,
            "descriptor": descriptor(row),
            "status": status,
            "text_path": str(text_rel),
            "html_path": str(html_rel),
            "has_raw_text": "yes" if clean(row.get("raw_text")) else "no",
            "has_raw_html": "yes" if clean(row.get("raw_html")) else "no",
            "has_raw_decho": "yes" if clean(row.get("raw_decho")) else "no",
            "parse_confidence": clean(row.get("parse_confidence")),
            "notes": clean(row.get("notes")),
        })

        exported += 1

    fieldnames = [
        "whois_id",
        "character_id",
        "character_name",
        "slug",
        "descriptor",
        "status",
        "text_path",
        "html_path",
        "has_raw_text",
        "has_raw_html",
        "has_raw_decho",
        "parse_confidence",
        "notes",
    ]

    write_csv(INDEX_CSV, fieldnames, index_rows)

    print(f"Wrote {INDEX_CSV}")
    print(f"Exported whois evidence files: {exported}")
    print(f"Skipped rows: {skipped}")
    print(f"Text directory: {TEXT_DIR}")
    print(f"HTML directory: {HTML_DIR}")


if __name__ == "__main__":
    main()
