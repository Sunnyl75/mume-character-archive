"""Data-only publishing to the Bree Deck plugin over verified HTTPS."""
import getpass
import json
import os
from pathlib import Path
import re
from urllib import request, error
from urllib.parse import urlsplit


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward the publishing key to a redirect destination.
        return None


def site_address(value):
    parsed = urlsplit(value)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path not in ('', '/') or parsed.port not in (None, 443)):
        raise ValueError('Use the canonical HTTPS site address, for example https://breelegends.com')
    return value.rstrip('/')


def call(site, token, route, data=None):
    if not re.fullmatch(r'[A-Za-z0-9]{48}', token):
        raise ValueError('The publishing key must be the 48-character key from Tools → Deck of Chars.')
    site = site_address(site)
    headers = {'X-Bree-Deck-Token': token, 'Accept': 'application/json'}
    body = None
    if data is not None:
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        if len(body) > 12 * 1024 * 1024:
            raise ValueError('The Deck data is larger than the plugin limit of 12 MiB.')
        headers['Content-Type'] = 'application/json'
    req = request.Request(site + '/wp-json/bree-deck/v1/' + route, data=body, headers=headers)
    try:
        with request.build_opener(NoRedirect()).open(req, timeout=90) as response:
            return json.load(response)
    except error.HTTPError as exc:
        raise ValueError(f'WordPress returned HTTP {exc.code}. Check the site address, plugin activation and publishing key. Manual JSON upload is available in Tools → Deck of Chars.') from None
    except error.URLError:
        raise ValueError('Could not connect to WordPress. Check the connection and site address.') from None


def private_write(path, text):
    temporary = path.with_name(path.name + '.tmp')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write(text)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def setup(config_path):
    site = site_address(input('Site address [https://breelegends.com]: ').strip() or 'https://breelegends.com')
    token = getpass.getpass('Deck publishing key (hidden): ').strip()
    result = call(site, token, 'status')
    if result.get('ready') is not True:
        raise ValueError('WordPress did not confirm that the Deck plugin is ready.')
    token_path = config_path.parent / '.deck-publish-token'
    private_write(token_path, token)
    private_write(config_path, json.dumps({'method': 'wordpress', 'site_url': site, 'token_file': str(token_path)}, indent=2) + '\n')
    print('Connection verified and saved. Rebuild and publish with: python3 scripts/publish_deck.py --publish')


def publish(config, data, dry_run=False):
    token_file = Path(config['token_file']).expanduser()
    if token_file.stat().st_mode & 0o077:
        raise ValueError('The token file must be private: chmod 600 ' + str(token_file))
    token = token_file.read_text().strip()
    if dry_run:
        if call(config['site_url'], token, 'status').get('ready') is not True:
            raise ValueError('WordPress did not confirm that the Deck plugin is ready.')
        print(f'Connection verified. Would publish {len(data["characters"])} characters; no remote data changed.')
        return
    result = call(config['site_url'], token, 'data', data)
    if result.get('characterCount') != len(data['characters']):
        raise ValueError('WordPress did not confirm the expected character count. Check Tools → Deck of Chars before retrying.')
    print(f'Published {result["characterCount"]} characters to WordPress.')
