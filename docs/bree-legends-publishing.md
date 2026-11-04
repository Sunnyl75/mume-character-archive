# Deck of Chars on Bree Legends

The public destination is `https://breelegends.com/deck-of-chars/`.
The archive stays on the Mac and in its existing Git repository. Publishing
copies only the Deck website and its exported data to the web server.

## Theme integration

`integrations/wordpress/bree-legends-deck.patch` updates the saved Bree Legends
1.1.7 theme to 1.1.8. Apply from the directory containing `bree-legends/` with
`git apply /path/to/bree-legends-deck.patch`, or install the supplied updated
theme ZIP in WordPress. Confirm the active theme is still based on that version
before replacing it; merge these changes into any newer theme instead.

The patch adds an editable Deck of Chars homepage card and a menu link. It
appends the menu link for configured primary menus unless the destination is
already present, and adds it to the fallback menu. The four homepage cards use
two columns on desktop and one on narrower screens. Existing card descriptions
remain saved in WordPress. No WordPress page is required for the static Deck.

## Configure uploading once

SSH access and rsync must be available on the Mac and web host. Establish SSH
access first and verify the server identity through the hosting control panel.
Use the current Bree Legends SSH account and **absolute document root** from
the hosting panel; the older archive worker's server is a separate project.

From `~/mume-character-archive`:

```bash
cp deck-deploy.example.json .deck-deploy.json
```

Edit `.deck-deploy.json` with the current SSH user/host and the absolute path
to the public `deck-of-chars` directory. It is ignored by Git. Configure keys
and nonstandard ports through `~/.ssh/config`; do not put passwords in this file.

## Rebuild and publish

Rebuild from the current imported archive and upload in one command:

```bash
python3 scripts/publish_deck.py --publish
```

To import a fresh Mudlet capture, rebuild and publish together:

```bash
python3 scripts/publish_deck.py --whois "$HOME/.config/mudlet/profiles/Multi-Users in Middle-earth/mume_whois_archive.json" --publish
```

Use your cleaned capture path instead if that is the capture you intend to
import. The same selected capture generates the formatted whois evidence.
Without `--whois`, existing formatted evidence is preserved.

For a local build with no upload, omit `--publish`. To export after your own
existing full archive rebuild, use `--export-only --publish`. Add `--dry-run`
to build and preview upload changes without writing to the web server (the
target directory must already exist for this preview).

The command validates the archive, refreshes classification/affiliation/immortal
evidence and the character manifest, exports the Deck, rejects empty data, and
checks JavaScript syntax when Node is installed. An error stops publication.
It creates `dist/deck-of-chars.zip` and uploads only that public site's files.
It uses delayed rsync updates and never deletes server files. This is not an
atomic release of the entire site; run it once at a time. Back up the initial
server directory before first installation. Database data, reports and raw
captures are not uploaded. Normal rebuilds change generated archive files but
do not create Git commits or push to GitHub.

The included Apache `.htaccess` asks browsers to revalidate HTML, JavaScript and
CSS. If the host uses a CDN or other cache overriding those headers, configure
the same revalidation there or purge it after publication.

After uploading, check the homepage card, primary menu, character search,
player decks, portraits and formatted whois evidence in a browser. The static
Deck's navigation has its own links to Home, Wiki, History, Comics and About;
it does not dynamically inherit later WordPress menu changes.

## Manual first installation

The supplied `deck-of-chars.zip` expands to one `deck-of-chars` folder. Upload
its contents beneath the site's document root at `/deck-of-chars/`, including
`.htaccess`. Keep the existing WordPress `.htaccess` at the document root.
Upload the Deck before installing the theme links so they lead to a working
destination. These packages are prepared for review; no live server was changed.
