=== Bree Legends — Deck of Chars ===
Requires at least: 6.2
Requires PHP: 8.1
Stable tag: 1.0.1
License: GPL-3.0-or-later

Illustrated MUME character archive with a data-only publishing connection.

== Installation ==
Upload the ZIP under Plugins > Add New Plugin > Upload Plugin and activate.
Activation creates /deck-of-chars/ if no page already uses that slug.
If it already exists, its content is preserved: add [bree_deck_of_chars] to it.
Open Tools > Deck of Chars to view the page and manage character updates.

Install the accompanying Bree Legends 1.1.8 theme update to add the homepage
card and fallback menu link. No SFTP connection is required for either ZIP.

== Updating character data ==
Create a publishing key under Tools > Deck of Chars, then run the archive's
python3 scripts/publish_deck.py --setup-wordpress command on your Mac.
Enter the site URL and key there. Do not share the key in chat or commit it.
Then python3 scripts/publish_deck.py --publish rebuilds and uploads character data.

Manual fallback: upload dist/deck-data.json through Tools > Deck of Chars.
The plugin validates complete updates before replacing the published data.
Plugin and theme updates preserve the published data and publishing key.
Deactivation retains the page and data; no site content is deleted.

== Remote publishing ==
HTTPS endpoints: /wp-json/bree-deck/v1/status and /wp-json/bree-deck/v1/data.
The publishing key authorizes only status checks and character data updates.
Only a SHA-256 hash of the key is stored by WordPress. Revoke or replace it
from Tools > Deck of Chars. Public data is readable without authentication,
as it is the content displayed in the public Deck. No external service is
contacted by the plugin. Remote access still depends on the host allowing
these requests; dashboard JSON upload remains available if it does not.
