# 2003 player affiliation webpage source

This folder contains a structured first-pass extraction from copied webpage content described as current in 2003.

The source is used for player-organised or socially meaningful clans/guilds/groups only. It should not be mixed with built-in MUME race, subrace, class, or faction classification.

## Files

- `player_affiliations.csv` — one row per clan/guild/group.
- `player_affiliation_members.csv` — one row per listed member, founder, contact, or alias candidate.
- `player_affiliation_patterns.csv` — phrases/acronyms/title patterns used to search existing whois text for candidate affiliation evidence.

## Important modelling notes

- `character_key` is the official searchable MUME name. It is taken as the first word of the listed display name.
- `display_name` preserves the full two-word or title-bearing name from the source webpage for display.
- For example, `Líëf O'le` has `character_key=Líëf`, `display_name=Líëf O'le`, and `name_suffix=O'le`.
- The Hand of Sauron entry lists Diamonium Dagamatri as the member/contact. `Sauron`, `Loremaster`, and title examples such as `Eye of Sauron` are not listed as ordinary members.
- A title phrase such as `of Sauron` is included as a whois matching pattern because it may indicate Hand of Sauron affiliation, but it must be reviewed.
- All rows begin as `candidate` or `needs_context` until reviewed.
