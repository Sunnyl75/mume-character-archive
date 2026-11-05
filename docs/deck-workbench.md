# Deck of Chars Workbench

A guided local interface for the archive's existing scripts. It runs on your
computer in your normal browser. Routine collection/import/rebuild/publication
does not require Terminal commands or a ChatGPT session. Python 3.10 or newer
is required; no Python packages, Node installation or AI account are required.

## One-time setup on Lewis's Mac

1. Download and unzip `Deck_Workbench_Setup.zip`.
2. Open `Install_Deck_Workbench.command`. If macOS asks which app opens it,
   choose Terminal. macOS may require approving a downloaded launcher through
   Finder's Open action or Privacy & Security; follow the system's own prompt.
3. The installer finds `~/mume-character-archive`, or asks you to select the
   existing archive folder. Read its installation message and click Install.
4. It downloads this project's code from `feature/deck-workbench`, backs up
   existing code, and opens the interface. It preserves your working database,
   captures, artwork and publishing configuration. Missing bundled reference
   and clan-source files are added only if absent. It does not switch branches,
   stage files or create commits. Installed code changes will show in Git status.
5. Next time, open **Deck of Chars Workbench.command** on your Desktop, or
   **Open Deck Workbench.command** in the archive folder.

Git access must work for the existing repository; the installer uses the Mac's
normal Git credentials. It never asks you to paste a GitHub token into chat.
Installation code backups are under
`~/Library/Application Support/MUME Deck Workbench/installation-backups/`.
Check the printed error if the download cannot complete; it does not reset or
clean your repository. Quit an existing workbench before updating its code.

If using Git directly, switch to the workbench branch with your usual process
after preserving local changes, then open its launcher. There is no need to run
the installer when the updated code is already present.

## Every session

Leave the launcher window open during operations. The browser interface is at
a private localhost address. It remembers your step and selected inputs when
you return. Reopening the launcher opens the already running workbench instead
of starting another archive writer. Close the launcher with Control-C after
its current operation finishes.

### 1. Add sources

**Research JSON / ZIP** accepts the July master research bundle, standalone
player-link candidates, website player lists and curated log indexes. You can
select the ZIP directly; no manual extraction is necessary.

**Webpage / gameplay log** is a form for preparing new sources without writing
JSON. Enter the source title and original/Wayback URL. Paste the text, or load a
text/HTML file. Enter a date label and optional date bounds, keeping event dates
separate from webpage posting dates. For a log, enter its observer character.

Record explicit player groups as:

```text
pDorien: Dorien, Utgbald, Rogrog
pHordak: Hordak, Ward, Gubbe
```

Click **Detect death & trophy lines**, inspect the exact source excerpts, and
select the player entries to include. The detector understands standard named
`is dead! R.I.P.` lines, the observer's `You are dead!` message, and named player
entries inside a confirmed `*** TROPHY ***` display. It excludes anonymous races
and multiword mobile descriptions. One-word names still need your review.
Nothing detected is included until selected. You can also enter other confirmed
participant names explicitly. Click **Prepare this source for import**.

This is a conservative source helper, not an AI crawler or a parser for every
historical log dialect. It does not infer ownership from shared activity,
attribute killers, date ambiguous prose, split multiple log perspectives or
reconstruct maps. Split a collection into individual logs before preparation.
Unrecognised text is retained in the source. Previously prepared structured
research JSON can be used for richer reviewed extractions.

### 2. Preview & import

Click **Preview proposed changes**. Check the additions and other review items;
each total opens the corresponding record list. Under **Inspect individual
records**, choose a record type, filter additions/updates, or search a character,
player, log title or value. Use **More records** to page through larger imports.

Click **Inspect** beside a record to see its proposed fields and supporting
source text. Updates show the current and proposed values side by side. Source
file names, URLs, extraction locations and confidence remain attached. Full
record identifiers are available in an expandable section. The detailed report
can also be downloaded. These inspection actions do not import anything.

