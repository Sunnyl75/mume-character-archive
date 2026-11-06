"""Persistent response review and an accepted-only handoff to the epoch catalogue.

Extraction never overwrites a human decision. The catalogue is a projection;
source facts and their revision history remain the review authority.
"""
from datetime import date, datetime, timezone
import hashlib
import json
import re

import source_review
from parse_epoch_responses import BODY_OVERRIDES, COMMENT, compile_rules, match_line, epoch_for
from build_date_indicators import validate as check_catalogue, build as build_comparison

SECTIONS = ['Social interactions', 'Combat & death', 'Spells', 'Mounts & followers',
            'Stats & equipment', 'World & NPCs', 'Calendar & features']
CATEGORIES = {'Socials': SECTIONS[0], 'Communication': SECTIONS[0], 'Combat': SECTIONS[1],
              'Death and position': SECTIONS[1], 'Special combat': SECTIONS[1], 'Spells': SECTIONS[2],
              'Mounts and followers': SECTIONS[3], 'Stats and equipment': SECTIONS[4],
              'Health and resources': SECTIONS[4], 'NPC speech': SECTIONS[5],
              'Movement and doors': SECTIONS[5], 'System failures': SECTIONS[5], 'Calendar': SECTIONS[6]}
PLACEHOLDERS = {'ACTOR': 'Actor', 'TARGET': 'Target', 'MESSAGE': 'Message', 'BODY': 'BodyPart',
                'N': 'Number', 'TARGET-POSS': 'TargetPossessive', 'TARGET-OBJ': 'TargetObject',
                'ACTOR-POSS': 'ActorPossessive', 'ACTOR-OBJ': 'ActorObject'}


def normalize(template):
    return re.sub(r'<([^<>]+)>', lambda m: '<' + PLACEHOLDERS.get(m[1], m[1].title().replace('_', '')) + '>', template)


def digest(*values):
    return hashlib.sha256(source_review.serial(values).encode()).hexdigest()[:24]


def validate_catalogue(value):
    """Check the WordPress upload contract before accepting a replacement base."""
    try:
        if not isinstance(value, dict): raise ValueError()
        for key in ('epochs', 'sources', 'indicators'):
            if not isinstance(value[key], list) or len(value[key]) > 5000: raise ValueError()
            if any(not isinstance(row, dict) for row in value[key]): raise ValueError()
        for indicator in value['indicators']:
            if not all(k in indicator for k in ('title', 'category', 'mode', 'status', 'patterns', 'attestations')): raise ValueError()
            if not isinstance(indicator['patterns'], list) or not isinstance(indicator['attestations'], list): raise ValueError()
            if any(not isinstance(a.get('quote'), str) for a in indicator['attestations']): raise ValueError()
        return check_catalogue(value)
    except (KeyError, TypeError, AttributeError, ValueError):
        raise ValueError('Choose a valid MUME comparison catalogue downloaded from the comparison Tools page.') from None


def validate_response(fact):
    meta = fact.get('response')
    keys = {'category', 'label', 'viewpoint', 'detail', 'date_start', 'date_end', 'date_label',
            'date_confidence', 'date_basis', 'calibration', 'dependencies'}
    if not isinstance(meta, dict) or set(meta) - keys:
        raise ValueError('Use the response wording, point of view and dating fields.')
    if meta.get('category') not in SECTIONS or meta.get('viewpoint') not in {'Actor', 'Target', 'Room', 'Unspecified'}:
        raise ValueError('Choose a response category and point of view.')
    if not str(meta.get('label', '')).strip() or not str(fact.get('value', '')).strip():
        raise ValueError('Enter a response name and normalized output.')
    if meta.get('date_confidence') not in {'high', 'medium', 'low', 'unknown'}:
        raise ValueError('Choose confidence in the gameplay date separately from the wording.')
    if meta.get('calibration') not in {'independent', 'unresolved', 'other-indicators'}:
        raise ValueError('Choose how the gameplay date is supported.')
    for key in ('date_start', 'date_end'):
        if meta.get(key):
            try:
                if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', meta[key]): raise ValueError()
                date.fromisoformat(meta[key])
            except (TypeError, ValueError):
                raise ValueError('Use valid ISO dates in response date bounds.') from None
    if meta.get('date_start') and meta.get('date_end') and meta['date_start'] > meta['date_end']:
        raise ValueError('The response date range is reversed.')
    if not isinstance(meta.get('dependencies', []), list) or any(not isinstance(v, str) for v in meta.get('dependencies', [])):
        raise ValueError('Date dependencies must be indicator IDs.')
    if meta.get('calibration') == 'independent' and (meta.get('dependencies') or not meta.get('date_basis', '').strip()):
        raise ValueError('An independent date needs its evidence and no indicator dependencies.')
    if not fact.get('citation', {}).get('quote', '').strip():
        raise ValueError('Keep the exact source quotation separately from the normalized output.')


