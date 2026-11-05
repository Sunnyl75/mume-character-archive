=== Bree Legends — MUME Dating Indicators ===
Contributors: breelegends
Requires at least: 5.8
Requires PHP: 7.4
Stable tag: 0.1.0
License: GPL-3.0-or-later

An evidence-backed chronology of dating clues, grouped by MUME epoch. Each entry
distinguishes documented version markers, provisional sorting anchors and
unresolved boundaries. Exact quotations and their date basis remain attached.

Installation:
1. Upload the ZIP through WordPress Plugins > Add New > Upload Plugin. Activate.
2. Create a normal Page titled MUME Dating Indicators.
3. Add a Shortcode block containing [mume_date_indicators]. Preview and publish.

The plugin never creates or publishes a page automatically.

Updates:
Tools > MUME Dating Indicators can add dated evidence to an existing indicator,
download the current catalogue or upload a revised catalogue JSON. An earlier
independent observation can move a shared anchor and its epoch placement.
Evidence whose date relies on the same indicator does not calibrate that anchor.
The previous catalogue is backed up in a separate option before each update.
Saved data survives plugin updates. If a page cache is enabled, refresh that
page's cache after updating the catalogue.

Seed data comes from the July consolidated log research. Broad version headings
are sourced from https://mume.org/about/history. Source dates and provisional
interpretations are not represented as exact feature introduction/removal dates.
The public page is read-only. Data changes require WordPress administrator access
and a nonce-checked form. This plugin does not modify the Deck of Chars archive.
