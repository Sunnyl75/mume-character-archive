# Deck of Chars mockup v12

Built from v11, preserving the landing/index starting state.

Changes:
- Added uploaded test character image as `assets/cards/card-image-human-warrior-male.png`.
- Test character image appears on identity/name cards and lower character cards.
- Stacked card edges now use clipped full-card edges to reduce the dark vertical alpha/shadow line.
- Edge labels sit further in from the card edge and change colour on hover.
- Whois terminal is widened and given an 80+ character minimum on desktop.
- Search field no longer has the grey outer box; input aligns with the other controls and includes a small search icon.
- Character names are further constrained inside the upper title area of the card.
- Character type/level text remains constrained near the card bottom.
- Trophy overlay remains above trophy card content.


v12 corrected: fixed JavaScript syntax after replacing player-deck behaviour.


v14 changes:
- Rebuilt from the user-uploaded v12 package.
- Replaced `assets/cards/card-trophy-damage-overlay.png` with the newly uploaded replacement.
- Character art now works as a full-card overlay layer, aligned to the exact card bounds.
- Removed the portrait-box image treatment that caused misalignment.
- Trophy cards now layer: trophy base card → character image overlay → text/content → damage overlay.
- Ordinary character cards now layer: card base → character image overlay → text/content.


v16 changes:
- Reverted the failed v15 parchment-fill approach.
- Uses the player deck method for the character deck: full card-sized elements overlap one another.
- Keeps the character deck in a straight horizontal stack, not a fanned player-deck layout.
- The character name card remains on top.
- Underlying category cards remain full card images, offset horizontally, so the visible edge should not expose the black panel background.
- No other page behaviour or layout intentionally changed.


v17 changes:
- Keeps the successful v16 player-deck-style full-card overlap.
- Moves the information cards underneath the main character/name card.
- The character card is now the true top card of the stack.
- The category card edges remain visible to the right.
- Moves the whois terminal further right so the stacked character deck does not overlap it.
- No other behaviour intentionally changed.


v18 changes:
- Fixed the reversed stacking order of the information cards beneath the character/name card.
- The underlying cards now stack in order: Facts, Whois, Clan, Logs, Deeds, Trophies, Sources.
- The character/name card remains on top.
- Removed the bottom symbol from the character card because it interfered with the text.


v19 changes:
- Adjusted the whois box so it sits inside the top panel rather than sliding beyond the right edge.
- Kept the whois box sized for approximately 100 monospace characters on desktop.
- Tightened the whois font slightly to make the 100-character requirement practical inside the panel.
- Removed the character image overlay from the Trophy card in the spread character deck.


v20 changes:
- Fixed the whois terminal so its right border closes inside the top panel.
- Removed the min-width rule that could force the whois terminal beyond the panel edge.
- Kept the whois terminal scaled for roughly 100 monospace characters on desktop.
- Added a “Return to Complete Archive” button beneath the player filter note.
- Made the Deck of Chars title clickable and return to the full archive.
- Removed breadcrumbs above the Deck of Chars title.
- Centered the title.
- Added `assets/images/deck-of-chars-title.png` as an image title styled to match the Bree Legends gold menu aesthetic.

v26 changes:
- Rebuilt from the uploaded v20 package.
- Applied only faction-card and immortal-display changes.
- Fixed the previous inline data issue by JSON-encoding `window.DECK_CHARS` and inserting it with a safe replacement function, preserving escaped newlines/backslashes in ASCII art.
- Added reverse cards for Immortals, Minions of Sauron, and Renegade Zaugurz.
- Added mock characters for all factions.
- Immortals display Immortal / Maia|Valar|Aratar / Cartographer|Wright|Implementor, with no “Level” prefix on the bottom line.
- No lower-card layout changes were added.

v27 changes:
- Fixed new faction backs in lower character decks by forcing them to scale like the Free Peoples back.
- Reduced the lower-deck fan/splay so only a modest edge of the backing cards is visible.
- Added overflow protection to the lower archive/related card grids so decks do not run past the parchment edge.
- Changed the bottom quote to: “Much that once was is lost”.
- Changed and centred the top subheading: “Some that die deserve life. Can you give it to them?”
