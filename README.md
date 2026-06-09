# MUME Character Archive

This repository is a working archive for historical and current MUME character/player information.

The project combines:

* historical player/character lists
* Mudlet `whois` capture archives
* parsed character descriptors
* candidate social links from `whois` text
* possible clan/guild/group references
* colour-preserved original `whois` display evidence
* generated review reports and static page previews

The long-term goal is to generate reliable character and player pages for a MUME history/wiki site while preserving the original evidence behind every derived claim.

## Core principles

The archive is evidence-first.

Raw source material should be preserved wherever possible. Derived fields such as race, class, faction, gender, player association, and affiliations are secondary interpretations and may require review.

Unknown values are acceptable. The parser should not force classification where the evidence is unclear.

Important distinctions:

* `not_found` means a `whois` query returned no current result. It does not prove the character never existed.
* Player associations from old lists are historical evidence, not necessarily current ownership.
* Extracted mentions are candidate social evidence, not necessarily friendships or confirmed links.
* Possible clan/guild/group references are candidates until reviewed.
* Gender is inferred only from available descriptors or title terms and should retain confidence information.

## Repository structure

```text
data/
  incoming/
    whois/
      mudlet_archives/
      ad_hoc/
      legacy_lists/

  working/
    characters.csv
    whois_records.csv
    players.csv
    player_character_links.csv
    historical_ambiguities.csv
    sources.csv

  reference/
    race_terms.csv
    class_titles.csv
    immortal_ranks.csv
    faction_rules.csv

  derived/
    character_pages_manifest.csv

  evidence/
    whois/
      text/
      html/
      index.csv

    whois_display/
      text/
      html/
      index.csv

exports/
  mudlet/
    whois_queue.txt

reports/
  derived_character_classification.csv
  derived_character_classification_summary.md
  whois_descriptor_classification_report.csv
  whois_descriptor_unknown_terms.md
  whois_possible_character_mentions.csv
  whois_possible_guilds_clans.csv
  whois_ascii_art_candidates.csv
  whois_social_formatting_summary.md
  character_pages_manifest_summary.md
  review_pack_descriptor.md
  review_pack_mentions.md
  review_pack_guilds_clans.md
  review_pack_ascii_art.md

site_preview/
  characters/
```

## Main workflow

Run commands from the repository root:

```bash
cd ~/mume-character-archive
```

### 1. Import Mudlet `whois` archive

The Mudlet archive currently lives at:

```text
/Users/Lewis/.config/mudlet/profiles/Multi-Users in Middle-earth/mume_whois_archive.json
```

Import it into the working CSV files:

```bash
python3 scripts/import_mudlet_whois_archive.py \
  "/Users/Lewis/.config/mudlet/profiles/Multi-Users in Middle-earth/mume_whois_archive.json"
```

If using the cleaned import copy instead:

```bash
python3 scripts/import_mudlet_whois_archive.py \
  "/Users/Lewis/.config/mudlet/profiles/Multi-Users in Middle-earth/mume_whois_archive.import_cleaned.json"
```

### 2. Build or refresh the Mudlet queue

This generates a queue of characters that still need `whois` capture.

```bash
python3 scripts/build_whois_queue.py
```

Output:

```text
exports/mudlet/whois_queue.txt
```

If the queue is empty, all currently known names have either been checked or imported.

### 3. Validate the working data

Run validation after imports and before commits:

```bash
python3 scripts/validate_data.py
```

A clean run should report zero errors. Warnings may indicate incomplete historical data that still needs future enrichment.

### 4. Build descriptor classification reports

This analyses `whois` descriptors against the reference tables.

```bash
python3 scripts/report_whois_descriptor_classification.py
```

Outputs include:

```text
reports/whois_descriptor_classification_report.csv
reports/whois_descriptor_unknown_terms.md
```

This stage derives candidate race, subrace, faction, class, gender, and immortal rank information.

### 5. Extract social, formatting, group, and ASCII-art evidence

```bash
python3 scripts/report_whois_social_and_formatting.py
```

Outputs include:

```text
reports/whois_possible_character_mentions.csv
reports/whois_possible_guilds_clans.csv
reports/whois_ascii_art_candidates.csv
reports/whois_social_formatting_summary.md
```

These outputs are intentionally cautious. Mentions and group references should be treated as candidate evidence until reviewed.

