#!/usr/bin/env python3
"""A local, dependency-free guide through the Deck of Chars workflow."""
from __future__ import annotations

import argparse
import base64
import csv
from collections import Counter
import hashlib
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import mimetypes
import os
import re
from pathlib import Path, PurePosixPath
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import parse_qs, urlsplit
import uuid
import webbrowser
import zipfile

import deck_wordpress_api
from workbench_sources import extract, prepare_source
from workbench_sources import plain_text
from historical_review import groups_for
import source_review

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'workbench'
MAX_REQUEST = 36 * 1024 * 1024


def read_json(path, fallback):
    return json.loads(path.read_text()) if path.exists() else fallback


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


def table(root, name):
    path = root / 'data/working' / (name + '.csv')
    if not path.exists():
        return []
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def working_stamp(root):
    return hashlib.sha256(json.dumps([(p.name, p.stat().st_size, p.stat().st_mtime_ns)
                                     for p in sorted((root / 'data/working').glob('*.csv'))]).encode()).hexdigest()


def input_hash(path):
    paths = sorted(path.rglob('*')) if path.is_dir() else [path]
    h = hashlib.sha256()
    for item in paths:
        if item.is_file():
            h.update(str(item.relative_to(path) if path.is_dir() else item.name).encode())
            h.update(item.read_bytes())
    return h.hexdigest()


def unpack_research(data, destination):
    """Check all members before extracting; reject traversal, symlinks and bombs."""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        members = archive.infolist()
        if len(members) > 2000 or sum(m.file_size for m in members) > 96 * 1024 * 1024:
            raise ValueError('Use a research ZIP with fewer than 2,000 files and under 96 MiB uncompressed.')
        seen = set()
        for member in members:
            p = PurePosixPath(member.filename)
            mode = member.external_attr >> 16
            if (p.is_absolute() or '..' in p.parts or '\\' in member.filename or not p.parts
                    or mode & 0o170000 == 0o120000 or member.flag_bits & 1):
                raise ValueError('The ZIP contains an unsafe or encrypted file entry.')
            if member.filename in seen:
                raise ValueError('The ZIP contains duplicate filenames.')
            seen.add(member.filename)
        archive.extractall(destination)


