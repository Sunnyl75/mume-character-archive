=== Bree Legends — MUME Dating Indicators ===
Contributors: breelegends
Requires at least: 5.8
Requires PHP: 7.4
Stable tag: 0.5.0
License: GPL-3.0-or-later

Compact comparison tables with Diku Alfa and MUME epochs as columns. Side tabs
show one category at a time within the normal full parchment page template.
Epoch cells show recorded output, with short action labels in the left column.
Superscript references lead to dated source notes below each table. Matching
wording keeps the same pale shade; another shade draws attention to a change.
Pale shades have no confidence or good/bad meaning. A bounded gap can show
shared wording as inferred continuity: same shade, dashed border, Inferred label
and a note citing both endpoints. These are not new attestations. Red underlining
marks changed text at a new form’s first observed appearance. A small red tick
marks a deletion, explained on hover. Dashes mean no evidence or bounded inference.
Confirmed feature continuation does not assert unobserved wording.

Installation:
1. Upload the ZIP through Plugins > Add New > Upload Plugin. Activate or replace.
2. Use a normal page with the full parchment template.
3. Add a Shortcode block containing [mume_date_indicators]. Preview and publish.

The plugin never creates or publishes pages automatically. Narrow tables scroll
inside the page while keeping output and Diku columns visible. Mobile tabs wrap.

Updates:
Tools > MUME Dating Indicators adds dated evidence to an existing indicator,
downloads the current catalogue, or uploads a revised catalogue JSON. Earlier
independent observations can move shared soft anchors. Circular evidence cannot
calibrate its own indicator. Only bounded evidence fitting an epoch is placed;
broad dates may be shown approximately. A dash does not establish absence.

Guardian shadows currently have a confirmed feature-continuation rule. Exact
wording and other indicators are not automatically extended to later epochs.
Legacy saved catalogues receive new comparison metadata and bundled rows while
retaining their observations. Saved research survives plugin updates; the
previous catalogue is backed up before changes. Refresh page caches as needed.

The log-facts app has no direct catalogue exporter yet. JSON upload is the
current connection. Administrator updates appear on the public page. Changes
require manage_options and nonce-checked forms. There is no public write API.
This plugin does not modify the Deck of Chars archive.

Epoch headings: https://mume.org/about/history
Diku baseline: original DikuMUD Alfa source, linked by row.
Source dates indicate surviving evidence, not exact feature introduction dates.

Changelog 0.5.0:
Bridges evidence gaps only for matching forms in the nearest observed cells.
Labels inferred continuity and cites its bounding sources, without changing data.
Marks inserted/replaced text in red with underlining at first observed appearance.
Shows deletions as a small red tick; later repeated forms are not highlighted.

Changelog 0.4.0:
Standardizes display placeholders such as <Actor>, <Target> and <Message>.
Separates Actor, Target (victim/recipient), and Room perspectives into rows.
Keeps full combat responses, also separating attack types.
Preserves original named quotations in the catalogue.

Changelog 0.3.1:
Stacks only variants evidenced within each epoch, ordered earlier above later.
Cells grow naturally; matching wording retains its shade across columns.
Dates and uncertain/overlapping ranges remain in source footnotes.

Changelog 0.3.0:
Moves recorded output into epoch cells and dates/links into source footnotes.
Groups Tell, Say, Death and first-kill variants into short-label rows.
Uses subtle wording-change colours with no confidence meaning.
Records a future Mudlet collector for current MUME IX responses; not implemented.
WordPress runtime still needs testing.
