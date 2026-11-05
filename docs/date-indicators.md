# MUME Dating Indicators

A separate, publishable research chronology. This does not implement the pending
Workbench redesign or alter character/death records.

## Put the page on Bree Legends

1. Upload `releases/bree-mume-date-indicators-0.1.0.zip` through WordPress → Plugins
   → Add New → Upload Plugin. Activate it.
2. Create a normal Page named **MUME Dating Indicators**. Add a Shortcode block:
   `[mume_date_indicators]`.
3. Preview and publish that page when ready. The plugin does not create or publish
   any page automatically. Use the site's wide parchment template if desired.

The plugin requires PHP 7.4 or newer. It is independent of Deck of Chars. Its CSS
is scoped to its own page content, and it loads no fonts, analytics or libraries
from third-party services. The standalone `releases/MUME_Date_Indicators.html`
contains the same current catalogue and can be opened directly in a browser.

## Update the running chronology

In **Tools → MUME Dating Indicators**, add a source observation to an existing
indicator. Give the source title, URL where available, date range, date evidence
and exact quotation. Mark whether the date is independent of this indicator.
Low-confidence and dependent dates stay visible but do not move its anchor.
Older/newer punctuation variants have their own selector.

The page recalculates epoch placement and sorting anchors from its stored data.
For example, an introduction currently placed **by Jan 1995** has a **soft after
Jan 1995** sorting hint. Adding stronger, independent evidence before Dec 1994
can move the label and hint earlier. This is a soft ordering preference, not a
proof that an undated log must fall after its first surviving attestation.

Upload a revised catalogue JSON to add or revise indicators, source dates,
dependencies or epoch definitions. Download the current catalogue before an
external edit. The previous catalogue is backed up before every update; saved
data survives plugin updates. Page caches may need refreshing after updates.
The WordPress public page is read-only; administration requires `manage_options`
and nonce-checked forms. No public write API is exposed.

## Evidence and epoch rules

`research/date_indicators.json` is the initial public catalogue. The seed has 21
indicators and exact excerpts matched against the retained July corpus. Sources
whose dates conflict, rely on unresolved calendar conversion or lack a usable
date bound remain visible but cannot calibrate a marker automatically. An
indicator's first dated appearance is distinct from an exact introduction date.

The official version headings follow https://mume.org/about/history. Their
months are reference points for grouping. A feature listed under a version is
not necessarily proven to have arrived on its opening day. Unresolved markers,
including Clip-clop removal and a calendar-reset hypothesis, have their own
section instead of invented dates.

The initial public export contains marker evidence, source titles/date bases
and short quotations. It excludes private player-identity files, raw archives,
publishing credentials and internal archive tables. Adding research through the
WordPress administration form publishes that research on this page.

## Rebuild the deliverables

```bash
python3 scripts/build_date_indicators.py
```

Use `--catalogue PATH` for a downloaded revised catalogue. The build validates
dates, IDs and source references, then produces the offline HTML and plugin ZIP.
It never publishes. Checks:

```bash
NODE_PATH=/tmp/deck-ui-check/node_modules node tests/test_date_indicators.cjs
```