class Workbench:
    def __init__(self, root, state_dir):
        self.root, self.directory = Path(root).resolve(), Path(state_dir).resolve()
        required = ['import_historical_evidence.py', 'publish_deck.py', 'build_whois_queue.py']
        if any(not (self.root / 'scripts' / name).exists() for name in required):
            raise ValueError('Choose the updated mume-character-archive repository containing the workbench scripts.')
        if self.directory == self.root or self.root in self.directory.parents:
            raise ValueError('Workbench session files must be outside the archive repository.')
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.data = read_json(self.directory / 'state.json', {'step': 0})
        self.job = None
        self.token = secrets.token_urlsafe(32)
        self.origin = ''
        self._counts_stamp, self._counts = '', {}
        self._report_cache, self._report_stamp = {}, None
        self._source_files, self._source_refs = {}, {}

    def remember_report(self, path):
        report = read_json(path, {})
        # Keep the polling response and persisted UI state small. Record details
        # are fetched explicitly from the local report when the user inspects them.
        self.data['research_report'] = {key: value for key, value in report.items()
                                       if key not in {'records', 'evidence_context', 'source_context', 'log_context', 'claim_review', 'source_fact_context'}}
        self.data['research_report']['claim_review'] = {'summary': report.get('claim_review', {}).get('summary', {})}
        self.data['research_report']['details_available'] = 'records' in report
        self._report_cache = report
        self._report_stamp = (path.stat().st_mtime_ns, path.stat().st_size)

    def research_report(self):
        path = self.directory / 'research-preview.json'
        if not self.data.get('research_report') or not path.exists():
            return {}
        stamp = (path.stat().st_mtime_ns, path.stat().st_size)
        if stamp != self._report_stamp:
            self._report_cache = read_json(path, {})
            self._report_stamp = stamp
        return self._report_cache

    def preview_records(self, query):
        report = self.research_report()
        records = report.get('records', [])
        selected_table = query.get('table', ['all'])[0]
        action = query.get('action', ['all'])[0]
        search = query.get('q', [''])[0][:300].casefold().strip()
        try:
            offset = max(0, int(query.get('offset', ['0'])[0]))
            limit = max(1, min(100, int(query.get('limit', ['25'])[0])))
        except ValueError:
            raise ValueError('Invalid preview page.') from None
        filtered = [r for r in records if (selected_table == 'all' or r['table'] == selected_table)
                    and (action == 'all' or r['action'] == action)
                    and (not search or search in json.dumps([r['table'], r['before'], r['after']], ensure_ascii=False).casefold())]
        return {'available': 'records' in report, 'total': len(filtered), 'all_total': len(records),
                'offset': offset, 'limit': limit, 'records': [
                    {key: r[key] for key in ('key', 'table', 'id', 'action', 'changed_fields')} |
                    {'after': {k: v for k, v in r['after'].items() if k != 'raw_text'}}
                    for r in filtered[offset:offset + limit]]}

    def preview_record(self, key):
        report = self.research_report()
        record = next((r for r in report.get('records', []) if r['key'] == key), None)
        if record is None:
            raise ValueError('This record is no longer in the preview. Run Preview proposed changes again.')
        return {'record': record,
                'evidence': [report.get('evidence_context', {})[eid] for eid in record['evidence_ids']
                             if eid in report.get('evidence_context', {})],
                'sources': [report.get('source_context', {})[sid] for sid in record['source_ids']
                            if sid in report.get('source_context', {})]}

    def claim_groups(self, scope='preview'):
        if scope == 'preview':
            result = json.loads(json.dumps(self.research_report().get('claim_review', {'groups': [], 'summary': {}})))
        elif scope == 'archive':
            result = groups_for(table(self.root, 'player_character_links'), table(self.root, 'historical_events'),
                                table(self.root, 'evidence'), table(self.root, 'logs'), table(self.root, 'sources'),
                                reviewed=source_review.saved_facts(self.root))
        else:
            raise ValueError('Unknown review scope.')
        for group in result['groups']:
            original = self.original_source(scope, group['id'], known_group=group)
            group['original_attached'] = bool(original['documents'])
            if not group['original_attached']:
                warning = 'The original source is not retained here; this group requires a source check before approval.'
                if warning not in group['concerns']:group['concerns'].append(warning)
                group.update(safe_to_accept=False, needs_judgement=True)
                if group['confidence']=='high':group['confidence']='medium'
                for member in group['members']:
                    member['assessment'].update(safe_to_accept=False, needs_judgement=True)
                    if member['assessment']['confidence']=='high':member['assessment']['confidence']='medium'
        ratings = Counter(g['confidence'] for g in result['groups'])
        result['summary'].update({rating: ratings[rating] for rating in ('high', 'medium', 'low', 'unknown')})
        result['summary'].update(needs_judgement=sum(g['needs_judgement'] for g in result['groups']),
                                 supported=sum(g['safe_to_accept'] for g in result['groups']))
        return result

    def source_facts(self, scope, source_id='', log_id='', group_id=''):
        if scope not in {'preview', 'archive'}:
            raise ValueError('Unknown review scope.')
        tables = (self.research_report().get('source_fact_context') if scope=='preview' else
                  {name: table(self.root, name) for name in ('player_character_links', 'historical_events', 'evidence', 'logs', 'sources', 'log_appearances')})
        if not tables:
            raise ValueError('Run Preview proposed changes again to load all attached facts.')
        groups = groups_for(tables['player_character_links'], tables['historical_events'], tables['evidence'],
                            tables['logs'], tables['sources'], reviewed=source_review.saved_facts(self.root))['groups']
        group = next((g for g in groups if g['id']==group_id), None) if group_id else None
        if group_id and group is None:
            raise ValueError('This group changed. Reopen the source review.')
        if group: source_id, log_id = group['source_id'], group['log_id']
        source = next((r for r in tables['sources'] if r['source_id']==source_id), None)
        log = next((r for r in tables['logs'] if r['log_id']==log_id), None)
        attached_log = any(r.get('source_id')==source_id and r.get('evidence_type')=='logical_log'
                           and r.get('location_in_source')==log_id for r in tables['evidence'])
        if not source or (log_id and (not log or not attached_log)):
            raise ValueError('Choose a source and logical log in this archive.')
        facts = source_review.source_facts(source_id, log_id, tables, groups,
                                          source_review.saved_facts(self.root), source_review.rows(self.root, 'research_fact_history'))
        return {'source_id': source_id, 'log_id': log_id, 'source': source, 'log': log, 'facts': facts,
                'players': [{k:r.get(k,'') for k in ('player_id', 'main_handle', 'known_by')} for r in table(self.root, 'players')],
                'logs': [{'id':r['log_id'], 'title':r['title']} for r in tables['logs'] if r['source_id']==source_id],
                'group_id': group['id'] if group else next((g['id'] for g in groups if g['source_id']==source_id and g['log_id']==log_id), '')}

    def original_source(self, scope, group_id, *, known_group=None):
        groups = self.claim_groups(scope)['groups'] if known_group is None else []
        group = known_group or next((g for g in groups if g['id'] == group_id), None)
        if group is None:
            raise ValueError('This review group is no longer available. Refresh the preview.')
        source_id = group['source_id']
        if scope == 'preview':
            report = self.research_report()
            source = report.get('source_context', {}).get(source_id, {})
            evidence = report.get('evidence_context', {})
            logical = report.get('log_context', {}).get(group['log_id'], {})
            for row in report.get('source_fact_context', {}).get('evidence', []):
                if row.get('source_id')==source_id and row.get('evidence_type')=='logical_log' and row.get('location_in_source')==group['log_id']:
                    try: logical = json.loads(row.get('raw_text', '{}'))
                    except ValueError: pass
            selected = self.selected('research')
            roots = [selected if selected.is_dir() else selected.parent]
        else:
            source = next((r for r in table(self.root, 'sources') if r['source_id'] == source_id), {})
            evidence = {r['evidence_id']: r for r in table(self.root, 'evidence')}
            logical = {}
            for row in evidence.values():
                if row.get('source_id') == source_id and row.get('evidence_type') == 'logical_log' and row.get('location_in_source') == group['log_id']:
                    try: logical = json.loads(row.get('raw_text', '{}'))
                    except ValueError: pass
            roots = []
            for manifest in (self.root / 'data/incoming/historical').glob('*/import-manifest.json'):
                if any(item.get('source_id') == source_id for item in read_json(manifest, {}).get('inputs', [])):
                    roots.append(manifest.parent / 'sources')
        wanted = Path(str(logical.get('source_file') or '')).name
        spans = logical.get('source_line_range_1_based') or logical.get('source_line_range') or []
        start, end = (spans[0], spans[1]) if isinstance(spans, list) and len(spans) >= 2 else (None, None)
        raw_claims = []
        for member in group['members']:
            row = evidence.get(member.get('evidence_id'), {})
            try: raw_claims.append(json.loads(row.get('raw_text', '{}')))
            except ValueError: pass
        cited = [r.get('source_line') for r in raw_claims if type(r.get('source_line')) is int and r['source_line'] > 0]
        if cited:
            start, end = min(cited), max(cited)
        if type(start) is not int or type(end) is not int:
            start, end = None, None
        url = source.get('url') or logical.get('source_url', '')
        if not url and scope == 'archive':
            url = next((r.get('source_url', '') for r in table(self.root, 'logs') if r['log_id'] == group['log_id']), '')
        files = []
        content_seen = set()
        for root in roots:
            root = root.resolve()
            if root not in self._source_files:
                self._source_files[root] = [p for p in root.rglob('*') if p.is_file() and p.resolve().is_relative_to(root)
                                            and p.suffix.casefold() in {'.txt', '.log', '.html', '.htm'}]
            candidates = self._source_files[root]
            exact = [p for p in candidates if wanted and p.name == wanted]
            if not exact and not wanted:
                # Manually prepared player sources retain original.txt too.
                exact = [p for p in candidates if p.name == 'original.txt']
            if not exact and not wanted and url:
                stamp = re.search(r'/web/(\d{10,14})', url)
                if stamp:
                    exact = [p for p in candidates if p.suffix.casefold() in {'.html', '.htm'}
                             and stamp[1] in p.read_text(encoding='utf-8', errors='replace')]
            for path in exact:
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                if digest in content_seen:
                    continue
                content_seen.add(digest)
                ref = hashlib.sha256((str(path.resolve()) + source_id + str(start) + str(end)).encode()).hexdigest()
                self._source_refs[ref] = {'path': path.resolve(), 'root': root, 'start': start, 'end': end}
                files.append({'ref': ref, 'name': path.name, 'path': str(path.relative_to(root)),
                              'line_start': start, 'line_end': end})
        return {'group': group, 'documents': files, 'url': url,
                'message': '' if files else 'The original log/page is not retained with this assertion. Only its extracted/transcribed claim is available here. Use the archived link if one is attached; do not treat the JSON as the original source.'}

    def original_for_source(self, scope, source_id, log_id):
        source = self.source_facts(scope, source_id, log_id)
        group = {'id':'source', 'source_id':source_id, 'log_id':log_id, 'members':[],
                 'title':(source['log'] or source['source'])['title']}
        return self.original_source(scope, '', known_group=group)

    def source_text(self, ref, query):
        source = self._source_refs.get(ref)
        if source is None or not source['path'].is_relative_to(source['root']):
            raise ValueError('Open the original source from a review group first.')
        if source['path'].stat().st_size > 16 * 1024 * 1024:
            raise ValueError('This retained source is too large for the inline reader.')
        data = source['path'].read_bytes()
        try: text = data.decode('utf-8-sig')
        except UnicodeDecodeError: text = data.decode('cp1252', errors='replace')
        html = bool(re.search(r'<(?:html|body|pre|div)\b', text, re.I))
        lines = (plain_text(text) if html else text).splitlines()
        try:
            start = max(1, int(query.get('start', [max(1, (source['start'] or 1)-8)])[0]))
        except ValueError:
            raise ValueError('Invalid source page.') from None
        search = query.get('q', [''])[0].casefold().strip()[:200]
        matches = [i+1 for i,line in enumerate(lines) if search and search in line.casefold()]
        if search and matches: start = max(1, matches[0]-8)
        start = min(start, max(1, len(lines)))
        end = min(len(lines), start+249)
        return {'ref': ref, 'name': source['path'].name, 'start': start, 'end': end, 'total': len(lines),
                'html_as_text': html, 'matches': len(matches), 'search': search,
                'citation': [source['start'], source['end']], 'lines': [
                    {'number': i+1, 'text': lines[i], 'highlight': bool(not html and source['start'] and source['start'] <= i+1 <= source['end'])}
                    for i in range(start-1,end)]}

    def save(self):
        with self.lock:
            atomic_json(self.directory / 'state.json', self.data)

    def profiles(self):
        folder = Path.home() / '.config/mudlet/profiles'
        return [{'path': str(p), 'profile': p.parent.name, 'modified': p.stat().st_mtime}
                for p in sorted(folder.glob('*/mume_whois_archive.json')) if p.is_file()]

    def public_state(self):
        with self.lock:
            stamp = working_stamp(self.root)
            if stamp != self._counts_stamp:
                chars, queue = table(self.root, 'characters'), table(self.root, 'whois_queue')
                self._counts = {'characters': len(chars), 'captures': len(table(self.root, 'whois_records')),
                                'pending': sum(str(r.get('already_checked', '')).casefold() not in {'true', 'yes', '1', 'checked', 'done'} for r in queue)}
                self._counts_stamp = stamp
            config = read_json(self.root / '.deck-deploy.json', {})
            state = dict(self.data)
            state.update(root=str(self.root), session_dir=str(self.directory), job=self.job,
                         profiles=self.profiles(), counts=self._counts,
                         connection={'configured': config.get('method') == 'wordpress', 'site': config.get('site_url', 'https://breelegends.com')},
                         build_current=self.data.get('build_stamp') == stamp)
            return state

    def uploaded(self, payload):
        kind = payload.get('kind')
        if kind not in {'research', 'whois'}:
            raise ValueError('Choose research or Whois input.')
        try:
            data = base64.b64decode(payload.get('data', ''), validate=True)
        except ValueError:
            raise ValueError('The selected file could not be read.') from None
        if not data or len(data) > 25 * 1024 * 1024:
            raise ValueError('Choose a non-empty file smaller than 25 MiB.')
        folder = self.directory / 'inputs' / uuid.uuid4().hex
        folder.mkdir(parents=True)
        filename = Path(str(payload.get('filename', 'input.json'))).name
        try:
            if kind == 'research' and filename.lower().endswith('.zip'):
                unpack_research(data, folder)
                target = folder
            else:
                parsed = json.loads(data.decode('utf-8-sig'))
                if not isinstance(parsed, dict):
                    raise ValueError('Choose a JSON object, or a research ZIP.')
                if kind == 'whois' and not {'records', 'captures'} <= parsed.keys():
                    raise ValueError('Choose mume_whois_archive.json from your Mudlet profile.')
                target = folder / ('mume_whois_archive.json' if kind == 'whois' else 'research.json')
                target.write_bytes(data)
        except BaseException:
            shutil.rmtree(folder)
            raise
        with self.lock:
            self.data[kind + '_path'] = str(target)
            self.data.pop(kind + '_preview', None)
            self.data.pop(kind + '_imported', None)
            if kind == 'research':
                self.data.pop('research_report', None)
                self.data.pop('research_applied', None)
            self.save()
        return {'path': str(target), 'name': filename}

    def prepare(self, payload):
        documents = prepare_source(payload)
        folder = self.directory / 'inputs' / uuid.uuid4().hex
        folder.mkdir(parents=True)
        (folder / 'original.txt').write_text(payload['text'])
        if payload.get('original_data'):
            (folder / 'original-file.bin').write_bytes(base64.b64decode(payload['original_data'], validate=True))
        atomic_json(folder / 'source-metadata.json', {k: payload.get(k, '') for k in ('title', 'url', 'date', 'start', 'end', 'observer')})
        for filename, document in documents.items():
            atomic_json(folder / filename, document)
        with self.lock:
            self.data['research_path'] = str(folder)
            self.data.pop('research_preview', None)
            self.data.pop('research_report', None)
            self.data.pop('research_applied', None)
            self.save()
        return {'path': str(folder), 'documents': list(documents)}

    def selected(self, kind):
        value = self.data.get(kind + '_path', '')
        if not value:
            raise ValueError(f'Choose a {kind} file first.')
        path = Path(value)
        if not path.exists():
            raise ValueError('The selected input no longer exists. Select it again.')
        return path

    def backup(self):
        folder = self.directory / 'backups'
        folder.mkdir(exist_ok=True)
        path = folder / (time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8] + '.zip')
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
            for source in (self.root / 'data/working').glob('*.csv'):
                archive.write(source, source.name)
        self.data['last_backup'] = str(path)
        self.save()

    def run(self, name, *args):
        script = self.root / 'scripts' / name
        process = subprocess.Popen([sys.executable, '-u', str(script), *map(str, args)],
                                   cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, encoding='utf-8', errors='replace', env={**os.environ, 'PYTHONUNBUFFERED': '1'})
        for line in process.stdout:
            with self.lock:
                self.job['log'].append(line.rstrip())
                self.job['log'] = self.job['log'][-1200:]
        if process.wait():
            raise ValueError(f'{name} stopped. Read the activity log below; your pre-operation backup is available.')

    def check_preview(self, kind):
        preview = self.data.get(kind + '_preview', {})
        if preview.get('hash') != input_hash(self.selected(kind)) or preview.get('stamp') != working_stamp(self.root):
            raise ValueError('The input or archive changed since preview. Run the preview again before importing.')

    def review_rows(self):
        links = [r for r in table(self.root, 'player_character_links') if r['link_id'].startswith('link_hist_')]
        evidence = {r['evidence_id']: r for r in table(self.root, 'evidence')}
        accepted = table(self.root, 'player_character_links')
        for row in links:
            # Show a claim summary, not all private raw player metadata.
            claim = evidence.get(row.get('primary_evidence_id'), {})
            row['source_location'] = claim.get('location_in_source', '')
            row['other_owners'] = sorted({r.get('main_handle') or r['player_id'] for r in accepted
                                        if r.get('character_id') == row['character_id'] and r.get('status') == 'accepted'
                                        and r['player_id'] != row['player_id']})
        return {'links': links, **self.claim_groups('archive'), 'players': [{k: r.get(k, '') for k in ('player_id', 'main_handle', 'known_by')}
                                          for r in table(self.root, 'players')]}

    def review(self, decisions):
        if not isinstance(decisions, list) or len(decisions) > 2000:
            raise ValueError('Choose the links to review.')
        path = self.root / 'data/working/player_character_links.csv'
        with path.open(encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            headers, links = reader.fieldnames, list(reader)
        by_id = {r['link_id']: r for r in links}
        players = {r['player_id']: r for r in table(self.root, 'players')}
        for decision in decisions:
            row = by_id.get(decision.get('link_id'))
            if not row or not row['link_id'].startswith('link_hist_'):
                raise ValueError('Only imported historical links can be reviewed here.')
            status = decision.get('status')
            player = players.get(decision.get('player_id') or row['player_id'])
            if status not in {'accepted', 'rejected', 'needs_review'} or not player:
                raise ValueError('Choose an existing player and a review decision.')
            row.update(status=status, player_id=player['player_id'], main_handle=player['main_handle'])
        for row in links:
            owners = {r['player_id'] for r in links if r['character_id'] == row['character_id'] and r['status'] == 'accepted'}
            if row['status'] == 'accepted' and len(owners) > 1 and row['link_id'].startswith('link_hist_'):
                raise ValueError(f"{row['character_name']} has a different accepted owner. Keep this link awaiting review or reject it.")
        with tempfile.TemporaryDirectory(dir=self.directory) as temp:
            draft = Path(temp) / path.name
            with draft.open('w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                writer.writerows(links)
            # Replace through a same-filesystem temporary path.
            target = path.with_suffix('.csv.workbench-tmp')
            shutil.copy2(draft, target)
            target.replace(path)

    def review_claims(self, payload, *, supported=False):
        groups = self.claim_groups('archive')['groups']
        if supported:
            chosen = [g for g in groups if g['safe_to_accept'] and g['pending']]
            status, mapping = 'accepted', ''
        else:
            ids = payload.get('groups', [])
            if not isinstance(ids, list) or not ids:
                raise ValueError('Select at least one source group.')
            chosen = [g for g in groups if g['id'] in ids]
            if len(chosen) != len(set(ids)):
                raise ValueError('A review group changed. Refresh the review list before deciding.')
            status, mapping = payload.get('status'), payload.get('player_id', '')
            if status not in {'accepted', 'rejected', 'needs_review'}:
                raise ValueError('Choose an approval, rejection or pending decision.')
        if not chosen:
            raise ValueError('There are no pending high-confidence, non-conflicting claims to accept.')
        decisions = []
        for group in chosen:
            for member in group['members']:
                if supported and member['status'] != 'needs_review':
                    continue
                decision = {'source_id':group['source_id'], 'log_id':group['log_id'], 'id':member['record_key'],
                            'action':{'accepted':'accept', 'rejected':'reject', 'needs_review':'pending'}[status]}
                if mapping and member['kind']=='link':
                    fact = next(f for f in self.source_facts('archive', group['source_id'], group['log_id'])['facts'] if f['id']==member['record_key'])
                    decision.update(action='revise', status=status, changes={'object':mapping, 'basis':fact['basis']})
                decisions.append(decision)
        count = source_review.save(self, decisions)
        self.job['log'].append(f"{status.replace('_',' ').capitalize()}: {count} claim(s) in {len(chosen)} source group(s). Other claims are unchanged.")

    def start(self, action, payload):
        allowed = {'preview_research', 'apply_research', 'save_review', 'queue', 'preview_whois', 'import_whois',
                   'build', 'validate', 'connect', 'test_connection', 'publish', 'restore', 'review_supported', 'review_claims', 'save_facts'}
        if action not in allowed:
            raise ValueError('Unknown workbench step.')
        with self.lock:
            if self.job and self.job['status'] == 'running':
                raise ValueError('An operation is already running. Wait for it to finish.')
            self.job = {'id': uuid.uuid4().hex, 'action': action, 'status': 'running', 'log': [], 'started': time.time()}
            threading.Thread(target=self.worker, args=(action, payload), daemon=False).start()
        return {'started': True}

    def worker(self, action, payload):
        try:
            report = self.directory / 'research-preview.json'
            if action == 'preview_research':
                source = self.selected('research')
                stamp, digest = working_stamp(self.root), input_hash(source)
                self.run('import_historical_evidence.py', source, '--report', report)
                self.remember_report(report)
                self.data['research_preview'] = {'hash': digest, 'stamp': stamp}
            elif action == 'apply_research':
                self.check_preview('research')
                self.backup()
                self.run('import_historical_evidence.py', self.selected('research'), '--apply', '--report', report)
                self.remember_report(report)
                self.data['research_applied'] = True
            elif action == 'save_review':
                self.backup()
                self.review(payload.get('decisions'))
                self.data['links_reviewed'] = True
            elif action in {'review_supported', 'review_claims'}:
                self.backup()
                self.review_claims(payload, supported=action == 'review_supported')
                self.data['links_reviewed'] = True
            elif action == 'save_facts':
                self.backup()
                count = source_review.save(self, payload.get('decisions'))
                self.data['links_reviewed'] = True
                self.job['log'].append(f'Saved {count} fact decision(s), with source citations and revision history.')
            elif action == 'queue':
                self.run('build_whois_queue.py')
                self.data['queue_ready'] = True
            elif action == 'preview_whois':
                source = self.selected('whois')
                stamp = working_stamp(self.root)
                snapshot = self.directory / 'whois-snapshots' / uuid.uuid4().hex / source.name
                snapshot.parent.mkdir(parents=True)
                snapshot.write_bytes(source.read_bytes())
                self.run('import_mudlet_whois_archive.py', snapshot, '--dry-run')
                self.data['whois_preview'] = {'hash': input_hash(snapshot), 'stamp': stamp, 'snapshot': str(snapshot)}
            elif action == 'import_whois':
                self.check_preview('whois')
                self.backup()
                source = Path(self.data['whois_preview']['snapshot'])
                self.run('import_mudlet_whois_archive.py', source)
                self.run('build_whois_queue.py')
                self.data['whois_imported'] = True
                self.data['whois_import_snapshot'] = str(source)
            elif action == 'build':
                self.backup()
                args = ['--whois', Path(self.data['whois_import_snapshot'])] if self.data.get('whois_imported') and self.data.get('whois_import_snapshot') else []
                self.run('publish_deck.py', *args)
                self.data['build_stamp'] = working_stamp(self.root)
                self.data['built_at'] = time.time()
                self.data['build_hash'] = input_hash(self.root / 'site/deck-of-chars/assets/data/deck-data.js')
                built = json.loads((self.root / 'site/deck-of-chars/assets/data/deck-data.js').read_text().removeprefix('window.DECK_CHARS = ').removesuffix(';\n'))
                self.data['build_count'] = len(built['characters'])
            elif action == 'validate':
                self.run('validate_data.py')
            elif action in {'connect', 'test_connection'}:
                if action == 'connect':
                    site = deck_wordpress_api.site_address(str(payload.get('site', '')).strip())
                    token = str(payload.get('key', '')).strip()
                    if deck_wordpress_api.call(site, token, 'status').get('ready') is not True:
                        raise ValueError('The website did not confirm the publishing connection.')
                    tokenfile = self.root / '.deck-publish-token'
                    deck_wordpress_api.private_write(tokenfile, token)
                    deck_wordpress_api.private_write(self.root / '.deck-deploy.json', json.dumps({
                        'method': 'wordpress', 'site_url': site, 'token_file': str(tokenfile)}) + '\n')
                else:
                    config = read_json(self.root / '.deck-deploy.json', {})
                    self.test_connection(config)
                self.job['log'].append('Publishing connection verified. No website data changed.')
            elif action == 'publish':
                if payload.get('confirm') is not True:
                    raise ValueError('Confirm publication in the Publish step.')
                if self.data.get('build_stamp') != working_stamp(self.root):
                    raise ValueError('The archive changed since the build. Rebuild and preview first.')
                if self.data.get('build_hash') != input_hash(self.root / 'site/deck-of-chars/assets/data/deck-data.js'):
                    raise ValueError('The Deck data changed. Rebuild and preview first.')
                config = read_json(self.root / '.deck-deploy.json', {})
                if config.get('method') != 'wordpress':
                    raise ValueError('Connect the WordPress publishing key first, or use the manual upload file.')
                data = json.loads((self.root / 'site/deck-of-chars/assets/data/deck-data.js').read_text().removeprefix('window.DECK_CHARS = ').removesuffix(';\n'))
                deck_wordpress_api.publish(config, data)
                self.job['log'].append(f"Published {len(data['characters'])} characters.")
                self.data['published_at'] = time.time()
            elif action == 'restore':
                if payload.get('confirm') is not True:
                    raise ValueError('Confirm restoring the backup.')
                source = self.data.get('last_backup')
                if not source or not Path(source).is_file():
                    raise ValueError('No pre-operation backup is available.')
                self.backup()  # The current state is retained too.
                with zipfile.ZipFile(source) as archive:
                    names = archive.namelist()
                    if any(Path(n).name != n or not n.endswith('.csv') for n in names):
                        raise ValueError('Invalid backup contents.')
                    working = self.root / 'data/working'
                    for target in working.glob('*.csv'):
                        if target.name not in names:
                            target.unlink()
                    for n in names:
                        (working / n).write_bytes(archive.read(n))
                self.data.pop('build_stamp', None)
                for flag in ('research_applied', 'links_reviewed', 'queue_ready', 'whois_imported', 'research_preview', 'whois_preview'):
                    self.data.pop(flag, None)
                self.job['log'].append('Working tables restored. Rebuild the queue and Deck next.')
            self.save()
            with self.lock:
                self.job['status'] = 'done'
        except Exception as exc:
            with self.lock:
                self.job['status'] = 'error'
                self.job['error'] = str(exc)
                self.job['log'].append(str(exc))
        finally:
            with self.lock:
                self.job['finished'] = time.time()
                atomic_json(self.directory / 'last-operation.json', self.job)

    def test_connection(self, config):
        if config.get('method') != 'wordpress':
            raise ValueError('Connect the website publishing key first.')
        token_path = Path(config['token_file']).expanduser()
        if token_path.stat().st_mode & 0o077:
            raise ValueError('The publishing key file is not private. Reconnect to save a private key file.')
        if deck_wordpress_api.call(config['site_url'], token_path.read_text().strip(), 'status').get('ready') is not True:
            raise ValueError('The website did not confirm the publishing connection.')


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Do not log tokens or submitted source material.

    @property
    def app(self):
        return self.server.app

    def send(self, status, data, content_type='application/json', headers=None):
        if not isinstance(data, bytes):
            data = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "frame-ancestors 'none'")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)

    def host_ok(self):
        return self.headers.get('Host') == self.app.origin.removeprefix('http://')

    def authenticated(self, cookie=False):
        token = self.headers.get('X-Workbench-Token', '')
        if cookie:
            jar = SimpleCookie()
            try:
                jar.load(self.headers.get('Cookie', ''))
                token = jar['workbench'].value if 'workbench' in jar else ''
            except Exception:
                return False
        return secrets.compare_digest(token, self.app.token)

    def do_GET(self):
        if not self.host_ok():
            return self.send(403, {'error': 'Invalid local host.'})
        parsed = urlsplit(self.path)
        route = parsed.path
        if route == '/api/state' or route == '/api/review':
            if not self.authenticated():
                return self.send(403, {'error': 'Open the workbench from its launcher.'})
            return self.send(200, self.app.public_state() if route.endswith('state') else self.app.review_rows())
        if route in {'/api/preview', '/api/preview-record'}:
            if not self.authenticated():
                return self.send(403, {'error': 'Open the workbench from its launcher.'})
            query = parse_qs(parsed.query)
            try:
                result = (self.app.preview_records(query) if route == '/api/preview'
                          else self.app.preview_record(query.get('key', [''])[0]))
                return self.send(200, result)
            except ValueError as exc:
                return self.send(400, {'error': str(exc)})
        if route in {'/api/claims', '/api/original', '/api/source-text', '/api/source-facts'}:
            if not self.authenticated():
                return self.send(403, {'error': 'Open the workbench from its launcher.'})
            query = parse_qs(parsed.query)
            try:
                scope = query.get('scope', ['preview'])[0]
                result = (self.app.source_facts(scope, query.get('source_id',[''])[0], query.get('log_id',[''])[0], query.get('group',[''])[0]) if route == '/api/source-facts' else
                          self.app.claim_groups(scope) if route == '/api/claims' else
                          (self.app.original_source(scope, query['group'][0]) if query.get('group') else
                           self.app.original_for_source(scope, query.get('source_id',[''])[0], query.get('log_id',[''])[0])) if route == '/api/original' else
                          self.app.source_text(query.get('ref', [''])[0], query))
                return self.send(200, result)
            except (ValueError, OSError) as exc:
                return self.send(400, {'error': str(exc)})
        if route == '/open-preview':
            token = parse_qs(parsed.query).get('token', [''])[0]
            if not secrets.compare_digest(token, self.app.token):
                return self.send(403, {'error': 'Invalid preview session.'})
            return self.send(303, b'', 'text/plain', {'Location': '/deck/index.html', 'Set-Cookie': f'workbench={self.app.token}; HttpOnly; SameSite=Strict; Path=/'})
        if route.startswith('/deck/'):
            if not self.authenticated(cookie=True):
                return self.send(403, {'error': 'Open Preview from the workbench.'})
            base = self.app.root / 'dist/deck-of-chars'
            target = (base / route.removeprefix('/deck/')).resolve()
            if not target.is_relative_to(base.resolve()) or not target.is_file():
                return self.send(404, {'error': 'Build the Deck before opening its preview.'})
            return self.send(200, target.read_bytes(), mimetypes.guess_type(target)[0] or 'application/octet-stream')
        if route.startswith('/download/'):
            token = parse_qs(parsed.query).get('token', [''])[0]
            if not secrets.compare_digest(token, self.app.token):
                return self.send(403, {'error': 'Invalid local session.'})
            artifact = route.removeprefix('/download/')
            if artifact == 'data':
                paths = [self.app.root / 'dist/deck-data.json']
            elif artifact == 'plugin':
                paths = sorted((self.app.root / 'dist').glob('bree-deck-of-chars-*.zip'), key=lambda p: p.stat().st_mtime, reverse=True)
            elif artifact == 'queue':
                paths = [self.app.root / 'exports/mudlet/whois_queue.txt']
            elif artifact == 'report':
                paths = [self.app.directory / 'research-preview.json']
            else:
                paths = []
            if not paths or not paths[0].is_file():
                return self.send(404, {'error': 'Create this file using the corresponding workflow step first.'})
            p = paths[0]
            return self.send(200, p.read_bytes(), 'application/octet-stream', {'Content-Disposition': f'attachment; filename="{p.name}"'})
        files = {'/': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css'}
        if route not in files:
            return self.send(404, {'error': 'Not found.'})
        p = ASSETS / files[route]
        return self.send(200, p.read_bytes(), mimetypes.guess_type(p)[0] or 'text/plain')

    def do_POST(self):
        if not self.host_ok() or not self.authenticated() or self.headers.get('Origin') != self.app.origin:
            return self.send(403, {'error': 'This request must come from your local workbench window.'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= MAX_REQUEST or self.headers.get_content_type() != 'application/json':
                raise ValueError('Choose a JSON request smaller than 36 MiB.')
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError('Invalid request.')
            route = urlsplit(self.path).path
            if route != '/api/step' and self.app.job and self.app.job['status'] == 'running':
                raise ValueError('An operation is running. Wait for it to finish before changing inputs.')
            if route == '/api/upload':
                result = self.app.uploaded(payload)
            elif route == '/api/analyse':
                if len(str(payload.get('text', ''))) > 8 * 1024 * 1024:
                    raise ValueError('Use one log at a time, under 8 MiB of text.')
                result = {'entries': extract(str(payload.get('text', '')), str(payload.get('observer', '')))}
            elif route == '/api/prepare':
                result = self.app.prepare(payload)
            elif route == '/api/select-profile':
                path = str(payload.get('path', ''))
                if path not in {p['path'] for p in self.app.profiles()}:
                    raise ValueError('Choose an available local Mudlet archive.')
                self.app.data['whois_path'] = path
                self.app.data.pop('whois_preview', None)
                self.app.data.pop('whois_imported', None)
                self.app.save()
                result = {'selected': True}
            elif route == '/api/step':
                step = payload.get('step')
                if type(step) is not int or not 0 <= step <= 6:
                    raise ValueError('Invalid step.')
                self.app.data['step'] = step
                self.app.save()
                result = {'saved': True}
            elif route == '/api/job':
                result = self.app.start(payload.get('action'), payload)
            else:
                return self.send(404, {'error': 'Unknown action.'})
            self.send(200, result)
        except (ValueError, OSError, KeyError, zipfile.BadZipFile) as exc:
            self.send(400, {'error': str(exc)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive-root', type=Path, default=ROOT)
    parser.add_argument('--state-dir', type=Path)
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    root = args.archive_root.expanduser().resolve()
    home = Path.home() / ('Library/Application Support' if sys.platform == 'darwin' else '.local/share')
    state = args.state_dir or home / 'MUME Deck Workbench' / hashlib.sha256(str(root).encode()).hexdigest()[:12]
    app = Workbench(root, state)
    # One workbench per archive, including repeated double-clicks on the launcher.
    import fcntl
    lockfile = open(root / '.deck-workbench.lock', 'a+')
    os.chmod(lockfile.name, 0o600)
    try:
        fcntl.flock(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lockfile.seek(0)
        address = lockfile.read().strip()
        if address.startswith('http://127.0.0.1:') and not args.no_browser:
            webbrowser.open(address)
        print('This archive already has a running workbench. Its existing window was reopened.')
        return
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    server.app = app
    app.origin = f'http://127.0.0.1:{server.server_port}'
    address = app.origin + '/#token=' + app.token
    lockfile.seek(0)
    lockfile.truncate()
    lockfile.write(address)
    lockfile.flush()
    print('Deck of Chars Workbench', flush=True)
    print('Local interface: ' + address, flush=True)
    print('Leave this window open while using the workbench. Press Control-C to close it.', flush=True)
    if not args.no_browser:
        webbrowser.open(address)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nWorkbench closed. A running archive job will finish before this process exits.')
    finally:
        server.server_close()
        lockfile.close()


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError) as exc:
        raise SystemExit('Workbench could not start: ' + str(exc))
