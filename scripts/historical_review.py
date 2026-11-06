"""Explain confidence and group source claims into review-sized decisions.

These are transparent rules over preserved evidence, not calibrated probabilities
and not a new AI interpretation of a source.
"""
from collections import Counter, defaultdict
import hashlib
import json
import re


def level(value):
    text = str(value or '').strip().casefold()
    if text.startswith('low'):
        return 'low'
    if text.startswith('high') or text == 'certain':
        return 'high'
    if text.startswith(('medium', 'moderate')):
        return 'medium'
    return 'unknown'


def payload(evidence):
    try:
        value = json.loads(evidence.get('raw_text', '{}'))
        return value if isinstance(value, dict) else {}
    except (TypeError, ValueError):
        return {}


def assess(kind, row, evidence, *, log=None, other_owners=()):
    raw = payload(evidence)
    reported = level(raw.get('confidence') or raw.get('evidence_confidence'))
    context = raw.get('source_context') or {}
    basis = ' '.join(str(raw.get(k, '')) for k in ('evidence', 'basis', 'notes', 'statement_scope', 'interpretation'))
    basis += ' ' + str(context.get('evidence_type', ''))
    lower = basis.casefold()
    reasons, concerns = [], []
    rating = reported
    if kind == 'link':
        explicit = bool(raw.get('characters_as_written') or raw.get('researcher_confirmed')
                        or 'player of' in lower or 'explicit' in lower)
        if raw.get('researcher_confirmed'):
            reasons.append('This association was explicitly entered/confirmed by the researcher in the source form.')
        elif explicit:
            reasons.append('Explicit same-player statement/list in the source extraction.')
        else:
            reasons.append('An association was transcribed; the original ownership statement is not quoted.')
            if rating == 'high':
                rating = 'medium'
        if row.get('status') == 'disputed':
            concerns.append('This association is already disputed.')
        if other_owners:
            concerns.append('Another owner is asserted or accepted: ' + ', '.join(sorted(set(other_owners))) + '.')
        if any(word in lower for word in ('inferred', 'possibly', 'uncertain', 'candidate only')):
            concerns.append('The source describes an inference or an uncertain association.')
    else:
        quote = str(raw.get('raw_line', ''))
        if kind == 'death':
            exact = bool(quote and ('is dead! R.I.P.' in quote or 'You are dead! Sorry' in quote))
        else:
            victim = str(row.get('other_character_name', ''))
            exact = bool(quote and re.search(r'\b' + re.escape(str(row.get('count', ''))) +
                         r'\s*,\s*\d+\s*%\s*,\s*#' + re.escape(victim) + r'(?:\s|\||$)', quote, re.I))
        if exact:
            reasons.append('The exact game-output line is retained' +
                           (' with its source line number.' if type(raw.get('source_line')) is int else '.'))
            rating = reported if reported in {'high', 'medium', 'low'} else 'high'
        else:
            reasons.append('A structured summary is retained, but no exact game-output line is attached to this claim.')
            if rating == 'high' or 'directly observed' in lower or 'recovered summary' in lower:
                rating = 'medium'
        if 'recovered summary' in lower:
            concerns.append('This finding was reconstructed from a summary; check the original once for the group.')
        if 'index title' in lower or 'retrospective' in lower:
            rating = 'low'
            concerns.append('Attribution relies on a title, retrospective account or contextual interpretation.')
        if 'inferred' in str(context.get('trophy_owner', '')).casefold():
            rating = 'medium' if rating == 'high' else rating
            concerns.append('The trophy owner was inferred from perspective, not explicitly identified in the display.')
    if reported != 'unknown':
        reasons.append('Source/extractor label: ' + reported + '.')
    else:
        reasons.append('The source extraction supplied no explicit confidence label.')
    if other_owners or row.get('status') == 'disputed':
        rating = 'low'
    date_note = ''
    if log:
        try:
            dates = json.loads(log.get('date_basis', '{}'))
        except (ValueError, TypeError):
            dates = {}
        if dates.get('alternative'):
            date_note = 'Conflicting event dates are preserved: ' + str(log.get('display_date', 'date uncertain')) + '.'
        elif log.get('date_confidence') != 'exact':
            date_note = 'Event date is approximate or unresolved; it is not being presented as exact.'
    safe = rating == 'high' and not concerns
    return {'confidence': rating, 'source_confidence': reported, 'reasons': reasons,
            'concerns': concerns, 'date_note': date_note, 'safe_to_accept': safe,
            'needs_judgement': not safe, 'rule_version': 'source-review/1'}


