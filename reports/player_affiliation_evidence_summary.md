# Player affiliation evidence summary

Inputs:

- `data/incoming/player_affiliations/2003_clans_webpage/source_metadata.csv`
- `data/incoming/player_affiliations/2003_clans_webpage/player_affiliations.csv`
- `data/incoming/player_affiliations/2003_clans_webpage/player_affiliation_members.csv`
- `data/incoming/player_affiliations/2003_clans_webpage/player_affiliation_patterns.csv`

Outputs:

- `data/derived/character_player_affiliations.csv`
- `reports/queries/player_affiliation_candidates.csv`
- `reports/queries/player_affiliation_whois_queue_candidates.csv`
- `exports/mudlet/affiliation_whois_queue.txt`

## Counts

- Affiliation source rows: 17
- Listed member/contact source rows: 108
- Source metadata rows: 1
- Pattern source rows: 45
- Derived affiliation evidence rows: 160
- Whois queue names: 72

## Evidence source counts

- 2003_clans_webpage_member_list: 108
- whois_records_raw_text: 52

## Review status counts

- candidate: 160

## Confidence counts

- medium: 130
- candidate: 17
- medium_high: 13

## Whois queue reason counts

- not_in_characters: 66
- known_character_without_whois: 6

## Top affiliation evidence counts

- Durin's House: 37
- Arda's Army: 26
- Durin's Army: 21
- The Hand of Sauron: 13
- Black Shadow Clan: 11
- Troll Kamikaze Squadron: 11
- Shire Shock Troops: 8
- The Seventh Battalion: 8
- Army of Arthedain: 5
- Damage Inc.: 5
- Scouts of Rivendell: 4
- The Brotherhood of the Squirrel: 4
- Friends to the Death: 3
- Riders of Rohan: 2
- Carrock of Anduin: 1
- Dead Horse Squad: 1

## Interpretation notes

- These are player-organised or socially meaningful affiliations, not built-in race/subrace/faction classifications.
- `source_id`, `source_name`, `source_url`, and `source_date_context` preserve where the historical evidence came from.
- Direct membership/contact rows from the 2003 webpage are historical evidence even when a current whois does not mention the group.
- Pattern matches from whois text are candidates and should be reviewed before public display as accepted affiliation.
- `character_key` is the official searchable MUME name, taken as the first word of a listed display name.
- `display_name` preserves surnames/titles from the source webpage for later public display.
- `affiliation_whois_queue.txt` contains searchable first-word character names from the affiliation source that are missing current whois evidence or are not yet in the character table.