### 6. Create review packs

```bash
python3 scripts/create_review_packs.py
```

Outputs:

```text
reports/review_pack_descriptor.md
reports/review_pack_mentions.md
reports/review_pack_guilds_clans.md
reports/review_pack_ascii_art.md
```

These are human-readable review summaries for checking parser output without opening large CSV files.

### 7. Build derived character classification

```bash
python3 scripts/build_derived_character_classification.py
```

Outputs:

```text
reports/derived_character_classification.csv
reports/derived_character_classification_summary.md
```

This file joins character records, player links, and descriptor-derived classification into a one-row-per-character view.

### 8. Export plain whois evidence

This creates fallback text/HTML evidence from `whois_records.csv`.

```bash
python3 scripts/export_whois_evidence_files.py
```

Outputs:

```text
data/evidence/whois/text/
data/evidence/whois/html/
data/evidence/whois/index.csv
```

This is useful when colour-preserved Mudlet display evidence is unavailable.

### 9. Export colour-preserved Mudlet whois display evidence

This reads the original Mudlet archive directly so that `raw_html`, `raw_decho`, and colour formatting can be preserved.

```bash
python3 scripts/export_whois_display_from_mudlet_archive.py
```

Outputs:

```text
data/evidence/whois_display/text/
data/evidence/whois_display/html/
data/evidence/whois_display/index.csv
```

The exporter strips default black terminal backgrounds such as:

```text
background: rgb(0,0,0)
```

but preserves non-black background colours, because those may be meaningful ASCII art or block-colour formatting.

### 10. Build the character page manifest

```bash
python3 scripts/build_character_pages_manifest.py
```

Outputs:

```text
data/derived/character_pages_manifest.csv
reports/character_pages_manifest_summary.md
```

The manifest joins classification, player links, whois display evidence, mentions, group candidates, and ASCII-art indicators into one build-ready file.

### 11. Build a local static character page preview

```bash
python3 scripts/build_static_character_pages_preview.py
open site_preview/characters/index.html
```

This creates a small local proof-of-concept site under:

```text
site_preview/characters/
```

The preview is intentionally evidence-heavy. It is not the final public design.

## Full rebuild command sequence

From the repo root:

```bash
cd ~/mume-character-archive

python3 scripts/import_mudlet_whois_archive.py \
  "/Users/Lewis/.config/mudlet/profiles/Multi-Users in Middle-earth/mume_whois_archive.import_cleaned.json"

python3 scripts/build_whois_queue.py
python3 scripts/validate_data.py

python3 scripts/report_whois_descriptor_classification.py
python3 scripts/report_whois_social_and_formatting.py
python3 scripts/create_review_packs.py

python3 scripts/build_derived_character_classification.py
python3 scripts/export_whois_evidence_files.py
python3 scripts/export_whois_display_from_mudlet_archive.py

python3 scripts/build_character_pages_manifest.py
python3 scripts/build_static_character_pages_preview.py

python3 scripts/validate_data.py
```

Then open the local preview:

```bash
open site_preview/characters/index.html
```

## Recommended commit checkpoints

After a successful validation and preview build:

```bash
git status
git add README.md \
        scripts \
        data/reference \
        data/derived \
        data/evidence \
        reports \
        site_preview

git commit -m "Document character archive workflow"
git push
```

Avoid committing temporary backup files such as:

```text
*.before_*
*.bak
```

unless they are deliberately being kept as evidence.

## Current known status

At the time this README was created, the manifest summary reported:

```text
characters: 1832
with_player_link: 1693
with_whois_display: 1329
with_colour_whois: 1302
with_mentions: 47
with_ascii_art: 71
with_group_candidates: 101
page_review_needed: 658
```

Classification status counts:

```text
classified: 607
race_only: 563
no_whois_classification: 502
immortal: 98
generic_title_no_class: 48
parser_suspect_or_custom_descriptor: 14
```

Faction counts:

```text
Free Peoples: 688
Minions of Sauron: 542
unknown: 502
Immortals: 98
Renegade Zaugurz: 2
```

## Future planned work

Planned next steps include:

* create a stable query script for archive research
* add reusable commands for clan/guild affiliation analysis
* add reusable commands for gender review
* support ad hoc whois imports
* support imports from other old lists and legacy files
* create stable derived affiliation files
* separate public-facing page data from hidden evidence/review data
* adapt the page preview into the final website or WordPress-compatible design

