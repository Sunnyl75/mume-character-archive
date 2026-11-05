"""Source-wide facts and versioned human review, independent of the public Deck.

Raw extractions stay immutable. Reviewed facts have stable source/log identities,
citations and before/after history; existing Deck tables are projections of them.
"""
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import uuid

FACT_FIELDS = ['fact_id', 'source_id', 'log_id', 'fact_json', 'updated_at']
HISTORY_FIELDS = ['revision_id', 'fact_id', 'source_id', 'log_id', 'action',
                  'before_json', 'after_json', 'reviewed_at']
STATUSES = {'accepted', 'rejected', 'needs_review'}
CONTEXT_KINDS = {'observer', 'attacker', 'killer', 'participant', 'location', 'date', 'other', 'death', 'trophy', 'link'}


def serial(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def rows(root, name):
    path = Path(root) / 'data/working' / (name + '.csv')
    if not path.exists():
        return []
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def saved_facts(root):
    return {row['fact_id']: json.loads(row['fact_json']) for row in rows(root, 'research_facts')}


def apply_reviewed(root, tables):
    """Reimports preserve human revisions instead of restoring the old extraction."""
    for fact in saved_facts(root).values():
        key = fact.get('record_key', '')
        if ':' not in key or not fact.get('canonical'):
            continue
        name, identity = key.split(':', 1)
        id_field = {'historical_events': 'event_id', 'player_character_links': 'link_id'}.get(name)
        for row in tables.get(name, []) if id_field else []:
            if row[id_field] == identity:
                row.update(fact['canonical'])


def version(fact):
    return hashlib.sha256(serial({k: v for k, v in fact.items() if k != 'version'}).encode()).hexdigest()


def readable(value):
    if isinstance(value, dict):
        return '; '.join(k.replace('_', ' ') + ': ' + readable(v) for k, v in value.items())
    if isinstance(value, list):
        return '; '.join(readable(v) for v in value)
    return str(value) if value is not None else 'Unknown'


def source_facts(source_id, log_id, tables, groups, reviewed=None, history=()):
    """All claims for a logical log or page, including unmodelled extraction fields."""
    reviewed = reviewed or {}
    evidence = {r['evidence_id']: r for r in tables['evidence']}
    facts, represented = [], set()
    for group in groups:
        if group['source_id'] != source_id or (log_id and group['log_id'] != log_id):
            continue
        for member in group['members']:
            ev = evidence.get(member['evidence_id'], {})
            try: raw = json.loads(ev.get('raw_text') or '{}')
            except ValueError: raw = {}
            represented.add(ev.get('location_in_source', ''))
            fact = {'id': member['record_key'], 'record_key': member['record_key'],
                    'source_id': source_id, 'log_id': member['log_id'], 'kind': member['kind'],
                    'subject': member['character'], 'object': member.get('player_id') or member.get('other_character', ''),
                    'value': str(member['count'] or ''), 'confidence': member['assessment']['confidence'],
                    'status': member['status'], 'basis': raw.get('evidence') or raw.get('basis') or '; '.join(member['assessment']['reasons']),
                    'notes': '', 'label': group['title'], 'about': '',
                    'citation': {'quote': raw.get('raw_line', ''), 'start': raw.get('source_line'),
                                 'end': raw.get('source_line'), 'file': '', 'url': ''}}
            facts.append(fact)
    # Every recorded appearance is visible, even if it has no death or trophy.
    for appearance in tables.get('log_appearances', []):
        ev = evidence.get(appearance.get('evidence_id'), {})
        if ev.get('source_id') != source_id or (log_id and appearance['log_id'] != log_id):
            continue
        represented.add(ev.get('location_in_source', ''))
        facts.append({'id': 'context:' + appearance['appearance_id'], 'record_key': '',
                      'source_id': source_id, 'log_id': appearance['log_id'], 'kind': 'participant',
                      'subject': appearance['character_name'], 'object': '', 'value': appearance['character_name'],
                      'confidence': appearance.get('confidence', 'unknown'), 'status': 'unreviewed',
                      'basis': 'Named appearance in the extraction; participation may need checking.',
                      'label': 'Named appearance', 'notes': '', 'about': '', 'citation': {}})

    def context(location, value, logical, path):
        identity = 'context:' + hashlib.sha256((source_id + '\n' + location + '\n' + path).encode()).hexdigest()[:24]
        facts.append({'id': identity, 'record_key': '', 'source_id': source_id, 'log_id': logical,
                      'kind': 'other', 'subject': '', 'object': '', 'value': readable(value),
                      'confidence': 'unknown', 'status': 'unreviewed', 'basis': 'Retained extraction field: ' + path,
                      'label': path.replace('_', ' '), 'notes': '', 'about': '', 'citation': {}})

    def fields(value, logical, path='', location=''):
        if isinstance(value, dict):
            for key, item in value.items():
                child = path + '/' + key if path else key
                if key in {'record_id', 'source_file', 'source_line_range', 'source_line_range_1_based'} and not path:
                    continue
                # Represented death/trophy objects already have an editable fact.
                if not path and key == 'deaths':
                    for i, death in enumerate(item):
                        if f'{logical}/death/{i}' not in represented:
                            context(location, death, logical, f'deaths/{i}')
                elif path == 'trophy_list' and key == 'derived_kill_evidence':
                    for i, trophy in enumerate(item):
                        if f'{logical}/trophy/{i}' not in represented:
                            context(location, trophy, logical, f'{child}/{i}')
                else:
                    fields(item, logical, child, location)
        elif isinstance(value, list):
            for i, item in enumerate(value):
                fields(item, logical, path + '/' + str(i), location)
        else:
            context(location, value, logical, path)

    player_metadata = set()
    for ev in evidence.values():
        if ev.get('source_id') != source_id:
            continue
        logical = ev.get('location_in_source', '')
        if ev.get('evidence_type') == 'logical_log':
            if log_id and logical != log_id:
                continue
            try: raw = json.loads(ev.get('raw_text') or '{}')
            except ValueError: continue
            fields(raw, logical, location=ev['evidence_id'])
        elif not log_id and logical not in represented:
            # Other retained assertions on a webpage/collection, not only the group clicked.
            try: raw = json.loads(ev.get('raw_text') or '{}')
            except ValueError: raw = ev.get('raw_text', '')
            context(ev['evidence_id'], raw, '', logical or ev.get('evidence_type', 'Finding'))
        elif not log_id and ev.get('evidence_type') == 'player_character_association':
            try: raw = json.loads(ev.get('raw_text') or '{}')
            except ValueError: continue
            # One list may back many associations. Show its additional fields once.
            extra = {k:v for k,v in raw.items() if k not in
                     {'characters_as_written', 'character_name', 'pName', 'player_id', 'same_player_as',
                      'confidence', 'evidence_confidence', 'basis', 'evidence', 'researcher_confirmed'}}
            digest = serial(extra)
            if extra and digest not in player_metadata:
                player_metadata.add(digest)
                fields(extra, '', location=ev['evidence_id'])
    current = {fact['id']: fact for fact in facts}
    for identity, fact in reviewed.items():
        if fact['source_id'] == source_id and (not log_id or fact['log_id'] == log_id):
            current[identity] = fact
    histories = {}
    for row in history:
        histories.setdefault(row['fact_id'], []).append(row)
    for fact in current.values():
        fact['version'] = version(fact)
        fact['history'] = [{'action': r['action'], 'at': r['reviewed_at'],
                            'before': json.loads(r['before_json']), 'after': json.loads(r['after_json'])}
                           for r in histories.get(fact['id'], [])]
    return sorted(current.values(), key=lambda f: (f['kind'] not in {'death', 'trophy', 'link'}, f['kind'], f['label'], f['subject']))


def transaction(root, changed):
    """Stage all changed tables; restore bytes if any replacement fails."""
    working = Path(root) / 'data/working'
    originals = {name: (working / (name + '.csv')).read_bytes() if (working / (name + '.csv')).exists() else None
                 for name in changed}
    with tempfile.TemporaryDirectory(dir=working, prefix='fact-review-') as temporary:
        for name, (headers, records) in changed.items():
            with (Path(temporary) / (name + '.csv')).open('w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader(); writer.writerows(records)
        replaced = []
        try:
            for name in changed:
                dest = working / (name + '.csv')
                (Path(temporary) / dest.name).replace(dest)
                replaced.append(name)
        except BaseException:
            for name in replaced:
                dest = working / (name + '.csv')
                if originals[name] is None: dest.unlink(missing_ok=True)
                else: dest.write_bytes(originals[name])
            raise


def save(app, decisions):
    """Validate and save explicit per-fact decisions with a complete revision trail."""
    from import_historical_evidence import Importer
    from workbench_sources import character_name
    if not isinstance(decisions, list) or not 1 <= len(decisions) <= 2000:
        raise ValueError('Choose one or more facts to review.')
    importer = Importer(app.root)
    facts = saved_facts(app.root)
    history = rows(app.root, 'research_fact_history')
    now = datetime.now(timezone.utc).isoformat()
    seen = set()
    cache = {}
    for decision in decisions:
        sid, log = decision.get('source_id', ''), decision.get('log_id', '')
        scope = (sid, log)
        if scope not in cache:
            cache[scope] = {f['id']: f for f in app.source_facts('archive', sid, log)['facts']}
        action = decision.get('action')
        if action not in {'accept', 'revise', 'reject', 'pending', 'add'}:
            raise ValueError('Choose Accept as written, Revise, Reject or Keep pending.')
        identity = decision.get('id')
        if action == 'add':
            identity = 'fact_' + uuid.uuid4().hex
            before = None
            fact = {'id': identity, 'source_id': sid, 'log_id': log, 'record_key': '',
                    'kind': 'other', 'subject': '', 'object': '', 'value': '', 'label': 'Added finding',
                    'status': 'needs_review', 'confidence': 'unknown', 'basis': '', 'notes': '', 'citation': {}, 'about': ''}
        else:
            if identity not in cache[scope]:
                raise ValueError('This fact changed or belongs to another source. Reopen the source review.')
            before = json.loads(serial(cache[scope][identity]))
            before.pop('history', None); before.pop('version', None)
            if decision.get('version') and decision['version'] != cache[scope][identity]['version']:
                raise ValueError('This fact has changed since you opened it. Reopen the source review.')
            fact = json.loads(serial(before))
        if identity in seen:
            raise ValueError('A fact was selected more than once.')
        seen.add(identity)
        if action in {'revise', 'add'}:
            changes = decision.get('changes') or {}
            allowed = {'subject', 'object', 'value', 'confidence', 'basis', 'notes', 'citation', 'about'}
            if action == 'add' or not fact.get('record_key'): allowed.add('kind')
            if set(changes) - allowed:
                raise ValueError('An unsupported fact field was supplied.')
            fact.update(changes)
            if not fact.get('record_key') and fact['kind'] not in CONTEXT_KINDS:
                raise ValueError('Choose a supported finding type.')
            if action=='revise' and not fact.get('record_key') and fact['kind'] in {'death','trophy','link'}:
                raise ValueError('Use Add a missing finding for a new death, trophy or player link.')
            if fact['confidence'] not in {'high', 'medium', 'low', 'unknown'}:
                raise ValueError('Choose a confidence rating.')
            if not str(fact.get('basis') or '').strip():
                raise ValueError('Explain what the source supports in Evidence / reason.')
            if not fact.get('record_key') and fact['kind']!='link' and not str(fact.get('value') or '').strip():
                raise ValueError('Enter the finding or named character.')
            citation = fact.get('citation')
            if not isinstance(citation, dict) or set(citation) - {'file', 'quote', 'start', 'end', 'url'}:
                raise ValueError('Use a source quotation and optional line range.')
            for key in ('start', 'end'):
                if citation.get(key) not in (None, '') and (type(citation[key]) is not int or citation[key] < 1):
                    raise ValueError('Citation lines must be positive whole numbers.')
            if citation.get('start') and citation.get('end') and citation['end'] < citation['start']:
                raise ValueError('The citation line range is reversed.')
            if fact.get('about') and fact['about'] not in cache[scope]:
                raise ValueError('Attach this finding to a fact from this source.')
        status = {'accept': 'accepted', 'reject': 'rejected', 'pending': 'needs_review'}.get(action, decision.get('status', 'needs_review'))
        if status not in STATUSES:
            raise ValueError('Choose whether the revised fact is accepted or pending.')
        fact.update(status=status, revised=True, reviewed_at=now, schema='source-fact/1')
        if action=='add' and fact['kind'] in {'death', 'trophy', 'link'}:
            raw = {'evidence':fact['basis'], 'confidence':fact['confidence'], 'researcher_confirmed':True,
                   'raw_line':fact['citation'].get('quote',''), 'source_line':fact['citation'].get('start')}
            location = 'review/' + identity
            if fact['kind']=='link':
                if str(fact.get('object','')).casefold() not in importer.indexes['players']:
                    raise ValueError('Choose an existing player ID for the association.')
                importer.link(sid, location, fact['subject'], fact['object'], raw)
                row = next((r for r in importer.tables['player_character_links']
                            if r['primary_evidence_id'] in {e['evidence_id'] for e in importer.tables['evidence']
                                                          if e['location_in_source']==location}), None)
                name, id_field = 'player_character_links', 'link_id'
            else:
                if not log: raise ValueError('Select the particular log before adding a death or trophy observation.')
                if not str(fact['value']).isdigit() or int(fact['value'])<1:
                    raise ValueError('The observation count must be a positive whole number.')
                source_log = next(r for r in importer.tables['logs'] if r['log_id']==log)
                dates = {k:source_log.get(k,'') for k in ('date_range_start','date_range_end','display_date','date_confidence')}
                importer.event(sid, log, location, fact['kind'], fact['subject'],
                               fact.get('object','') if fact['kind']=='trophy' else '', int(fact['value']), raw, dates)
                row = next((r for r in importer.tables['historical_events'] if r['evidence_id'] in
                            {e['evidence_id'] for e in importer.tables['evidence'] if e['location_in_source']==location}),None)
                name, id_field = 'historical_events', 'event_id'
            if row is None: raise ValueError('Enter valid named characters for the new observation.')
            fact['id'] = fact['record_key'] = name + ':' + row[id_field]
        key = fact.get('record_key', '')
        if key:
            name, identity_value = key.split(':', 1)
            id_field = {'historical_events': 'event_id', 'player_character_links': 'link_id'}[name]
            row = next((r for r in importer.tables[name] if r[id_field] == identity_value), None)
            if row is None: raise ValueError('The imported record is no longer available.')
            char = importer.character(fact['subject'])
            if not char: raise ValueError('Enter one unambiguous character name.')
            row.update(character_name=char['name'], character_id=char['character_id'], confidence=fact['confidence'])
            if name == 'player_character_links':
                player = importer.indexes['players'].get(fact['object'].casefold())
                if not player: raise ValueError('Choose an existing player for the association.')
                row.update(player_id=player['player_id'], main_handle=player['main_handle'], status=status)
            else:
                if not str(fact['value']).isdigit() or int(fact['value']) < 1:
                    raise ValueError('The observation count must be a positive whole number.')
                row.update(count=str(fact['value']), review_status=status)
                if fact['kind'] == 'trophy':
                    other = importer.character(fact['object'])
                    if not other: raise ValueError('Enter the trophy victim character.')
                    row.update(other_character_id=other['character_id'], other_character_name=other['name'])
                    importer.queue(other, row['evidence_id'])
            importer.queue(char, row.get('evidence_id') or row.get('primary_evidence_id', ''))
            fact['canonical'] = dict(row)
        elif fact['kind'] in {'observer', 'attacker', 'killer', 'participant'} and status != 'rejected':
            name = character_name(fact['value'])
            if not name: raise ValueError('Enter one named character per role finding.')
            char = importer.character(name)
            if not char: raise ValueError('This character name is ambiguous.')
            importer.queue(char, fact['id'])
        facts[fact['id']] = fact
        history.append({'revision_id': 'review_' + uuid.uuid4().hex, 'fact_id': fact['id'], 'source_id': sid,
                        'log_id': log, 'action': action, 'before_json': serial(before), 'after_json': serial(fact), 'reviewed_at': now})
    for row in importer.tables['player_character_links']:
        if row['status'] == 'accepted' and row['link_id'].startswith('link_hist_'):
            owners = {r['player_id'] for r in importer.tables['player_character_links']
                      if r['character_id'] == row['character_id'] and r['status'] == 'accepted'}
            if len(owners) > 1: raise ValueError(row['character_name'] + ' has a conflicting accepted owner.')
    changed = {}
    for name in ('historical_events', 'player_character_links', 'characters', 'whois_queue', 'evidence'):
        if importer.tables[name] != rows(app.root, name):
            changed[name] = (importer.headers[name], importer.tables[name])
    changed['research_facts'] = (FACT_FIELDS, [{'fact_id': f['id'], 'source_id': f['source_id'], 'log_id': f['log_id'],
                                               'fact_json': serial(f), 'updated_at': f['reviewed_at']} for f in facts.values()])
    changed['research_fact_history'] = (HISTORY_FIELDS, history)
    transaction(app.root, changed)
    return len(decisions)