def scan(app, sid, log_id):
    if not log_id:
        raise ValueError('Select one gameplay log before finding response lines.')
    data = app.source_facts('archive', sid, log_id)
    original = app.original_for_source('archive', sid, log_id)
    if len(original['documents']) != 1:
        raise ValueError('Response extraction needs one unambiguous retained original for this log.')
    doc = original['documents'][0]
    path = app._source_refs[doc['ref']]['path']
    raw = path.read_bytes()
    try: text = raw.decode('utf-8-sig')
    except UnicodeDecodeError: text = raw.decode('cp1252')
    html = bool(re.search(r'<(?:html|body|pre|div)\b', text, re.I))
    if html:
        raise ValueError('Prepare this HTML log as readable text first, so response citations have stable text line numbers.')
    lines = text.splitlines()
    start, end = doc['line_start'], doc['line_end']
    if not start or not end:
        same_file = [r for r in source_review.rows(app.root, 'logs') if r.get('source_id') == sid and r.get('filename') == path.name]
        if len(same_file) > 1:
            raise ValueError('This file contains several logs. Establish this log’s line bounds before scanning it.')
        start, end = 1, len(lines)
    override = BODY_OVERRIDES.get(log_id)
    if override:
        if hashlib.sha256(raw).hexdigest() != override['file_sha256']:
            raise ValueError('The source changed; its audited gameplay bounds need checking before extraction.')
        start, end = override['range']
    if not 1 <= start <= end <= len(lines):
        raise ValueError('The retained log’s line bounds are invalid.')
    rules = compile_rules(json.loads((app.root / 'research/epoch-responses/rules.json').read_text()))
    log = data['log']
    try: event = json.loads(log.get('date_basis') or '{}')
    except ValueError: event = {}
    catalogue = json.loads((app.root / 'research/date_indicators.json').read_text())
    reference = next((s for s in catalogue['sources'] if s['id'] == log_id), {})
    start_date, end_date = log.get('date_range_start', ''), log.get('date_range_end', '')
    independent = (reference.get('calibration') == 'independent' and not reference.get('dependencies') and
                   reference.get('date_start') == start_date and reference.get('date_end') == end_date and
                   not (event.get('alternative') or event.get('alternatives')))
    confidence = str(event.get('confidence', '')).lower()
    confidence = next((v for v in ('high', 'medium', 'low') if confidence.startswith(v)), 'unknown')
    defaults = {'date_start': start_date, 'date_end': end_date, 'date_label': log.get('display_date', ''),
                'date_confidence': confidence, 'calibration': 'independent' if independent else 'unresolved',
                'date_basis': str(event.get('basis') or event.get('evidence') or reference.get('date_basis') or ''),
                'dependencies': []}
    found = {}
    file_hash = hashlib.sha256(raw).hexdigest()
    for number in range(start, end + 1):
        if COMMENT.match(lines[number-1].strip()): break
        for hit in match_line(lines[number-1], rules):
            rule = hit['rule']
            view = {'actor': 'Actor', 'actor-self': 'Actor', 'actor-targeted': 'Actor', 'leader': 'Actor',
                    'target': 'Target', 'victim': 'Target', 'recipient': 'Target',
                    'room': 'Room', 'room-self': 'Room', 'room-targeted': 'Room', 'observer': 'Room'}.get(hit['viewpoint'], 'Unspecified')
            # Targeted and untargeted variants stay distinct conditions within
            # each viewpoint; combat verbs likewise remain separate responses.
            detail = hit['viewpoint'].split('-', 1)[1] if '-' in hit['viewpoint'] and hit['viewpoint'] != 'context-dependent' else ''
            key = 'response_' + digest(sid, log_id, file_hash, rule['category'], rule['response'], view, hit['template'])
            if key in found: continue
            found[key] = {'id': key, 'source_id': sid, 'log_id': log_id, 'record_key': '',
                          'kind': 'response', 'subject': '', 'object': '', 'value': normalize(hit['template']),
                          'label': rule['response'], 'confidence': 'medium', 'status': 'needs_review',
                          'basis': 'Anchored response-pattern match. Check context, perspective and client substitutions.',
                          'notes': '', 'about': '', 'citation': {'file': path.name, 'quote': lines[number-1],
                              'start': number, 'end': number, 'url': original['url']},
                          'response': {**defaults, 'category': CATEGORIES[rule['category']],
                                       'label': rule['response'], 'viewpoint': view, 'detail': detail},
                          'schema': 'source-fact/1', 'revised': False,
                          'reviewed_at': datetime.now(timezone.utc).isoformat()}
    saved = source_review.saved_facts(app.root)
    added = [f for key, f in found.items() if key not in saved]
    for f in added: validate_response(f)
    if added:
        saved.update({f['id']: f for f in added})
        history = source_review.rows(app.root, 'research_fact_history')
        for f in added:
            history.append({'revision_id': 'extract_' + digest(f['id']), 'fact_id': f['id'], 'source_id': sid,
                            'log_id': log_id, 'action': 'extract', 'before_json': 'null',
                            'after_json': source_review.serial(f), 'reviewed_at': f['reviewed_at']})
        source_review.transaction(app.root, {
            'research_facts': (source_review.FACT_FIELDS, [{'fact_id': f['id'], 'source_id': f['source_id'],
                'log_id': f['log_id'], 'fact_json': source_review.serial(f), 'updated_at': f['reviewed_at']} for f in saved.values()]),
            'research_fact_history': (source_review.HISTORY_FIELDS, history)})
    return len(added), len(found)


