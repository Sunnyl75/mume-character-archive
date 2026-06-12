# Deck of Chars alpha 0.1 — real data

This version connects the visual mockup to real archive data from:

- `data/derived/character_pages_manifest.csv`
- `data/working/characters.csv`
- `data/working/players.csv`
- `data/evidence/whois_display/text/*.txt`

Generated data file:

- `assets/data/deck-data.js`

Counts:

- Characters: 1832
- Players/groups: 225
- ASCII whois candidates: 71

Notes:

- ASCII whois content is stored in `deck-data.js`, not pasted raw into inline HTML.
- Filtering now uses real character fields.
- Player/character grouping uses `player_id` from the manifest.
- Clan/trophy/log detail cards are intentionally conservative until accepted data joins exist.
