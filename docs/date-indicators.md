# MUME wording & date indicators

A compact public comparison page, separate from the Deck of Chars workbench.

## Put the page on Bree Legends

1. Upload `releases/bree-mume-date-indicators-0.2.0.zip` through WordPress → Plugins
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

- `—` means no evidence assigned to that epoch; it does not prove absence.
- Boundary cells use short markers such as `(present by Jan 1995)` or
  `(present around Jun 1998)`. Interior observed epochs say `Present`.
- Dates link to the original online source, including retained Wayback copies.
  `†` identifies dates whose original URL has not yet been recovered.
- `Present*` means a feature continues by an explicit continuity rule. Only
  guardian shadows currently have this rule, following the researcher's
  confirmation that they persisted. This extends feature presence, not exact
  spelling or output. Earlier epochs remain unknown.

The initial catalogue has 37 indicators, displayed as 38 comparison rows.
Exact quotes, source dates, dependencies and line references stay in the data;
the public page omits evidence panels and lengthy explanations. Diku wording
was checked against the original Alfa source. MUME epoch headings follow
https://mume.org/about/history. Those headings do not establish exact feature
introduction dates.

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
There is no direct exporter from the log-facts app yet; the current connection
is uploading catalogue JSON. Adding observations or uploading a catalogue makes
that research available on the public page.

## Rebuild

```bash
python3 scripts/build_date_indicators.py
NODE_PATH=/path/to/node_modules node tests/test_date_indicators.cjs
```

The builder validates dates, IDs and source references, then creates the offline
HTML and versioned plugin ZIP. `--catalogue PATH` accepts a revised catalogue.
It never publishes. The export excludes raw archives, private identity data
and credentials.
