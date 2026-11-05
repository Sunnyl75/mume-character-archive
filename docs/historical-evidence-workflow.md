# Historical evidence into the Character Archive

The historical importer connects the July research JSON to the existing archive.
It preserves same-player assertions independently of the Mudlet queue and adds
log references, death observations and trophy snapshots to Deck of Chars.

It imports structured extractions. It does not crawl websites or parse arbitrary
raw gameplay text. The July bundle's sources and unconverted observations remain
available for a later extraction pass. Equipment, skills and map observations
are retained in the source package, but do not yet have normalized importers.

## Import the existing research bundle

Extract `mume_historical_research_master_v1.0.zip` outside the repository, for
example in Downloads. From the repository, preview:

```bash
python3 scripts/import_historical_evidence.py \
  "$HOME/Downloads/mume_historical_research_master_v1.0" \
  --report "$HOME/Downloads/historical-import-review.json"
```

The preview writes only the explicitly requested review report. It lists added
records, proposed player links and unresolved references. It never publishes.
After reviewing, apply the same import:

```bash
python3 scripts/import_historical_evidence.py \
  "$HOME/Downloads/mume_historical_research_master_v1.0" \
  --apply --report "$HOME/Downloads/historical-import-review.json"
python3 scripts/build_whois_queue.py
```

Use the actual extracted directory containing `corpus/` and `website_ingest/`.
Standalone supported JSON files also work, including
`pDorien_whois_queue_candidates_v0.1.json`.

Supported schema prefixes:

- `mume_historical_logs_corpus/`: logical logs, explicit participant names,
  named structured deaths, and `trophy_list.derived_kill_evidence`.
- `mume_player_character_evidence/`: explicit website player/character lists.
- `mume_whois_queue_evidence/`: same-player candidates with preserved evidence.
- `deck_of_chars_log_list/`: curated index titles, dates, links and recovery state.

Legacy corpus copies are not imported a second time. Private-player JSON and
other unsupported inputs are retained without being projected into public data.
Deaths hidden in free-text outcomes or prose, and trophy entries without a
structured owner/victim assertion, require another extraction/review pass.

## Review player identities

New player links default to `needs_review`, so they do not change public player
decks. The link rows retain their evidence IDs and the original assertions.
The importer matches public player handles/IDs exactly; it does not guess that
two differently named player records are the same person from overlapping alts.

To map a source pName to an existing archive player, supply a JSON object:

```json
{"pDorien": "player_0123"}
```

`player_0123` above is an example: choose the real ID from `players.csv`.
Pass this file with `--player-map /path/to/player-map.json` in both preview and
apply. Mapping targets must already exist. Source-specific spelling corrections
are retained in raw evidence; they are not applied as global aliases.

After reviewing the proposed associations, `--accept-links` accepts
high-confidence associations with no conflicting owner. Preview that option
before applying it. Conflicting and lower-confidence links remain reviewable.
Previously accepted, rejected or disputed decisions survive reimport.
For individual decisions, the canonical link table's `status` is the existing
review mechanism; accepted links are consumed by the normal Deck rebuild.

## Collect and import Whois

Load the rebuilt queue in Mudlet:

```text
mha queue load
mha queue status
mha queue delay 5
mha queue batch 500
```

The queue is still one name per line. Relationships stay in archive evidence
and link tables. Names already captured, checked or queued are not added again,
but new relationship evidence is still retained. Run the Whois importer against
all captures, or use the integrated rebuild below. It reuses historical character
IDs by name rather than replacing the character or its relationship records.

## Rebuild and publish

On the publishing branch, one command can import both inputs and rebuild locally:

```bash
python3 scripts/publish_deck.py \
  --historical "$HOME/Downloads/mume_historical_research_master_v1.0" \
  --whois "$HOME/.config/mudlet/profiles/Multi-Users in Middle-earth/mume_whois_archive.json"
```

This leaves new player links awaiting review. If links were already reviewed
through the importer, omit `--historical` and rebuild normally. The publisher
refreshes the queue following imports, validates, rebuilds derived tables, and
exports the Deck and WordPress package. Add `--publish` only when ready to update
the website and the existing publishing connection is configured.

The publisher's `--dry-run` controls remote upload: it still imports and rebuilds
local data. For a read-only import preview, use the historical importer's default
mode instead. The publisher's `--historical` option is not a dry-run importer.
Importer staging is transactional within its CSV/source updates; the whole
rebuild/publishing command is not one transaction.

## Storage and interpretation

| Data | Destination |
| --- | --- |
| Sources and extraction claims | `data/working/sources.csv`, `evidence.csv` |
| Character identities and proposed relationships | `characters.csv`, `players.csv`, `player_character_links.csv` |
| Logical logs and character appearances | `logs.csv`, `log_appearances.csv` |
| Death observations and trophy snapshots | `historical_events.csv` |
| Full curated index, including unrecovered entries | `historical_log_index.csv` |
| Collection work | `whois_queue.csv`, then `exports/mudlet/whois_queue.txt` |
| Immutable source checkpoint and input hashes | `data/incoming/historical/<session>/` |

Reimporting identical input adds no duplicate rows. Source changes receive new
evidence identities; prior observations remain available. Session names identify
immutable inputs; use a new session for changed inputs. The importer stages and
validates data before replacing canonical files, and restores previous tables
if a replacement fails. Do not run simultaneous archive writers.

Death counts are source observations, not a deduplicated lifetime total.
Different logs may show the same death. Trophy counts are minimum counts at a
display date, not kills during that battle; snapshot counts are never summed.
Trophy-only victims are queued without being marked as battle participants.
Unknown outcomes and anonymous/NPC entities do not create named death records.
The July bundle has two mismatched logical-log references; these remain in the
review report and source index rather than being joined by a guessed title.

Public exports use an explicit field selection. Private player data, raw claims
and research notes remain outside historical Deck data. Log links allow HTTP(S)
only. New Logs views show approximate date and linked title; death observations
include their source basis. The existing Trophies controls show dated snapshots.
Existing public-player display rules are unchanged; private names from these
new sources are never copied into the public player table.

## Future app

The import engine (`Importer`) and public-view builder (`historical_views`) are
separate from the interface. An app can run the same preview, review, apply,
queue export, Whois import, local rebuild and publish stages. Acquisition and raw
log extraction should be separate operations with visible progress. A review UI
should resolve player mappings, uncertain observations and duplicate events
before incorporating them into public summaries.

## Checks

```bash
python3 -m unittest discover -s tests -p 'test_historical_import.py' -v
node --check site/deck-of-chars/deck-of-chars.js
node tests/test_historical_ui.cjs
```
