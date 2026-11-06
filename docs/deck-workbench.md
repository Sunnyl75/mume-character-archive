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
4. It downloads this project's code from `feature/workbench-review-export`, backs up
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
participant names explicitly. Click **Add this source to review**.

This is a conservative source helper, not an AI crawler or a parser for every
historical log dialect. It does not infer ownership from shared activity,
attribute killers, date ambiguous prose, split multiple log perspectives or
reconstruct maps. Split a collection into individual logs before preparation.
Unrecognised text is retained in the source. Previously prepared structured
research JSON can be used for richer reviewed extractions.

Click **Add research to review**, or **Add this source to review** for the
text form. The app checks the input, backs up the tables and preserves the source
in the local research archive. New relationships, deaths and trophies remain
pending. This is evidence storage, not acceptance or publication. Existing
review decisions survive reloading the same input. The app opens Step 2 directly;
there is no separate preview/import stage.

### 2. Review findings

Use **Needs judgement**, **High confidence**, or **All source groups**, and search
by character or source. These groups are actionable here: accept, revise, reject
or keep pending. Confidence ratings explain their evidence and limitations;
they are not probabilities or a fresh AI interpretation of a log.

**Read original source** opens the retained text with search and line numbers.
**View source & all claims** lists all retained extraction fields, appearances
and reviewed findings, alongside the original. A standalone JSON cannot supply
missing originals; use the full historical research ZIP when available.

The **Open any source and all its findings** selector also includes sources
without a death, trophy or ownership claim. Select a particular log to read its
original, add findings or scan responses. Filter the attached findings by type
or pending status; filters survive review decisions. **Read cited passage** jumps
to and highlights a finding’s source lines. Supporting storage rows and the import report are available
under the optional details panel; they do not require separate approval.

**Accept all pending high-confidence claims** accepts only supported groups with
retained originals and no flagged conflicts. Medium, low and unrated groups stay
pending. Read one source and decide its related claims together, rather than
reviewing every backing row. Select groups to accept, reject or keep pending;
expand the individual claims when a group needs closer inspection.

Use the optional existing-player dropdown to map selected player associations
to a known player. A conflicting accepted owner blocks acceptance. Reject an
incorrect imported assertion or leave an ambiguous identity pending. Older
non-historical relationships and legacy event review decisions are preserved.
Rebuild later to include accepted links, deaths and trophy snapshots in the Deck.

Each group also has a decision menu beside it. Choose **Accept group as written**,
**Review / revise individual claims**, **Reject group**, or **Keep group pending**.
The source review lists a decision menu beside every individual fact:

- **Accept as written** keeps its existing content and confidence.
- **Revise…** opens a form for the subject, count or player/victim, confidence,
  evidence/reason, exact quotation, source line range and private review notes.
  Choose **Save & accept revision** or **Save pending**.
- **Reject** and **Keep pending** retain the evidence outside public event views.

**Add a missing finding** records an observer, participant, attacker, final
killer, location, date or another finding. You can also add a missed death, trophy
snapshot or association with an existing player. Select a particular log before
adding a death or trophy, and supply its count; new observations get their own
evidence record without rewriting the original extraction. Give each role its own evidence and
confidence. Attach an attacker/location to the relevant death observation;
recording an attacker never automatically assigns a final killer or adds a
trophy kill. Add one named character per role. Named role findings feed the
existing collection queue. Accepted observer/attacker/killer/location details
attached to an accepted death appear in its public log details after rebuild;
other contextual findings remain available in the research archive.

For Eazy's example, revise the death's reason to identify his log perspective,
quote `You are dead! Sorry...`, cite line 8335, and select the confidence you can
support. Add Archie and Iqpi as separate attacker findings attached to that death,
with their own citations and confidence; leave the final killer unassigned if
the source does not establish it. These are instructions, not pre-applied edits.

Revisions and decisions retain before/after history in the source view. They do
not replace raw source evidence, and reimporting identical input preserves them.
The history records this local review session's action/time; it does not claim
an authenticated multi-user reviewer identity.

