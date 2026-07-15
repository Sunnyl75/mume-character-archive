# MUME Character Archive — Session Handover

Updated: 15 July 2026

## Project Direction

The MUME Character Archive is part of a broader historical reconstruction project for Bree Legends.

The project aims to preserve raw historical evidence and derive structured information about:

- characters
- players
- clans
- logs
- websites
- events
- places
- eras
- relationships within the MUME community

The public presentation should be historical-first. Modern evidence may be collected, but forgotten characters, legendary names, early logs, historical events, and the early MUME web should remain the main focus.

Raw evidence must remain first-class and should not be overwritten by derived classifications.

The primary public website is:

    https://breelegends.com

## Repositories

### Character archive and Deck of Chars

Local repository:

    ~/mume-character-archive

Current working branch:

    deck-of-chars-alpha-0.1

Deck source:

    site/deck-of-chars/

This repository owns:

- Mudlet WHOIS imports
- canonical character/player data
- WHOIS evidence
- derived classifications
- Deck of Chars exporter
- Deck of Chars static website

### Historical archive worker

DreamPress server:

    wp_s68w9h@dp-70dcd19edd.dreamhostps.com

Server repository:

    ~/tools/mume-archive

GitHub repository:

    Sunnyl75/mume-archive-worker

This separate repository owns:

- Wayback discovery
- historical website crawling
- local preservation of historical webpages
- future log discovery and parsing
- reconstruction of the early MUME web

Do not confuse the archive-worker repository with the character archive repository.

## Current Deck of Chars State

The complete Deck runs locally as a static website from:

    ~/mume-character-archive/site/deck-of-chars/

To run it:

    cd ~/mume-character-archive/site/deck-of-chars
    python3 -m http.server 9000

Then open:

    http://localhost:9000

The static-site pipeline has been successfully tested:

    archive data
        -> exporter
        -> assets/data/deck-data.js
        -> HTML/CSS/JavaScript Deck
        -> local browser

The immediate deployment goal is to place this working proof of concept on:

    breelegends.com/deck-of-chars/

The Deck is a soft-launch alpha. It does not need to be fully polished before deployment.

## Work Completed Recently

- Confirmed that the complete Deck is held in the Git-controlled local repository.
- Confirmed that the Deck runs successfully as a static website.
- Removed the hardcoded Diamonium ASCII loading example.
- Replaced the previous Deck heading with:

    assets/images/deck-of-chars-logo.png

- Centred the title image, tagline and decorative divider.
- Added the parchment scroll artwork:

    assets/images/scroll-pop-up.png

- Rebuilt the scroll popup so it has:
  - a fixed title region
  - an independently scrollable body
  - a fixed footer/tagline
  - source subheadings
  - dividers between source types
- Consolidated the accumulated experimental scroll CSS into one main scroll-layout section.
- Adjusted the footer tagline upward into the lower parchment area.
- Documented the progressive portrait naming and fallback intention in:

    site/deck-of-chars/README.md

## Important Presentation Decisions

### WHOIS

WHOIS should use the existing terminal-style side panel.

WHOIS should not be displayed inside the parchment scroll because:

- WHOIS formatting is often wide
- the colour-preserving terminal presentation already exists
- evidence and internal source information belong under Sources

The WHOIS card should eventually reveal or focus the existing WHOIS terminal rather than call:

    openScroll('whois')

### Scroll popup

The parchment scroll is intended for:

- sources
- logs
- clan history
- historical events
- biographies
- other archival reference material

Its title, scrollable body and footer should remain independently positioned.

Long source lists should scroll inside the parchment without moving the title or footer.

### Sources

The current source display still exposes some internal archive identifiers and file paths.

Eventually these should become human-readable source records, for example:

    Whois record
    Retired Immortals List
    ElvenRunes biography
    Wayback snapshot

The canonical internal identifiers should remain in the archive but should not normally be the public-facing label.

### Portrait overlays

The portrait system should be progressive.

Initial broad race images should work immediately. More specific race/class/gender/subrace images should automatically replace broader images as they are added.

Canonical qualifier order:

    Race-Class-Gender-Subrace

Rules:

- hyphens separate qualifiers
- underscores join words within one qualifier
- unknown qualifiers are omitted
- subrace is optional
- not every combination needs artwork

Example:

    Human-Warrior-Male-Black_Numenorean.png

Intended fallback:

    Human-Warrior-Male-Black_Numenorean.png
    Human-Warrior-Male.png
    Human-Warrior.png
    Human.png
    Unknown.png

Existing artwork may still use the prefix:

    Card-Image-

Before implementing the selector, inspect the actual current filenames and decide whether to preserve that prefix or rename the artwork consistently.

## Immediate Next Tasks

1. Inspect and implement the portrait-overlay selection system.
2. Begin with broad race portraits, then fall back progressively to more specific artwork when files exist.
3. Change the WHOIS card so it reveals/focuses the existing terminal panel rather than opening a parchment popup.
4. Test the Deck locally after those changes.
5. Deploy the working static Deck to breelegends.com.
6. Identify the current Bree Legends WordPress theme source and place it under Git if it is not already version-controlled.
7. Add Deck of Chars to the site menu and homepage.

## Future Organisation Goal

Create a canonical project ledger or master project document in Git.

It should eventually contain:

- project vision
- evidence and privacy philosophy
- repository ownership
- architecture
- data model
- presentation standards
- decisions made
- active priorities
- completed milestones
- known technical debt
- deployment procedures

The repository should become the long-term memory of the project. ChatGPT contexts should be temporary workspaces rather than the only record of decisions.

A likely future document is:

    docs/PROJECT_LEDGER.md

or:

    docs/MASTER_PROJECT_DOCUMENT.md

This is a future organisational task and should not delay the current Deck proof-of-concept deployment.

## Working Method for the Next Context

Before changing code:

1. Read this handover.
2. Inspect the actual current files.
3. Use narrow, evidence-based patches.
4. Do not guess at code that has not been shown.
5. Avoid broad rewrites of the Deck.
6. Prefer exporter/data fixes before duplicating historical logic in the browser.
7. Keep Git as the source of truth.


---

## Session Update (15 July 2026)

- Scroll popup rebuilt around the parchment artwork.
- Scroll now has:
  - fixed title
  - independently scrolling evidence area
  - fixed footer
  - structured source sections with headings and dividers.
- Scroll layout is close to complete. Remaining work is visual polish.
- WHOIS should no longer use the scroll. It should reveal the existing terminal viewer.
- Next priority is implementing progressive portrait selection and fallback.
- After that, deploy the Deck of Chars proof-of-concept to breelegends.com.