def export(app, base):
    catalogue = json.loads(base.read_text())
    validate_catalogue(catalogue)
    facts = [f for f in source_review.saved_facts(app.root).values() if f['kind'] == 'response']
    logs = {r['log_id']: r for r in source_review.rows(app.root, 'logs')}
    sources = {r['source_id']: r for r in source_review.rows(app.root, 'sources')}
    indicators = {r['id']: r for r in catalogue['indicators']}
    # Refresh this archive's projection, including later rejections and revisions.
    # Other catalogue edits and evidence are retained without being overwritten.
    owner = 'deck_' + digest(str(app.root))
    for indicator in catalogue['indicators']:
        indicator['attestations'] = [a for a in indicator['attestations'] if a.get('workbench_archive') != owner]
    catalogue['sources'] = [s for s in catalogue['sources'] if s.get('workbench_archive') != owner]
    deferred, exported = [], 0
    def defer(fact, reason):
        deferred.append({'fact_id': fact['id'], 'source_id': fact['source_id'], 'log_id': fact['log_id'],
                         'title': logs.get(fact['log_id'], {}).get('title') or fact.get('label', 'Response'),
                         'output': fact['value'], 'quote': fact.get('citation', {}).get('quote', ''),
                         'response': fact.get('response', {}), 'reason': reason})
    for fact in facts:
        if fact['status'] != 'accepted': continue
        try: validate_response(fact)
        except ValueError as exc:
            defer(fact, str(exc)); continue
        meta = fact['response']
        # Unbounded, circular and cross-epoch dates remain review findings, not
        # apparently dated cells in the public comparison.
        epoch = epoch_for(meta.get('date_start'), meta.get('date_end'), catalogue['epochs'])
        if not epoch or meta['calibration'] != 'independent' or meta.get('dependencies') or meta['date_confidence'] not in {'high', 'medium'}:
            defer(fact, 'Needs independent date bounds within one epoch, with high or medium date confidence.'); continue
        log = logs.get(fact['log_id'], {})
        source = sources.get(fact['source_id'], {})
        sid = 'wbsource_' + digest(owner, fact['source_id'], fact['log_id'], {k: meta.get(k) for k in
                                 ('date_start', 'date_end', 'date_label', 'date_confidence', 'date_basis')})
        if not any(s['id'] == sid for s in catalogue['sources']):
            catalogue['sources'].append({'id': sid, 'title': log.get('title') or source.get('title') or fact['label'],
                'url': fact['citation'].get('url') or log.get('source_url') or source.get('url', ''),
                **{k: meta.get(k, '') for k in ('date_start', 'date_end', 'date_label', 'date_confidence', 'date_basis', 'calibration', 'dependencies')},
                'file_label': fact['citation'].get('file', ''), 'workbench_archive': owner})
        iid = 'wbresponse_' + digest(meta['category'], meta['label'], meta['viewpoint'], meta.get('detail', ''))
        if iid not in indicators:
            indicator = {'id': iid, 'title': meta['label'], 'category': meta['category'], 'mode': 'observed_by',
                'status': 'provisional', 'patterns': [], 'attestations': [],
                'comparison': {'section': meta['category'], 'label': meta['label'], 'row': meta['label'],
                               'viewpoint': meta['viewpoint'], 'detail': meta.get('detail', '')}}
            indicators[iid] = indicator; catalogue['indicators'].append(indicator)
        indicator = indicators[iid]
        if fact['value'] not in indicator['patterns']: indicator['patterns'].append(fact['value'])
        indicator['attestations'].append({'id': 'wb_' + digest(owner, fact['id']), 'source_id': sid,
            'quote': fact['citation']['quote'], 'display_template': fact['value'], 'viewpoint': meta['viewpoint'],
            'line_start': fact['citation'].get('start'), 'line_end': fact['citation'].get('end'),
            'file_label': fact['citation'].get('file', ''), 'confidence': fact['confidence'],
            'basis': fact['basis'], 'workbench_archive': owner, 'fact_id': fact['id']})
        exported += 1
    catalogue['indicators'] = [i for i in catalogue['indicators'] if not i['id'].startswith('wbresponse_') or i['attestations']]
    catalogue['updated_at'] = date.today().isoformat()
    validate_catalogue(catalogue)
    folder = app.directory / 'epoch-export'; folder.mkdir(exist_ok=True)
    output = folder / 'epoch-comparison-catalogue.json'
    output.write_text(json.dumps(catalogue, ensure_ascii=False, indent=2) + '\n')
    if output.stat().st_size > 4 * 1024 * 1024:
        raise ValueError('The comparison catalogue exceeds the WordPress upload limit of 4 MiB.')
    page, _ = build_comparison(output, folder)
    report = {'exported': exported, 'pending': sum(f['status'] != 'accepted' for f in facts), 'deferred': deferred,
              'base': base.name, 'created_at': datetime.now(timezone.utc).isoformat()}
    (folder / 'export-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    return report