Possible future query commands:

```bash
python3 scripts/query_character_archive.py summary
python3 scripts/query_character_archive.py clans
python3 scripts/query_character_archive.py gender-review
python3 scripts/query_character_archive.py females
python3 scripts/query_character_archive.py uncertain-gender
python3 scripts/query_character_archive.py review-needed
python3 scripts/query_character_archive.py no-whois
python3 scripts/query_character_archive.py mentions Rik
python3 scripts/query_character_archive.py player Burb
```

## Public display guidance

The generated preview is not the final design.

For public pages, keep the front-facing view simple:

* character name
* associated player, cautiously phrased
* confident race/faction/class information
* original whois display
* selected notable links where useful

Put detailed evidence into collapsible or secondary sections:

* raw whois evidence
* extracted mentions
* possible affiliations
* parser status
* confidence values
* capture IDs
* source paths
* review flags

The archive should remain transparent and evidence-rich, but the public page should not overwhelm the reader with internal parser details# MUME Character Archive

This repository is a historical data archive for **MUME** characters, players, whois records, old game logs, and evidence linking them together.

The long-term goal is to generate website pages for MUME characters and players, using card-style layouts similar to the Mume Bestiary design. Player pages will show associated characters; character pages will show whois data, log appearances, evidence, dates, notes, and links to related adventures.

The archive is evidence-led. A player-character link is treated as a claim supported by one or more sources, not as an unquestioned fact.

## Current status

The current base dataset comes from `PLAYERS.TXT`, a historical “who plays who” list found at:

`https://github.com/iheartdisraptor/mume/blob/master/guide/PLAYERS.TXT`

This source is unusually valuable because it groups many characters by player, but it is still treated as a historical source with subjective notes and possible ambiguity.

## Repository layout

```text
data/
  raw/
    players_txt/
      PLAYERS.TXT
    logs/
      README.md
  working/
    players.csv
    characters.csv
    player_character_links.csv
    sources.csv
    evidence.csv
    historical_ambiguities.csv
    whois_queue.csv
    logs.csv
    log_appearances.csv
    whois_records.csv
  generated/
    initial_parsed_players_with_ambiguity_flags.json

docs/
  data-model.md
  evidence-rules.md
  date-confidence.md

exports/
  mudlet/
    whois_queue.txt

scripts/
  validate_data.py
  build_whois_queue.py
  import_mudlet_whois_archive.py
```

## Important concepts

### Characters can exist without known players

Future data will come from many places: whois output, logs, websites, lists, manual research notes, and other odd evidence. Many characters may be known before their player is known.

That is valid.

The archive should allow:

```text
Character known, player unknown.
```

The archive should reject only broken structure, such as a link pointing to a missing character or missing player.

### Duplicate character names are historical ambiguities

No two active characters can have the same name in MUME at the same time.

If the same character name appears under more than one player group in this archive, the likely explanations are:

1. In early MUME, characters were not tied to accounts and may have been transferred or shared.
2. Less likely, an old character was deleted and a new character later reused the same name.

Such cases should be recorded as historical ambiguities, not automatically treated as parser errors.

### Evidence is first-class

Every major claim should eventually point back to evidence.

Examples of evidence:

- A line in `PLAYERS.TXT`
- A whois capture
- A dated game log
- An undated game log with date bounds
- A forum post or website list
- A manual research note

## Main files

### `data/working/players.csv`

One row per known or inferred player group.

Important fields include:

```text
player_id
main_handle
real_name
notes
primary_source_id
```

### `data/working/characters.csv`

One row per known character name.

A character does not need to have a known player yet.

Important fields include:

```text
character_id
name
race
class
level
status
first_seen
last_seen
notes
```

### `data/working/player_character_links.csv`

Links characters to players where evidence exists.

This is where uncertain or historical relationships are tracked.

Important fields include:

```text
link_id
player_id
character_id
link_type
status
confidence
primary_evidence_id
notes
```

### `data/working/sources.csv`

Records the sources used by the archive.

Examples:

```text
PLAYERS.TXT
old logs
web pages
forum posts
manual notes
whois exports
```

### `data/working/evidence.csv`

Stores evidence claims extracted from sources.