After updating an older workbench, click **Preview proposed changes** again to
regenerate the detailed report. Your selected input is remembered.

Click **Import into my local archive** when ready.
An input or archive change invalidates its preview and requires a fresh preview.
Imports preserve sources and leave new player relationships pending.

### 3. Review player links

Search names, select rows, and accept, reject or keep them pending. Use the
existing-player dropdown to map selected source associations to a known player.
A conflicting accepted owner blocks acceptance. Reject an incorrect imported
assertion or leave an ambiguous identity pending. The app does not modify older
non-historical relationship rows. Rebuild later to see accepted links in decks.

### 4. Collect Whois

Click **Build Whois queue**, then **Copy Mudlet commands**. Paste the commands
into Mudlet, one line at a time. The `mha` collector must already be installed
and enabled in that profile. The workbench does not control or connect to the
game itself. Return after the batch finishes. This stage is optional.

### 5. Import captures

Select an automatically discovered local Mudlet profile, or choose its JSON
archive. Click **Preview new captures**, inspect the activity output, then
**Import captures**. The importer works from the exact snapshot previewed, so
the local rebuild uses the same captured text and colour data. If Mudlet saves
more captures after preview, preview again before importing them.

### 6. Build & preview

Click **Rebuild Deck of Chars**. Progress streams into Activity while the
interface remains responsive. The existing validation/classification/evidence/
export scripts run in order. Open **local Deck preview** to inspect the actual
generated website. Download the plugin or data file from this step.

For first use of the new Logs and Trophies interface, upload the rebuilt plugin
through WordPress → Plugins → Add New → Upload Plugin. Subsequent data-only
updates use the final step. New interface code or portrait assets also require
a plugin update.

### 7. Publish

Create a publishing key in WordPress → Tools → Deck of Chars, then enter the
site address and key in the workbench. **Verify & save connection** checks the
key without publishing character data. Keys remain in the existing private
local token file and are not included in browser state or activity reports.

**Publish Deck data** requires a completed build matching the current archive
and a deliberate confirmation. It uses the established WordPress publishing
API; source imports and rebuilds never publish automatically. If the connection
is blocked, download the data JSON and upload it manually through the WordPress
Tools page. The workbench cannot confirm a manual upload automatically.

## Backups, local files and limitations

Working CSV tables are backed up before imports, relationship decisions and
rebuilds. **Restore last backup** restores those tables and backs up the current
state first. Afterwards, rebuild the queue and Deck. It does not roll back a
published website or remove retained source evidence. Code installation has a
separate backup as described above.

Session files and table backups live outside the repository, under
`~/Library/Application Support/MUME Deck Workbench/<archive-id>/` on macOS
(`~/.local/share/MUME Deck Workbench/` on Linux). Imported source checkpoints are
also retained by the historical importer inside the archive. Do not run other
archive writers at the same time. The app serializes its own background jobs.

The local service listens on 127.0.0.1 only, with per-launch tokens and an origin
check for writes. No public hosting or cloud account is required. The browser
contains all interface assets locally; source text is not sent to an AI service.
The app does not automatically commit or push archive data to GitHub.

## Developer checks

```bash
python3 -m unittest discover -s tests -p 'test_*import.py' -v
python3 -m unittest discover -s tests -p 'test_deck_workbench.py' -v
node --check workbench/app.js
```

The optional DOM integration test uses jsdom as a development-only dependency:

```bash
npm install --prefix /tmp/deck-ui-check jsdom
NODE_PATH=/tmp/deck-ui-check/node_modules node tests/test_workbench_browser.cjs
```

It uses an isolated archive copy and exercises source preparation, historical
import, relationship acceptance, queue building, Whois preview/import, full
rebuild and the publication gate. It never uploads to WordPress. macOS launcher
behaviour still needs a test on a Mac; backend and DOM checks run on Linux.
