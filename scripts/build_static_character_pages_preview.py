#!/usr/bin/env python3

import csv
import html
import shutil
from pathlib import Path


MANIFEST = Path("data/derived/character_pages_manifest.csv")
MENTIONS = Path("reports/whois_possible_character_mentions.csv")
GROUPS = Path("reports/whois_possible_guilds_clans.csv")
ASCII_ART = Path("reports/whois_ascii_art_candidates.csv")

OUT_DIR = Path("site_preview/characters")


PREFERRED_NAMES = {
    "rik",
    "gray",
    "norsu",
    "aalok",
    "aaz",
    "rogon",
    "zaugurz",
    "woland",
    "tauno",
    "mume",
}


def clean(value):
    return (value or "").strip()


def read_csv(path):
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def esc(value):
    return html.escape(clean(value))


def load_manifest():
    rows = read_csv(MANIFEST)
    by_slug = {clean(r.get("page_slug")): r for r in rows if clean(r.get("page_slug"))}
    by_name = {clean(r.get("character_name")).casefold(): r for r in rows if clean(r.get("character_name"))}
    return rows, by_slug, by_name


def group_by_source(rows):
    by_id = {}
    by_name = {}

    for row in rows:
        cid = clean(row.get("source_character_id"))
        name = clean(row.get("source_character_name")).casefold()

        if cid:
            by_id.setdefault(cid, []).append(row)
        if name:
            by_name.setdefault(name, []).append(row)

    return by_id, by_name


def get_related(by_id, by_name, character_id, character_name):
    if character_id and character_id in by_id:
        return by_id[character_id]
    key = character_name.casefold()
    return by_name.get(key, [])


def link_for_name(name, manifest_by_name):
    target = manifest_by_name.get(clean(name).casefold())
    if target:
        return f'<a href="{esc(target["page_slug"])}.html">{esc(name)}</a>'
    return esc(name)


def copy_whois_file(row):
    src_value = clean(row.get("whois_display_html_path"))
    if not src_value:
        return ""

    src = Path(src_value)
    if not src.exists() or not src.is_file():
        return ""

    dst_dir = OUT_DIR / "whois"
    dst_dir.mkdir(parents=True, exist_ok=True)

    dst = dst_dir / src.name
    shutil.copyfile(src, dst)

    return f"whois/{dst.name}"


def metadata_table(row):
    fields = [
        ("Associated player", row.get("player_known_by")),
        ("Player-link confidence", row.get("player_link_confidence")),
        ("Race", row.get("derived_race")),
        ("Subrace", row.get("derived_subrace")),
        ("Faction", row.get("derived_faction")),
        ("Class", row.get("derived_base_class")),
        ("Title", row.get("derived_class_title")),
        ("Gender", row.get("derived_gender")),
        ("Gender confidence", row.get("derived_gender_confidence")),
        ("Immortal rank", row.get("derived_immortal_rank")),
        ("Classification status", row.get("classification_status")),
        ("Colour whois", row.get("has_colour_whois")),
        ("Review needed", row.get("page_review_needed")),
    ]

    lines = ['<table class="meta">']
    for label, value in fields:
        value = clean(value)
        if not value:
            continue
        lines.append(f"<tr><th>{esc(label)}</th><td>{esc(value)}</td></tr>")
    lines.append("</table>")
    return "\n".join(lines)


def mentions_section(rows, manifest_by_name):
    if not rows:
        return "<section><h2>Mentioned characters</h2><p>No extracted character mentions.</p></section>"

    lines = ["<section>", "<h2>Mentioned characters</h2>"]
    lines.append('<p class="note">Automatically extracted candidate mentions. These are evidence links, not necessarily friendships or ownership.</p>')
    lines.append("<ul>")

    seen = set()
    for r in rows[:40]:
        name = clean(r.get("mentioned_name"))
        if not name:
            continue
        key = (name.casefold(), clean(r.get("mention_type")), clean(r.get("heading")))
        if key in seen:
            continue
        seen.add(key)

        linked = link_for_name(name, manifest_by_name)
        mtype = esc(r.get("mention_type"))
        heading = esc(r.get("heading"))
        confidence = esc(r.get("confidence"))
        known = esc(r.get("matched_known_character"))
        evidence = esc(r.get("evidence_excerpt"))

        lines.append(
            f"<li>{linked} "
            f"<span class='tag'>{mtype}</span> "
            f"<span class='tag'>confidence: {confidence}</span> "
            f"<span class='tag'>known: {known}</span>"
            + (f" <span class='tag'>heading: {heading}</span>" if heading else "")
            + f"<br><small>{evidence}</small></li>"
        )

    lines.append("</ul>")
    lines.append("</section>")
    return "\n".join(lines)


