# MUME Character Archive

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
