#!/usr/bin/env python3
"""Build a reviewable response-evidence snapshot from independently dated logs.

No archive writes, inference of dates from wording, network calls, or publication.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = 'epoch-response-parser/1'
ANSI = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')
COMMENT = re.compile(r'^\d{4}/\d{2}/\d{2} \d\d:\d\d,')
SPEECH = re.compile(r"\b(?:says|narrates|tells you|yells|shouts|whispers|screams) '")
# Audited gameplay bounds apply only to these exact retained source bytes.
BODY_OVERRIDES = {'log_reliquary_sil_c_1994_12_1995_01': {'range': [6, 855], 'file_sha256': '618eec57da47ca7781d443331d3fa62f0816660929c56ed5bb8fa24804869ea2'}, 'log_mekin_warrens_1996_11_17': {'range': [6, 1582], 'file_sha256': 'c94e6f86f1f24dbdba1bdf6f32aafc59256d06f0a4908168ce518dd91c47d0e0'}, 'log_diamonium_inside_warrens_1997_11_02': {'range': [9, 792], 'file_sha256': '2269b210653a7b1dad9139259e57491717ca4f4580eaf99055a584f6058817da'}, 'log_nightstalker_1997_11_02': {'range': [10, 376], 'file_sha256': 'af58f28db967766fc09441b3fdf8ec06fe1a347484991a3cb847b2f9bce08824'}, 'log_rivendell_defended_cadfael_1996_08_09': {'range': [5693, 6694], 'file_sha256': '546db70c487767069fe7c6c62c8dde8db90c8955d20054cc21d9891cbd49dc99'}}


def serial(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def identity(prefix, *values):
    return prefix + '_' + digest(serial(values))[:24]


def epoch_for(start, end, epochs):
    if not start or not end:
        return None
    date.fromisoformat(start); date.fromisoformat(end)
    if start > end:
        return None
    return next((e['id'] for e in epochs if start >= e['start'] and (not e.get('end') or end < e['end'])), None)


def date_selection(record, source, epochs):
    event = record.get('event_date', {})
    start, end = event.get('earliest'), event.get('latest')
    confidence = event.get('confidence', '')
    if event.get('alternative') or event.get('alternatives'):
        return None, 'Competing event dates.'
    if not str(confidence).lower().startswith('high'):
        return None, 'Date confidence below the strict pilot threshold.'
    if not source or source.get('calibration') != 'independent' or source.get('dependencies'):
        return None, 'No independent date calibration recorded.'
    epoch = epoch_for(start, end, epochs)
    if not epoch:
        return None, 'Unbounded date or range spanning epochs.'
    return epoch, 'Independent high-confidence event-date range wholly inside one epoch.'


def clean_line(raw):
    """Keep raw text separately. Strip only a recognizable prompt/annotation."""
    text = ANSI.sub('', raw).strip()
    prompt, annotation = '', ''
    if '>' in text:
        candidate, rest = text.split('>', 1)
        if (('HP:' in candidate or 'Mana:' in candidate) and len(candidate) < 120 or
                re.fullmatch(r'[0-9*oRWC \t]*', candidate)):
            prompt, text = candidate + '>', rest.strip()
    m = re.search(r'\s+<[-=]{2,}.*$', text)
    if m:
        annotation, text = text[m.start():], text[:m.start()].rstrip()
    return text, prompt, annotation


def compile_rules(definition):
    if definition.get('schema') != 'mume-response-rules/1':
        raise ValueError('Unsupported response-rule schema')
    seen, result = set(), []
    for rule in definition['rules']:
        if rule['id'] in seen:
            raise ValueError('Duplicate response rule: ' + rule['id'])
        seen.add(rule['id'])
        result.append((rule, re.compile(rule['pattern'])))
    return result


def match_line(raw, compiled):
    text, prompt, annotation = clean_line(raw)
    if not text or text.startswith(('#', '//', 'http:', 'https:')):
        return []
    speech = bool(SPEECH.search(text))
    matches = []
    for rule, pattern in compiled:
        # Speech may quote a social, a death or even another tell. Never scan
        # the quoted message as system output. Retain speech as its own form.
        if speech and rule['category'] not in {'Communication', 'Spells', 'NPC speech'}:
            continue
        m = pattern.fullmatch(text)
        if not m:
            continue
        values = {k: v or '' for k, v in m.groupdict().items()}
        actor, target = values.get('actor', ''), values.get('target', '')
        values.update(text=text,
                      actor_form='You' if actor == 'You' else '<ACTOR>',
                      named_actor='not defined' if actor=='not defined' else '<ACTOR>',
                      target_form='your' if target == 'your' else '<TARGET-POSS>',
                      actor_normalized=text.replace(actor, '<ACTOR>', 1) if actor else text,
                      numbers_normalized=re.sub(r'-?\d+(?:\.\d+)?', '<N>', text))
        template = rule['template'].format_map(values)
        viewpoint = rule['viewpoint']
        if viewpoint == 'context-dependent' and rule['id'] in {'melee', 'defence'}:
            viewpoint = 'actor' if actor == 'You' else 'victim' if target == 'your' else 'room'
        matches.append({'rule': rule, 'template': template, 'viewpoint': viewpoint,
                        'text': text, 'prompt': prompt, 'annotation': annotation,
                        'variables': m.groupdict()})
    # A very broad action-failure pattern must not duplicate a specific failure.
    if len(matches) > 1:
        matches = [m for m in matches if m['rule']['id'] not in {'failure-self', 'failure-fixed'}] or matches[:1]
    return matches


def extract(bundle, catalogue, definition):
    corpus_path = bundle / 'corpus/mume_historical_logs_corpus_v1.0_consolidated.json'
    corpus = json.loads(corpus_path.read_text())
    source_map = {s['id']: s for s in catalogue['sources']}
    file_counts = Counter(r['source_file'] for r in corpus['records'])
    compiled = compile_rules(definition)
    selected, deferred, forms, observations, segments_seen = [], [], {}, {}, set()
    for record in corpus['records']:
        rid = record['record_id']; source = source_map.get(rid)
        epoch, reason = date_selection(record, source, catalogue['epochs'])
        if not epoch:
            deferred.append({'source_id': rid, 'title': record['title'], 'reason': reason})
            continue
        matches = list((bundle / 'sources/raw_logs').rglob(record['source_file']))
        if len(matches) != 1:
            raise ValueError('Missing or ambiguous source file: ' + record['source_file'])
        raw_bytes = matches[0].read_bytes(); lines = raw_bytes.decode('utf-8').splitlines()
        bounds = record.get('source_line_range_1_based') or record.get('source_line_range')
        if not bounds and file_counts[record['source_file']] != 1:
            raise ValueError('Shared source file has no logical-log boundaries: ' + rid)
        override = BODY_OVERRIDES.get(rid)
        if override and override['file_sha256'] != hashlib.sha256(raw_bytes).hexdigest():
            raise ValueError('Changed source copy requires a new gameplay-boundary audit: ' + rid)
        start, end = override['range'] if override else (bounds or (1, len(lines)))
        if not (1 <= start <= end <= len(lines)):
            raise ValueError('Invalid source boundaries: ' + rid)
        # A posting/comment timestamp belongs to the webpage, not the event.
        for offset, line in enumerate(lines[start-1:end], start):
            if COMMENT.match(line.strip()):
                end = offset-1; break
        segment_hash = digest('\n'.join(lines[start-1:end]))
        if segment_hash in segments_seen:
            deferred.append({'source_id': rid, 'title': record['title'], 'reason': 'Duplicate source segment.'})
            continue
        segments_seen.add(segment_hash)
        event = record['event_date']
        selection = {'source_id': rid, 'title': record['title'], 'url': source.get('url', ''),
                     'epoch': epoch, 'date_start': event['earliest'], 'date_end': event['latest'],
                     'date_label': event.get('display', ''), 'date_confidence': event['confidence'],
                     'date_basis': event.get('basis') or event.get('evidence') or source.get('date_basis') or event['confidence'],
                     'observer': record.get('credited_observer', ''), 'file': record['source_file'],
                     'file_sha256': hashlib.sha256(raw_bytes).hexdigest(), 'segment_sha256': segment_hash,
                     'line_start': start, 'line_end': end, 'selection_basis': reason}
        selected.append(selection)
        for number in range(start, end+1):
            raw = lines[number-1]
            for hit in match_line(raw, compiled):
                rule = hit['rule']; template = hit['template']; viewpoint = hit['viewpoint']
                fid = identity('form', rule['category'], rule['response'], viewpoint, template)
                forms.setdefault(fid, {'form_id': fid, 'category': rule['category'], 'response': rule['response'],
                                       'viewpoint': viewpoint, 'template': template, 'status': 'needs_review'})
                oid = identity('observation', rid, fid)
                context = '\n'.join(lines[max(start-1, number-3):min(end, number+2)])
                if oid not in observations:
                    observations[oid] = {'observation_id': oid, 'form_id': fid, 'source_id': rid,
                                         'first_line': number, 'last_line': number, 'occurrences': 0,
                                         'raw_line': raw, 'last_raw_line': raw, 'matched_text': hit['text'],
                                         'prompt': hit['prompt'], 'annotation': hit['annotation'],
                                         'context': context, 'variables': hit['variables'], 'rules': [],
                                         'status': 'needs_review', 'extraction_basis': 'Anchored response-pattern match; context and client rendering still require review.'}
                obs = observations[oid]
                # Same template can match two overlapping rules on one line.
                if obs['last_line'] != number or obs['occurrences'] == 0:
                    obs['occurrences'] += 1
                obs['last_line'], obs['last_raw_line'] = number, raw
                if rule['id'] not in obs['rules']:
                    obs['rules'].append(rule['id'])
    return {'schema': 'mume-epoch-response-evidence/1', 'parser': VERSION,
            'corpus_sha256': hashlib.sha256(corpus_path.read_bytes()).hexdigest(),
            'selected_sources': selected, 'deferred_sources': deferred,
            'forms': sorted(forms.values(), key=lambda f: (f['category'], f['response'], f['template'], f['viewpoint'])),
            'observations': sorted(observations.values(), key=lambda o: (o['source_id'], o['first_line'], o['form_id']))}


def database(snapshot, definition, destination):
    with sqlite3.connect(destination) as db:
        db.executescript('''
            PRAGMA foreign_keys=ON;
            CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE sources(source_id TEXT PRIMARY KEY,title TEXT,url TEXT,epoch TEXT,date_start TEXT,date_end TEXT,
              date_label TEXT,date_confidence TEXT,date_basis TEXT,observer TEXT,file TEXT,file_sha256 TEXT,
              segment_sha256 TEXT,line_start INTEGER,line_end INTEGER,selection_basis TEXT);
            CREATE TABLE forms(form_id TEXT PRIMARY KEY,category TEXT,response TEXT,viewpoint TEXT,template TEXT,status TEXT);
            CREATE TABLE observations(observation_id TEXT PRIMARY KEY,form_id TEXT REFERENCES forms(form_id),
              source_id TEXT REFERENCES sources(source_id),first_line INTEGER,last_line INTEGER,occurrences INTEGER,
              raw_line TEXT,last_raw_line TEXT,matched_text TEXT,prompt TEXT,annotation TEXT,context TEXT,
              variables TEXT,rules TEXT,status TEXT,extraction_basis TEXT);
            CREATE TABLE rules(rule_id TEXT PRIMARY KEY,definition TEXT);
            CREATE TABLE deferred_sources(source_id TEXT PRIMARY KEY,title TEXT,reason TEXT);
            CREATE INDEX observations_form ON observations(form_id);
            CREATE VIEW epoch_forms AS SELECT s.epoch,f.category,f.response,f.viewpoint,f.template,
              COUNT(DISTINCT s.source_id) AS source_logs,SUM(o.occurrences) AS matched_lines,MIN(s.date_start) AS earliest_bound,
              MAX(s.date_end) AS latest_bound,f.status
              FROM observations o JOIN sources s USING(source_id) JOIN forms f USING(form_id)
              GROUP BY s.epoch,f.form_id;
        ''')
        for table, rows in [('sources', snapshot['selected_sources']), ('forms', snapshot['forms']),
                            ('observations', snapshot['observations']), ('deferred_sources', snapshot['deferred_sources'])]:
            for row in rows:
                cols = list(row); values = [serial(row[k]) if isinstance(row[k], (list, dict)) else row[k] for k in cols]
                db.execute(f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})", values)
        for rule in definition['rules']:
            db.execute('INSERT INTO rules VALUES (?,?)', (rule['id'], serial(rule)))
        for k in ('schema', 'parser', 'corpus_sha256'):
            db.execute('INSERT INTO metadata VALUES (?,?)', (k, snapshot[k]))
        db.execute('INSERT INTO metadata VALUES (?,?)', ('rules_sha256', digest(serial(definition))))
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'


def report(snapshot):
    forms = {f['form_id']: f for f in snapshot['forms']}; sources = {s['source_id']: s for s in snapshot['selected_sources']}
    by_epoch = Counter(s['epoch'] for s in sources.values()); counts = defaultdict(lambda: defaultdict(set))
    for o in snapshot['observations']:
        counts[forms[o['form_id']]['category']][sources[o['source_id']]['epoch']].add(o['form_id'])
    lines = ['# Targeted epoch-response pilot', '',
             f"Selected **{len(sources)} independently dated logs**: " + ', '.join(f'MUME {e.upper()}: {n}' for e,n in sorted(by_epoch.items())) + '.',
             f"Extracted **{len(forms)} response forms**, supported by **{len(snapshot['observations'])} form/log observations** and **{sum(o['occurrences'] for o in snapshot['observations'])} matching lines**.",
             '', 'All extracted observations await review. Repeated lines in one log count as one form/log observation; frequency does not raise confidence.', '',
             '| Category | MUME V forms | MUME VI forms |', '|---|---:|---:|']
    for category, epochs in sorted(counts.items()):
        lines.append(f"| {category} | {len(epochs['v'])} | {len(epochs['vi'])} |")
    lines += ['', 'Other epochs have no selected logs in this pilot. A zero is no matched evidence, not proof of absence.', '',
              '## Source selection', '', '| Log | Epoch | Event date | Date basis |', '|---|---|---|---|']
    def cell(value):
        return str(value).replace('|', '\\|').replace('\n', ' ')
    for s in sources.values():
        title = f"[{s['title']}]({s['url']})" if s['url'] else s['title'] + ' (URL not recorded)'
        lines.append('| ' + ' | '.join(map(cell, [title, s['epoch'].upper(), s['date_label'], s['date_basis']])) + ' |')
    lines += ['', '## Examples to inspect', '', '| Category | Epoch | Recorded output | Source and line |', '|---|---|---|---|']
    seen = set()
    for obs in snapshot['observations']:
        form, source = forms[obs['form_id']], sources[obs['source_id']]
        key = (form['category'], source['epoch'])
        if key in seen: continue
        seen.add(key)
        lines.append('| ' + ' | '.join(map(cell, [form['category'],source['epoch'].upper(),obs['matched_text'],f"{source['title']} · {source['file']}:{obs['first_line']}"])) + ' |')
    lines += ['', '## Deferred logs', '']
    for s in snapshot['deferred_sources']:
        lines.append(f"- {s['title']}: {s['reason']}")
    lines += ['', '## Limits and next pass', '',
              '- These are response-form candidates, not accepted character facts or exact introduction/removal dates.',
              '- The date basis is independent of the response being tested. Webpage posting dates and circular wording/calendar estimates are excluded.',
              '- Game-output classification, client substitutions, observer perspective and inline editorial changes still need review.',
              '- Matching stock Diku wording establishes a textual match; it does not prove code ancestry or uninterrupted survival.',
              '- The watch-list cannot discover every response. Missing, unmatched and context-dependent messages remain future work.',
              '- Next sources needed: independently dated MUME I–IV and VII–IX logs, including the planned current Mudlet response captures.',
              '- No changes were made to the live page, published catalogue, character tables, whois queue or workbench.', '']
    return '\n'.join(lines)


def form_review(snapshot):
    sources = {s['source_id']: s for s in snapshot['selected_sources']}
    grouped = defaultdict(list)
    for obs in snapshot['observations']:
        grouped[obs['form_id']].append(obs)
    lines = ['# Response-form review', '',
             'All forms below are candidates awaiting review. Examples are exact matched excerpts; their raw lines, prompts, nearby context and additional sources are retained in the SQLite snapshot.', '',
             'Epoch coverage lists observed support only. A template combines variable names, message contents or numeric values; spelling and punctuation remain significant.', '']
    category = None
    def cell(value):
        return str(value).replace('|', '\\|').replace('\n', ' ')
    def code(value):
        return '`' + cell(value).replace('`', '&#96;') + '`'
    for form in snapshot['forms']:
        if category != form['category']:
            category = form['category']
            lines += ['', '## '+category, '', '| Response / perspective | Form | Epochs | Recorded example | Date and source |', '|---|---|---|---|---|']
        hits = sorted(grouped[form['form_id']], key=lambda o: (sources[o['source_id']]['date_end'], o['source_id'], o['first_line']))
        sample = hits[0]; source = sources[sample['source_id']]
        epochs = ', '.join(sorted({sources[o['source_id']]['epoch'].upper() for o in hits}))
        title = cell(source['title'])
        if source['url']: title = '['+title+']('+source['url']+')'
        citation = cell(source['date_label'])+' · '+title+' · '+cell(source['file'])+':'+str(sample['first_line'])
        lines.append('| '+cell(form['response']+' / '+form['viewpoint'])+' | '+code(form['template'])+' | '+epochs+' | '+code(sample['matched_text'])+' | '+citation+' |')
    return '\n'.join(lines)+'\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle', type=Path)
    parser.add_argument('--catalogue', type=Path, default=ROOT/'research/date_indicators.json')
    parser.add_argument('--rules', type=Path, default=ROOT/'research/epoch-responses/rules.json')
    parser.add_argument('--output', type=Path, default=ROOT/'releases/MUME_Epoch_Response_Pilot.zip')
    parser.add_argument('--report', type=Path, default=ROOT/'reports/epoch-response-pilot.md')
    args = parser.parse_args()
    definition = json.loads(args.rules.read_text())
    snapshot = extract(args.bundle, json.loads(args.catalogue.read_text()), definition)
    text = report(snapshot)
    review_text = form_review(snapshot)
    review_path = args.report.with_name(args.report.stem+'-forms.md')
    args.output.parent.mkdir(parents=True, exist_ok=True); args.report.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp)/'epoch-responses.sqlite3'; database(snapshot, definition, db)
        with zipfile.ZipFile(args.output, 'w', zipfile.ZIP_DEFLATED) as z:
            z.write(db, db.name)
            z.writestr('README.md', text)
            z.writestr('response-form-review.md', review_text)
            z.writestr('source-selection.json', json.dumps({k:v for k,v in snapshot.items() if k not in {'forms','observations'}}, ensure_ascii=False, indent=2)+'\n')
            z.writestr('response-rules.json', json.dumps(definition, ensure_ascii=False, indent=2)+'\n')
    args.report.write_text(text)
    review_path.write_text(review_text)
    print(f"{len(snapshot['selected_sources'])} logs; {len(snapshot['forms'])} forms; {len(snapshot['observations'])} form/log observations")
    print(args.output); print(args.report); print(review_path)


if __name__ == '__main__':
    main()
