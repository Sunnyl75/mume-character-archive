# MUME wording & date indicators

A compact public comparison page, separate from the Deck of Chars workbench.

## Put the page on Bree Legends

1. Upload `releases/bree-mume-date-indicators-0.5.1.zip` through WordPress → Plugins
   → Add New → Upload Plugin. Activate it, or replace the earlier version.
2. Use a normal page with the regular full parchment template. Add a Shortcode
   block containing `[mume_date_indicators]`.
3. Preview, then publish the page when ready. The plugin creates no pages.

Side tabs show one category at a time: social interactions, combat and death,
spells, mounts and followers, stats and equipment, world and NPCs, and calendar
and features. The table has Diku Alfa and MUME I–IX columns, with epoch dates
below the headings. Narrow screens scroll the table within the parchment;
the output and Diku columns stay visible. On phones the tabs wrap above it.

The plugin requires PHP 7.4 or newer. Its styles are scoped and inherit the
surrounding page. It loads no external libraries, fonts or analytics. The
standalone `releases/MUME_Date_Indicators.html` contains the same catalogue.
Browser behaviour and PHP 7.4 syntax have been checked; installation and runtime
behaviour still need checking on WordPress.

## Reading the tables

The left column names the action or indicator, for example **Tell**, **Nod**
or **First kill**, followed by its viewpoint. **Actor**, **Target** (including
victim/recipient) and **Room** messages have separate rows. Sent and unavailable
tell results are separate conditions; combat attack types are also separated.
Each epoch cell shows a normalized response template. Different forms recorded in
one epoch stack in that cell, with earlier evidence above later evidence. Cells
grow to fit their samples. Observed forms stay in their evidenced epochs. A
bounded gap may additionally show inferred continuity, as described below.

Date ranges that overlap remain as recorded in the footnotes. Their display
order does not establish an exact replacement date or an epoch launch change.

Superscript footnote numbers point to dates and source links below the active
table. Each template cites its retained original quotation. Names in the
source titles remain unchanged.
Missing online URLs are stated in the footnote. Complete observations remain in
the catalogue.

The first recorded wording uses light green. Each different form in that same
response uses another pale shade, and matching forms keep their shade across
later observed epochs. Names, message contents and changing stat values do not
create a wording change; punctuation and spelling do. The pale shades carry no
confidence or good/bad meaning. At the first observed occurrence of a new form,
changed words and punctuation are red and underlined. Deleted text is represented
by a small red tick with a hover description, without adding old words to the
current response. Subsequent repetitions of that form have no red highlighting.
These are textual differences, not proof that a server update caused them.

When matching normalized wording occurs in the nearest observed cells on both
sides of a gap, the intervening epochs can show that form with the same shade,
a dashed border and an **Inferred** label. A source note identifies both bounding
observations and states that there is no direct evidence in the gap. Only forms
shared by those bounding cells are inferred. An intervening observation lacking
a form blocks bridging across it. No inferred wording is extended before the first or
after the last observation. Actor, Target and Room rows remain separate.

Inferred entries are display-only: they have no attestation records, never move
shared date anchors and never count as evidence for another gap. `—` remains
where there is neither evidence nor a bounded continuity inference. Guardian
shadows can be marked as a continuing feature, following the researcher's confirmation that they persisted. That continuation does not
assert an exact game-output string in an epoch without a sample.

The initial catalogue has 37 indicators, displayed in 48 rows after separating
viewpoints and response conditions. Templates come from retained quotations.
Names use `<Actor>` and `<Target>` consistently; variable message contents,
values and body parts use `<Message>`, `<Number>` and `<BodyPart>`. A named
character in the Tan Istar field uses `<Character>`. Full combat lines preserve
the attack-effectiveness wording and injury clause. Exact named quotations
remain unchanged in the catalogue. Stat comparisons retain the relevant
field. Quoted player speech and editorial comments that resemble game output
are excluded from the comparison view. The raw retained observations are not
changed. Documented features without a game-output sample are identified in
footnotes. Diku cells use source-code templates. MUME epoch headings follow
https://mume.org/about/history; these do not establish exact feature dates.

## Update the catalogue

In **Tools → MUME Dating Indicators**, add a source observation to an existing
indicator, or upload a revised catalogue JSON. Provide a title, original URL
where known, date range, basis for the date, and exact quotation. Older/newer
punctuation variants have their own selector. Download the current catalogue
before editing it elsewhere. The previous catalogue is backed up before each
update, and saved research survives plugin updates. Clear page caches if needed.

The comparison assigns evidence to an epoch only when its date range fits
inside that epoch. Broad single-year evidence may be displayed as approximate.
Unbounded or cross-epoch dates are not forced into a column. Conflicting dates
remain provisional.
Evidence dated using the same indicator, directly or through dependencies,
cannot place that indicator. Low-confidence evidence does not move its shared
anchor and appears as approximate when it can be placed.

Shared soft anchors are still derived from independently dated observations.
For example, earlier evidence can move shadows from **by Jan 1995** to **by
Dec 1994**, and move a soft ordering hint accordingly. This is not a hard proof
that every undated shadow log must postdate the earliest surviving observation.

Legacy saved catalogues receive the comparison metadata and new bundled rows,
while retaining their existing observations. Revised catalogues already using
the comparison format retain their chosen rows.

The public page is read-only. Updates require WordPress administrator access
and nonce-checked forms. This plugin does not change character/death records.
The workbench exports an accepted response catalogue for review and upload.
Adding observations or uploading a catalogue makes that research available on
the public page; the workbench does not publish it automatically.

## Rebuild

```bash
python3 scripts/build_date_indicators.py
NODE_PATH=/path/to/node_modules node tests/test_date_indicators.cjs
```

The builder validates dates, IDs and source references, then creates the offline
HTML and versioned plugin ZIP. `--catalogue PATH` accepts a revised catalogue.
It never publishes. The export excludes raw archives, private identity data
and credentials.

## Future: collect MUME IX responses with Mudlet

A future optional collector should save actual current responses, the triggering
command/event, character perspective, capture time, MUME version/epoch and a
source identifier. Preserve both original colour/ANSI information and plain
text. A user should run a small, deliberate test checklist rather than have the
script send unsolicited commands or messages automatically. Record prompts
separately and distinguish game output from chat quoting that output.

Export observations to review before they enter the dating catalogue; place
verified captures under MUME IX. Text differences should propose variants for
review, retaining the original capture. Captured private tells need redaction
before publication. This collector is planned, not implemented in this release.

## Targeted historical parsing

The [epoch-response pilot](epoch-response-research.md) parses independently dated
logs into reviewable response forms with original line references. Its SQLite
snapshot is a research input; it does not yet promote candidates into this
public catalogue or add them to the workbench review interface.

## Workbench handoff

The Deck Workbench now scans retained gameplay logs into persistent response
findings and exports accepted independently dated observations as a comparison
catalogue and HTML review page. Original quotes, line citations, normalized
output and point of view stay separate. Load the website’s current catalogue in
the workbench first to preserve separate website edits. See
[the workbench guide](deck-workbench.md#epoch-response-review-and-export).

Version 0.5.1 accepts the exporter’s explicit normalized display templates;
original quotations are retained in the catalogue. It does not otherwise change
the comparison layout.
