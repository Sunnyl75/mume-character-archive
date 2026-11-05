"""Conservative, reviewable extraction helpers for the local workbench."""
from html.parser import HTMLParser
import hashlib
import re


class PageText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.hidden = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style'}:
            self.hidden += 1
        if not self.hidden and tag in {'br', 'p', 'div', 'tr', 'li', 'pre', 'h1', 'h2', 'h3'}:
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in {'script', 'style'}:
            self.hidden = max(0, self.hidden - 1)
        elif not self.hidden and tag in {'p', 'div', 'tr', 'li', 'pre'}:
            self.parts.append('\n')

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def plain_text(text):
    if re.search(r'<(?:html|body|pre|div|br|p)\b', text, re.I):
        parser = PageText()
        parser.feed(text)
        text = ''.join(parser.parts)
    return re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', text).replace('\r\n', '\n')


def character_name(value):
    value = str(value or '').strip()
    if value.casefold() in {'a', 'an', 'the', 'unknown', 'someone', 'somebody', 'you'}:
        return ''
    return value if re.fullmatch(r'[^\W\d_][\w\'-]*', value, re.UNICODE) else ''


def extract(text, observer=''):
    """Return candidates, never assertions of ownership or kill attribution."""
    result = []
    in_trophy, gap, block = False, 0, 0
    for number, line in enumerate(plain_text(text).splitlines(), 1):
        if '*** TROPHY ***' in line:
            in_trophy, gap, block = True, 0, block + 1
            continue
        if in_trophy:
            entries = []
            for cell in line.split('|'):
                match = re.fullmatch(r'\s*(\d+)\s*,\s*(\d+)\s*%\s*,\s*#([^|]+?)\s*', cell)
                if match and character_name(match[3]) and int(match[1]) > 0:
                    entries.append({'kind': 'trophy', 'character': match[3].strip(), 'count': int(match[1]),
                                    'owner': character_name(observer), 'line': number, 'block': block, 'raw': line})
            result.extend(entries)
            # Mobile-only rows and explicit pagination remain within the display.
            if entries or re.match(r'\s*\d+\s*,\s*\d+\s*%', line) or '*** Return:' in line:
                gap = 0
            else:
                gap += 1
                if gap > 3:
                    in_trophy = False
        # Accept exact death wording; free prose and anonymous races are left alone.
        match = re.match(r'^\s*\*?([^*]+?)\*? is dead! R\.I\.P\.', line)
        candidate = ''
        if match:
            label = match[1].strip()
            starred = line.lstrip().startswith('*')
            if starred and ' the ' in label:
                label = label.split(' the ', 1)[0]
            candidate = character_name(label)
        elif re.match(r'^\s*You are dead! Sorry', line):
            candidate = character_name(observer)
        if candidate:
            result.append({'kind': 'death', 'character': candidate, 'count': 1,
                           'line': number, 'raw': line, 'owner': ''})
    return result


def prepare_source(payload):
    text = str(payload.get('text', ''))
    title = str(payload.get('title', '')).strip()
    url = str(payload.get('url', '')).strip()
    if not title or not text.strip():
        raise ValueError('Enter a source title and paste or load the original text.')
    observer = character_name(payload.get('observer'))
    record_id = 'log_manual_' + hashlib.sha256((url + '\n' + text).encode()).hexdigest()[:20]
    dates = {'display': str(payload.get('date', '')).strip(),
             'earliest': str(payload.get('start', '')).strip(), 'latest': str(payload.get('end', '')).strip(),
             'basis': 'Date entered during source review; posting date is not assumed to be event date.'}
    supplied = extract(text, observer)
    selected = payload.get('selected', [])
    if not isinstance(selected, list) or any(type(i) is not int or not 0 <= i < len(supplied) for i in selected):
        raise ValueError('The selection no longer matches the extracted source. Detect entries again.')
    picked = [supplied[i] for i in sorted(set(selected))]
    deaths, trophies = [], []
    for entry in picked:
        if entry['kind'] == 'death':
            deaths.append({'character': entry['character'], 'count': 1, 'evidence': 'directly observed',
                           'confidence': 'high', 'source_line': entry['line'], 'raw_line': entry['raw']})
        else:
            if not observer:
                raise ValueError('Enter the character displaying the trophy before including trophy entries.')
            trophies.append({'killer_character': observer, 'victim_character': entry['character'],
                             'minimum_kill_count': entry['count'], 'confidence': 'high',
                             'source_line': entry['line'], 'snapshot_block': entry['block'], 'raw_line': entry['raw']})
    named = []
    for value in re.split(r'[,;\s]+', str(payload.get('characters', ''))):
        if value:
            valid = character_name(value)
            if not valid:
                raise ValueError(f'Use one searchable character name at a time: {value}')
            named.append(valid)
    records = []
    if picked or named or observer:
        records.append({'record_id': record_id, 'title': title, 'source_file': 'original.txt',
                        'source_url': url, 'credited_observer': observer, 'principal_characters': named,
                        'event_date': dates, 'deaths': deaths,
                        'trophy_list': {'present': bool(trophies), 'derived_kill_evidence': trophies}})
    documents = {}
    if records:
        documents['log.json'] = {'schema_version': 'mume_historical_logs_corpus/1.0', 'records': records}
    players = []
    for line in str(payload.get('groups', '')).splitlines():
        if not line.strip():
            continue
        if ':' not in line:
            raise ValueError('Write each player group as pName: CharacterOne, CharacterTwo')
        handle, chars = line.split(':', 1)
        handle = handle.strip()
        names = [character_name(x) for x in re.split(r'[,;\s]+', chars.strip()) if x]
        if not character_name(handle) or not names or not all(names):
            raise ValueError('Use a public player handle and a list of searchable character names.')
        players.append({'pName': handle, 'characters_as_written': names, 'confidence': 'high', 'researcher_confirmed': True,
                        'basis': 'Explicit association entered by the researcher; raw source retained.'})
    if players:
        documents['players.json'] = {'schema_version': 'mume_player_character_evidence/0.1',
                                     'source_capture_url': url, 'players': players}
    if not documents:
        raise ValueError('Add a player group, confirmed character names, observer, or selected log observations.')
    return documents