def groups_for(links, events, evidence_rows, logs, sources, *, selected_keys=None, reviewed=None):
    reviewed = reviewed or {}
    evidence = {r['evidence_id']: r for r in evidence_rows}
    by_log = {r['log_id']: r for r in logs}
    by_source = {r['source_id']: r for r in sources}
    claims = []
    owners = defaultdict(dict)
    for r in links:
        if r.get('status') not in {'rejected'}:
            owners[r['character_id']][r['player_id']] = r.get('main_handle') or r['player_id']
    for kind, rows, id_field, table in [('link', links, 'link_id', 'player_character_links'),
                                       ('event', events, 'event_id', 'historical_events')]:
        for row in rows:
            record_key = table + ':' + row[id_field]
            if selected_keys is not None and record_key not in selected_keys:
                continue
            if kind == 'link' and not row[id_field].startswith('link_hist_'):
                continue
            claim_kind = 'link' if kind == 'link' else row['event_type']
            ev = evidence.get(row.get('primary_evidence_id') or row.get('evidence_id'), {})
            source_id = ev.get('source_id') or row.get('source_id', '')
            other = [name for pid, name in owners.get(row.get('character_id'), {}).items() if pid != row.get('player_id')] if kind == 'link' else []
            assessment = assess(claim_kind, row, ev, log=by_log.get(row.get('log_id')), other_owners=other)
            revision = reviewed.get(record_key)
            if revision:
                assessment.update(confidence=revision['confidence'],
                                  reasons=['Human review: ' + revision['basis']],
                                  concerns=(['Another owner is asserted or accepted: ' + ', '.join(other) + '.'] if other else []),
                                  safe_to_accept=revision['confidence']=='high' and not other,
                                  needs_judgement=revision['confidence']!='high' or bool(other))
                if other: assessment['confidence'] = 'low'
            claims.append({'kind': claim_kind, 'id': row[id_field], 'record_key': record_key,
                           'evidence_id': row.get('primary_evidence_id') or row.get('evidence_id', ''),
                           'character': row.get('character_name', ''), 'other_character': row.get('other_character_name', ''),
                           'count': row.get('count', ''), 'status': row.get('status') if kind == 'link' else row.get('review_status') or 'accepted',
                           'player_id': row.get('player_id', ''), 'player': row.get('main_handle', ''),
                           'source_id': source_id, 'log_id': row.get('log_id', ''), 'assessment': assessment})
    # Response observations share persistent decisions, without creating names.
    for fact in reviewed.values():
        if fact.get('kind') != 'response' or selected_keys is not None:
            continue
        rating = fact['confidence']
        assessment = {'confidence': rating, 'source_confidence': rating,
                      'reasons': [fact['basis']], 'concerns': [], 'date_note': '',
                      'safe_to_accept': rating == 'high' and fact.get('revised', False),
                      'needs_judgement': rating != 'high' or not fact.get('revised', False)}
        claims.append({'kind': 'response', 'id': fact['id'], 'record_key': fact['id'], 'evidence_id': '',
                       'character': fact.get('response', {}).get('label', 'Response'), 'other_character': '',
                       'count': '', 'status': fact['status'], 'player_id': '', 'player': '',
                       'source_id': fact['source_id'], 'log_id': fact['log_id'], 'assessment': assessment})
    grouped = defaultdict(list)
    for claim in claims:
        group_key = (claim['kind'], claim['source_id'], claim['player_id'] or claim['log_id'],
                     claim['assessment']['confidence'], claim['assessment']['safe_to_accept'])
        grouped[group_key].append(claim)
    result = []
    for key, members in grouped.items():
        kind, source_id, owner, rating, safe = key
        unique_names = sorted({m['character'] for m in members}, key=str.casefold)
        title = ((members[0]['player'] or owner) + ' — ' + str(len(unique_names)) + ' character(s)' if kind == 'link'
                 else (by_log.get(owner, {}).get('title') or owner) + ' — ' + str(len(members)) +
                 {'death': ' death observation(s)', 'trophy': ' trophy snapshot(s)', 'response': ' response form(s)'}[kind])
        result.append({'id': hashlib.sha256(json.dumps(key).encode()).hexdigest()[:20], 'kind': kind,
                       'title': title, 'confidence': rating, 'safe_to_accept': safe,
                       'needs_judgement': not safe, 'source_id': source_id,
                       'source': by_source.get(source_id, {}).get('title') or source_id,
                       'log_id': members[0]['log_id'], 'names': unique_names, 'members': members,
                       'reasons': list(dict.fromkeys(reason for m in members for reason in m['assessment']['reasons'])),
                       'concerns': list(dict.fromkeys(reason for m in members for reason in m['assessment']['concerns'])),
                       'date_notes': list(dict.fromkeys(m['assessment']['date_note'] for m in members if m['assessment']['date_note'])),
                       'pending': sum(m['status'] == 'needs_review' for m in members)})
    result.sort(key=lambda g: (g['safe_to_accept'], {'low':0, 'unknown':1, 'medium':2, 'high':3}[g['confidence']], g['title'].casefold()))
    summary = dict(Counter(g['confidence'] for g in result))
    summary.update(groups=len(result), claims=len(claims), needs_judgement=sum(g['needs_judgement'] for g in result),
                   supported=sum(g['safe_to_accept'] for g in result), pending=sum(g['pending'] for g in result))
    return {'groups': result, 'summary': summary}