def groups_section(rows):
    if not rows:
        return "<section><h2>Possible affiliations / group references</h2><p>No group-reference candidates.</p></section>"

    lines = ["<section>", "<h2>Possible affiliations / group references</h2>"]
    lines.append('<p class="note">Automatically extracted and intentionally cautious. Tolkien lore references and MUME clans may require human distinction.</p>')
    lines.append("<ul>")

    for r in rows[:25]:
        confidence = esc(r.get("confidence"))
        evidence = esc(r.get("evidence_excerpt"))
        lines.append(f"<li><span class='tag'>confidence: {confidence}</span><br><small>{evidence}</small></li>")

    lines.append("</ul>")
    lines.append("</section>")
    return "\n".join(lines)


def ascii_section(rows):
    if not rows:
        return "<section><h2>ASCII art candidates</h2><p>No ASCII art candidate detected.</p></section>"

    lines = ["<section>", "<h2>ASCII art candidates</h2>"]

    def score(row):
        try:
            return float(clean(row.get("ascii_art_score")) or "0")
        except ValueError:
            return 0.0

    for r in sorted(rows, key=score, reverse=True)[:3]:
        lines.append(f"<p><span class='tag'>score: {esc(r.get('ascii_art_score'))}</span></p>")
        lines.append(f"<pre class='ascii'>{esc(r.get('ascii_art_excerpt'))}</pre>")

    lines.append("</section>")
    return "\n".join(lines)


def whois_section(row):
    copied = copy_whois_file(row)
    if not copied:
        return "<section><h2>Original whois</h2><p>No whois display evidence available.</p></section>"

    return f"""
<section>
<h2>Original whois</h2>
<p class="note">Colour-preserved where available. Displayed as captured evidence, separate from derived classification.</p>
<iframe class="whois-frame" src="{esc(copied)}"></iframe>
</section>
"""