Evidence is used to support player-character links, log dates, whois facts, and later website pages.

### `data/working/whois_queue.csv`

Structured queue of character names to be checked with MUME `whois`.

### `exports/mudlet/whois_queue.txt`

Simple one-name-per-line export for Mudlet.

This file is generated from `data/working/whois_queue.csv`.

## Commands

Run all commands from the repository root:

```bash
cd ~/mume-character-archive
```

### Validate the archive data

```bash
python3 scripts/validate_data.py
```

The validator is deliberately permissive about incomplete historical research.

It allows:

```text
characters with no known player
players with no real name
logs with uncertain dates
partial evidence
historical duplicate-name ambiguity
```

It fails only on structural problems, such as:

```text
duplicate IDs
missing required columns
links pointing to missing records
bad date ranges
invalid status/confidence labels
```

### Rebuild the Mudlet whois queue

```bash
python3 scripts/build_whois_queue.py
```

This reads:

```text
data/working/whois_queue.csv
```

and writes:

```text
exports/mudlet/whois_queue.txt
```

By default, rows already marked as checked are skipped.

### Include already-checked names

```bash
python3 scripts/build_whois_queue.py --include-checked
```

### Export only the first 50 queued names

```bash
python3 scripts/build_whois_queue.py --limit 50
```

### Export only a specific priority

```bash
python3 scripts/build_whois_queue.py --priority high
```

### Write the queue to another file

```bash
python3 scripts/build_whois_queue.py --output exports/mudlet/test_queue.txt
```


### Import Mudlet whois archive captures

The existing Mudlet whois script writes a JSON archive at:

```text
/Users/Lewis/.config/mudlet/profiles/Multi-Users in Middle-earth/mume_whois_archive.json
```

Import it into the repository with:

```bash
python3 scripts/import_mudlet_whois_archive.py "/Users/Lewis/.config/mudlet/profiles/Multi-Users in Middle-earth/mume_whois_archive.json"
```

The importer reads the Mudlet JSON archive and updates:

```text
data/working/sources.csv
data/working/characters.csv
data/working/whois_records.csv
data/working/whois_queue.csv
```

It preserves every individual whois capture in `whois_records.csv`, including failed or low-confidence captures. It uses each record's latest parsed result to update the summary fields in `characters.csv`.

Before writing changes, you can preview the import with:

```bash
python3 scripts/import_mudlet_whois_archive.py "/Users/Lewis/.config/mudlet/profiles/Multi-Users in Middle-earth/mume_whois_archive.json" --dry-run
```

After importing, validate the archive:

```bash
python3 scripts/validate_data.py
```

Then rebuild the Mudlet queue so successfully imported names are skipped next time:

```bash
python3 scripts/build_whois_queue.py
```

Then commit:

```bash
git add data/working/sources.csv data/working/characters.csv data/working/whois_records.csv data/working/whois_queue.csv exports/mudlet/whois_queue.txt
git commit -m "Import Mudlet whois archive captures"
git push
```

## Normal Git workflow

After changing data or scripts:

```bash
git status
git add .
git commit -m "Describe the change"
git push
```

Before committing data changes, run:

```bash
python3 scripts/validate_data.py
```

If the Mudlet whois queue should change, also run:

```bash
python3 scripts/build_whois_queue.py
```

Then include the updated export in the commit.

## Suggested workflow when adding new evidence

1. Add the source to `data/working/sources.csv`.
2. Add the relevant claim or quotation to `data/working/evidence.csv`.
3. Add or update records in `characters.csv`, `players.csv`, or `player_character_links.csv`.
4. If new characters need whois checks, add them to `whois_queue.csv`.
5. Run:

```bash
python3 scripts/validate_data.py
python3 scripts/build_whois_queue.py
```

6. Commit and push:

```bash
git add .
git commit -m "Add evidence from SOURCE_NAME"
git push
```

## Future planned workflow

The archive is expected to grow toward this pipeline:

```text
parsed player lists
+ Mudlet whois captures
+ old game logs
+ manual evidence links
= generated character/player/adventure website pages
```

Future scripts may include:

```text
import_whois_records.py
parse_logs_for_appearances.py
generate_site_data.py
generate_character_pages.py
generate_player_pages.py
```

When those scripts change the workflow, this README should be updated at the same time.
