# Deck of Chars on Bree Legends

The public destination is `https://breelegends.com/deck-of-chars/`.
The archive stays on the Mac and in its existing Git repository. Publishing
copies only the Deck website and its exported data to the web server.

## Install through WordPress (current Bree Legends hosting)

Bree Legends uses WordPress.com hosting with plugin/theme uploads, without
SFTP access on the current plan. Use the dashboard route below. The SSH
configuration later in this document is only for other hosting setups.

1. Upload `bree-deck-of-chars-1.0.1.zip` through Plugins → Add New Plugin →
   Upload Plugin, then activate it.
2. Open Tools → Deck of Chars → View Deck of Chars. Activation creates the
   published `/deck-of-chars/` page if that slug is free. An existing page is
   preserved; add `[bree_deck_of_chars]` to it if instructed.
3. Upload the accompanying Bree Legends 1.1.9 theme ZIP through Appearance →
   Themes → Add New → Upload Theme. Choose to replace the existing 1.1.7 theme
   when prompted. This adds the homepage card and the fallback menu link.
4. The initial plugin package contains the GitHub archive snapshot: 2,574
   characters and 225 players. Rebuild from your current local archive to
   publish any newer data or artwork.

### Connect the Mac once

Under Tools → Deck of Chars, click Create publishing key. On your Mac, from
the updated archive repository, run:

```bash
python3 scripts/publish_deck.py --setup-wordpress
```

Enter `https://breelegends.com` and paste the key at the hidden prompt. The
command verifies the connection before saving a private local token file.
The key authorizes only Deck data updates; WordPress stores its hash. Never
paste it into chat. The token and deployment configuration are ignored by Git.

Then rebuild and publish automatically with:

```bash
python3 scripts/publish_deck.py --publish
```

Add `--whois "/path/to/your/mume_whois_archive.json"` to import a fresh capture
as part of that command. `--dry-run` rebuilds and verifies the connection
without changing the published data. Use the WordPress Tools page to revoke
or replace the key at any time. If hosting blocks the API, upload the generated
`dist/deck-data.json` through Tools → Deck of Chars instead. The live connection
must be tested after plugin installation; it was not available during packaging.

Every build also produces `dist/bree-deck-of-chars-1.0.1.zip`, an installable
plugin with the current website assets. Remote data publication updates data
only: new portraits or frontend changes require uploading the rebuilt plugin
ZIP through WordPress. Stored character updates survive plugin/theme updates.
The plugin does not import raw captures or run the archive's Python code on
WordPress. Rebuilding and uploading remain one command on the Mac.

### Validation

PHP 8.3 syntax checks pass for the plugin and changed theme files. Standalone
PHP contract tests cover the bundled schema, correct/incorrect/revoked update
keys, preserving published data after an invalid update, unsafe portrait paths,
duplicate character IDs, and preserving an existing page during activation.
Those tests stub WordPress services, so live WordPress.com installation and
remote publication still need verification. JavaScript syntax and publisher
HTTPS/configuration checks also pass.

## Theme integration

`integrations/wordpress/bree-legends-deck.patch` updates the saved Bree Legends
1.1.7 theme to 1.1.9. Apply from the directory containing `bree-legends/` with
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


## Full Parchment Width template (theme 1.1.9)

Edit a normal page and select **Full Parchment Width** in Page settings →
Template, then update the page. Content and the heading divider fill the
existing parchment interior. The template retains the existing frame and
responsive padding, and inserts no sidebar. Its block content-size variables
allow the default constrained block layout to use this available width;
wide/full alignment stays inside the parchment. The older Full Width Page
option for wider embedded tools remains available unchanged.

The theme ZIP was checked against the packaged source files; the generated
patch applies to the saved 1.1.7 source. PHP 8.3 syntax checks passed for the
new template, homepage and theme functions. Live appearance should be checked
after installation on WordPress.com.


## Yada Wiki layouts (theme 1.1.10)

The separate wiki menu uses the `yada_wiki` content type. Theme 1.1.10 registers
Full Parchment Width for both `page` and `yada_wiki`, so WordPress can display
the template selector for wiki entries too. Edit an entry through the Wiki
menu, choose Full Parchment Width in Template (editor sidebar or Attributes
box), and update it. This is a per-entry choice; other wiki layouts remain
unchanged. The PHP minimum remains 8.0, as declared in 1.1.9.