def page_template(title, body):
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{esc(title)} — MUME Character Archive Preview</title>
<style>
body {{
  margin: 0;
  padding: 2rem;
  background: #e8dcc3;
  color: #22180f;
  font-family: Georgia, "Times New Roman", serif;
}}
main {{
  max-width: 1100px;
  margin: 0 auto;
  background: rgba(255, 248, 226, 0.88);
  border: 4px solid #6b5135;
  padding: 1.5rem 2rem;
  box-shadow: 0 8px 24px rgba(0,0,0,.25);
}}
h1, h2 {{
  color: #3a2414;
}}
a {{
  color: #682500;
}}
.meta {{
  border-collapse: collapse;
  margin: 1rem 0 2rem;
  width: 100%;
}}
.meta th {{
  text-align: left;
  width: 220px;
  background: #d6c39c;
}}
.meta th, .meta td {{
  border: 1px solid #8c744f;
  padding: .4rem .55rem;
}}
section {{
  margin-top: 2rem;
}}
.tag {{
  display: inline-block;
  font-family: system-ui, sans-serif;
  font-size: .75rem;
  background: #d6c39c;
  border: 1px solid #8c744f;
  border-radius: 4px;
  padding: .05rem .3rem;
  margin-left: .25rem;
}}
.note {{
  color: #60492f;
  font-style: italic;
}}
.ascii {{
  background: #111;
  color: #ddd;
  padding: 1rem;
  overflow-x: auto;
}}
.whois-frame {{
  width: 100%;
  min-height: 520px;
  border: 3px solid #3a2414;
  background: #111;
}}
.index-list li {{
  margin-bottom: .35rem;
}}
</style>
</head>
<body>
<main>
{body}
</main>
</body>
</html>
"""


def build_page(row, manifest_by_name, mentions_by_id, mentions_by_name, groups_by_id, groups_by_name, ascii_by_id, ascii_by_name):
    cid = clean(row.get("character_id"))
    name = clean(row.get("character_name"))
    slug = clean(row.get("page_slug"))

    mentions = get_related(mentions_by_id, mentions_by_name, cid, name)
    groups = get_related(groups_by_id, groups_by_name, cid, name)
    ascii_rows = get_related(ascii_by_id, ascii_by_name, cid, name)

    body = []
    body.append(f"<p><a href='index.html'>← Character index</a></p>")
    body.append(f"<h1>{esc(name)}</h1>")
    body.append(metadata_table(row))
    body.append(mentions_section(mentions, manifest_by_name))
    body.append(groups_section(groups))
    body.append(ascii_section(ascii_rows))
    body.append(whois_section(row))

    path = OUT_DIR / f"{slug}.html"
    path.write_text(page_template(name, "\n".join(body)), encoding="utf-8")
    return path


def choose_preview_rows(rows):
    chosen = []
    seen = set()

    by_name = {clean(r.get("character_name")).casefold(): r for r in rows}

    for name in PREFERRED_NAMES:
        row = by_name.get(name)
        if row and clean(row.get("character_id")) not in seen:
            chosen.append(row)
            seen.add(clean(row.get("character_id")))

    # Add examples with useful features.
    feature_checks = [
        lambda r: r.get("has_colour_whois") == "yes" and r.get("has_ascii_art") == "yes",
        lambda r: r.get("mention_count") != "0",
        lambda r: r.get("group_candidate_count") != "0",
        lambda r: r.get("derived_faction") == "Renegade Zaugurz",
        lambda r: r.get("derived_faction") == "Immortals",
        lambda r: r.get("derived_faction") == "Minions of Sauron",
        lambda r: r.get("classification_status") == "no_whois_classification",
    ]

    for check in feature_checks:
        for row in rows:
            cid = clean(row.get("character_id"))
            if cid in seen:
                continue
            if check(row):
                chosen.append(row)
                seen.add(cid)
                break

    return chosen[:25]


def build_index(rows):
    lines = []
    lines.append("<h1>MUME Character Archive Preview</h1>")
    lines.append("<p class='note'>Local proof of concept. Not final WordPress design.</p>")
    lines.append("<ul class='index-list'>")

    for row in rows:
        slug = esc(row.get("page_slug"))
        name = esc(row.get("character_name"))
        player = esc(row.get("player_known_by")) or "-"
        faction = esc(row.get("derived_faction")) or "-"
        colour = esc(row.get("has_colour_whois"))
        mentions = esc(row.get("mention_count"))
        lines.append(
            f"<li><a href='{slug}.html'>{name}</a> "
            f"<span class='tag'>player: {player}</span> "
            f"<span class='tag'>faction: {faction}</span> "
            f"<span class='tag'>colour whois: {colour}</span> "
            f"<span class='tag'>mentions: {mentions}</span></li>"
        )

    lines.append("</ul>")
    (OUT_DIR / "index.html").write_text(page_template("Character Index", "\n".join(lines)), encoding="utf-8")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    manifest_rows, _by_slug, manifest_by_name = load_manifest()

    mention_rows = read_csv(MENTIONS)
    group_rows = read_csv(GROUPS)
    ascii_rows = read_csv(ASCII_ART)

    mentions_by_id, mentions_by_name = group_by_source(mention_rows)
    groups_by_id, groups_by_name = group_by_source(group_rows)
    ascii_by_id, ascii_by_name = group_by_source(ascii_rows)

    preview_rows = choose_preview_rows(manifest_rows)

    for row in preview_rows:
        build_page(
            row,
            manifest_by_name,
            mentions_by_id,
            mentions_by_name,
            groups_by_id,
            groups_by_name,
            ascii_by_id,
            ascii_by_name,
        )

    build_index(preview_rows)

    print(f"Wrote preview index: {OUT_DIR / 'index.html'}")
    print(f"Character pages: {len(preview_rows)}")


if __name__ == "__main__":
    main()
