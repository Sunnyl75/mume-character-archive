=== Bree Legends — MUME Dating Indicators ===
Contributors: breelegends
Requires at least: 5.8
Requires PHP: 7.4
Stable tag: 0.2.0
License: GPL-3.0-or-later

Compact comparison tables with Diku Alfa and MUME epochs as columns. Side tabs
show one category at a time within the normal full parchment page template.
Dates link to original sources; dashes mean no evidence. Present* marks explicit
feature continuation. A dagger marks an original URL not yet recovered.
Exact quotations and date evidence remain in the catalogue, outside the table.

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

Changelog 0.2.0:
Replaces long chronology cards with category tabs and compact epoch tables.
Adds Diku baseline comparisons and social, death and spell output observations.
Keeps detailed evidence in the catalogue. WordPress runtime still needs testing.
