# Targeted response evidence from known epochs

The first pilot selects independently dated historical logs, extracts response
forms and preserves their original source lines. It supplies a research dataset
for the wording/epoch page. It does not change the public catalogue, archive
character records, whois queue or workbench.

The current sample covers **MUME V and VI only**. Other epochs need suitable
source logs. The current counts and source list are in
[the pilot report](../reports/epoch-response-pilot.md); every extracted form has
a dated example in [the form review](../reports/epoch-response-pilot-forms.md).

## Use the snapshot

Unzip `releases/MUME_Epoch_Response_Pilot.zip`. It contains:

- `epoch-responses.sqlite3`: sources, response forms, supporting observations,
  extraction rules and deferred source decisions.
- `response-form-review.md`: all candidate forms, perspectives, epoch coverage,
  an actual example, date, source link where known and original line number.
- `source-selection.json`: the selection policy results, date bases, source
  bounds and content hashes.
- `response-rules.json`: the versioned extraction watch-list, including pinned
  Diku source-code references for social-response templates.
- `README.md`: results, source selection and limitations.

The database is a generated research snapshot, not the canonical archive or a
new application database. All forms and observations have `needs_review` status.
Do not use an edited snapshot as the only home for review decisions: rebuilding
regenerates it. The workbench does not yet review or promote this new record type.
A future importer should keep accepted/rejected decisions in the existing fact
review framework and preserve them across extraction reruns.

## Selection and parsing rules

A log qualifies when the retained event date has high confidence, both bounds
fall wholly inside one epoch, and the dating catalogue records independent
calibration with no indicator dependencies. Exact dates are not required if the
whole supported interval lies inside one epoch. Webpage posting dates do not
supply gameplay dates. Conflicting, calculated, medium-confidence and unbounded
dates remain deferred in this strict pilot.

Shared files use explicit logical-log boundaries. The five manually audited
body ranges are tied to exact file hashes, so a changed source copy requires a
new boundary audit. Webpage comments are excluded from the parsed body.

An anchored watch-list finds socials, communication, combat, health/resources,
spells, failures, movement, mounts and selected other responses. It does not
pretend to be an exhaustive game parser. Diku templates are a matching baseline;
matching them proves neither code ancestry nor presence in an unobserved epoch.

The parser retains original lines separately from matched excerpts. Recognized
prompts and inline editorial annotations are stored separately. Names, stat
values and ordinary message contents can be represented as variables in forms;
spelling, punctuation, attack adverbs, incantations and injury effects survive.
The observer/perspective is retained where supported. Context and client
substitution still need review. No player identities or character attributes
are inferred from these response matches.

Repeated occurrences of a form in one log are grouped into one observation,
with a count, first and last source lines, exact examples and nearby context.
Repeated lines do not increase confidence. Duplicate source segments are not
counted twice. Stable form and observation IDs allow later review integration.

## Reproduce the pilot

From the repository, with the extracted historical bundle:

```bash
python3 scripts/parse_epoch_responses.py \
  "$HOME/Downloads/mume_historical_research_master_v1.0"
python3 -m unittest discover -s tests -p 'test_epoch_responses.py' -v
```

`--rules`, `--catalogue`, `--output` and `--report` accept alternative paths.
The catalogue is read only for epoch definitions and independent-date metadata;
it is not changed. The parser makes no network requests or publishing calls.
Source paths in reports remain relative filenames, not machine-specific paths.

The SQLite `epoch_forms` view groups forms by observed epoch. For example:

```sql
SELECT epoch, category, response, viewpoint, template, source_logs
FROM epoch_forms
WHERE category = 'Socials'
ORDER BY response, epoch;

SELECT s.title, s.date_label, s.date_basis, s.file, o.first_line,
       o.raw_line, o.context
FROM observations o
JOIN sources s USING (source_id)
JOIN forms f USING (form_id)
WHERE f.response = 'Nod';
```

## Next steps

1. Review representative forms and their source context; separate genuine
   wording changes from perspective, language, aliases and client rendering.
2. Integrate approved response observations with the existing fact-review
   framework, then export accepted forms to the epoch-page catalogue.
3. Seek independently dated source logs for MUME I–IV and VII–IX. Prefer a few
   well-dated examples per epoch with different perspectives and command types.
4. Add the planned deliberate Mudlet response collector for current MUME IX,
   retaining both original colour and plain text, command/event, time and version.

A dated observation supplies an attestation, not an exact introduction or removal
date. Absence from a short log does not establish absence from an epoch.