### 3. Whois (optional)

Click **Build Whois queue**, then **Copy Mudlet commands**. Paste the commands
into Mudlet, one line at a time. The `mha` collector must already be installed
and enabled in that profile. This app does not connect to the game.

After the batch finishes, return to this same step. Select a discovered Mudlet
profile or its JSON archive. Click **Preview new captures**, then **Import
captures**. The importer uses the snapshot previewed, including colour data.
Preview again if Mudlet saves more captures. Historical player links remain
attached to the same archive character IDs.

You can skip this step when publishing historical findings alone.

### 4. Build & export

**Rebuild Deck of Chars** validates and builds the local website data. Review
the searchable list of added, updated and removed characters, with changed
fields and before/after player, level, race, class and history counts. Only
changed characters are listed; the full Deck preview is no longer part of the
workflow. The baseline is the last publication from this workbench, or the Deck
present before its first updated build. Manual website uploads cannot be tracked
and are identified as such. A later archive change requires a fresh build.

Plugin and data downloads are under **Installation and manual data downloads**.
Upload the rebuilt Deck plugin through WordPress → Plugins for interface updates.

#### Epoch response review and export

In Step 2, select a particular gameplay log and click **Find epoch response
lines**. An anchored watch-list creates pending response findings with normalized
output, exact raw quotation, original line number and a separate point of view.
Repeated wording within one log supplies one finding. Repeating a scan preserves
accepted, rejected and revised findings. A changed source copy requires fresh
review; ambiguous/shared files without known log bounds cannot be scanned.
HTML logs must first be prepared as readable text with stable line numbers.

Choose **Revise…** on a response finding to review its category, response name,
point of view, condition, normalized output and dates. Use `<Actor>`, `<Target>`
and similar placeholders; retain original names in the supporting quotation.
Date confidence and evidence are separate from confidence in the wording.
Do not use the wording itself to independently date its own occurrence.
Use **Apply these dates to the other unrejected response findings in this log**
to establish a log’s date once; this does not accept its other pending findings.
You can also choose **response** in **Add a missing finding**.

In Step 4, **Export epoch comparison** creates:

- An HTML comparison page to download and review in a browser.
- `epoch-comparison-catalogue.json`, compatible with the comparison plugin.
- A dating follow-up report, with original quotes and source/log identities.
- An updated comparison plugin supporting these normalized display templates.

Only accepted response findings with independent, high/medium-confidence date
bounds wholly within one epoch enter the table. Unclear, circular or cross-epoch
dates stay in the archive and appear in the follow-up list, with a button back
to their source review. They are not silently assigned an epoch. Pending/rejected
findings, private review notes and supporting archive tables are not exported.

If you have edited the comparison catalogue on the website, first download it
from WordPress → Tools → MUME Dating Indicators, then choose **Use this catalogue**
in the workbench. Existing catalogue evidence is retained; this archive's prior
export is refreshed so corrections and later rejections do not leave stale
observations. Otherwise the bundled comparison is used. The exporter does not
modify the selected base file or publish to WordPress.

Review the downloaded HTML, install the updated comparison plugin if needed,
then upload the JSON through WordPress → Tools → MUME Dating Indicators →
**Replace the catalogue**. The epoch page and Deck have separate publication
steps. Exports become stale when archive decisions or the base catalogue change;
create a fresh export before downloading.

### 5. Publish

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
python3 -m unittest discover -s tests -p 'test_epoch_workbench.py' -v
node --check workbench/app.js
```

The optional DOM integration test uses jsdom as a development-only dependency:

```bash
npm install --prefix /tmp/deck-ui-check jsdom
NODE_PATH=/tmp/deck-ui-check/node_modules node tests/test_workbench_browser.cjs
```

It uses an isolated archive copy and exercises source preparation, historical
import into actionable review, death revisions and attached roles, response
extraction/dating/export, relationship acceptance, combined Whois collection and
import, named build changes and the publication gate. It never uploads to WordPress. macOS launcher
behaviour still needs a test on a Mac; backend and DOM checks run on Linux.
