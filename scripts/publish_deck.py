#!/usr/bin/env python3
"""Rebuild the Deck and publish through its WordPress plugin or SSH/rsync."""
import argparse
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import subprocess
import sys
import tempfile
import deck_wordpress_api
from build_deck_wordpress_plugin import build_plugin

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / 'site/deck-of-chars'


def run_script(name, *args):
    subprocess.run([sys.executable, str(ROOT / name), *map(str, args)], cwd=ROOT, check=True)


def deployment_config(path):
    config = json.loads(path.read_text())
    if config.get('method') == 'wordpress':
        config['site_url'] = deck_wordpress_api.site_address(config['site_url'])
        if not Path(config['token_file']).expanduser().is_file():
            raise ValueError('Publishing key file is missing. Run --setup-wordpress first.')
        return config
    target = config['ssh_target']
    remote = config['remote_directory']
    if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]*@[A-Za-z0-9][A-Za-z0-9.-]*', target):
        raise ValueError('ssh_target must be user@host (use ~/.ssh/config for keys/ports).')
    if (not re.fullmatch(r'/[A-Za-z0-9_./-]+', remote)
            or '..' in remote.split('/') or not remote.rstrip('/').endswith('/deck-of-chars')):
        raise ValueError('remote_directory must be an absolute path ending in /deck-of-chars, without spaces or ..')
    return target, remote.rstrip('/')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--publish', action='store_true', help='Upload after a successful build.')
    parser.add_argument('--dry-run', action='store_true', help='Build and show rsync changes without uploading.')
    parser.add_argument('--whois', type=Path, help='Import this Mudlet JSON before rebuilding.')
    parser.add_argument('--historical', type=Path, help='Import structured historical research before rebuilding; player links remain reviewable.')
    parser.add_argument('--export-only', action='store_true', help='Use the already rebuilt archive manifest.')
    parser.add_argument('--config', type=Path, default=ROOT / '.deck-deploy.json')
    parser.add_argument('--setup-wordpress', action='store_true', help='Connect to the plugin once; prompts for the publishing key.')
    args = parser.parse_args()
    if args.setup_wordpress:
        deck_wordpress_api.setup(args.config.expanduser().resolve())
        return
    if (args.whois or args.historical) and args.export_only:
        parser.error('Imports and --export-only cannot be combined')
    # Fail before changing data if deployment is requested but not configured.
    deploy = deployment_config(args.config.expanduser()) if args.publish or args.dry_run else None
    if isinstance(deploy, tuple) and not shutil.which('rsync'):
        parser.error('rsync is required to publish')
    if args.historical:
        run_script('scripts/import_historical_evidence.py', args.historical.expanduser().resolve(strict=True),
                   '--apply', '--report', ROOT / 'reports/historical-import-review.json')
    if args.whois:
        whois = args.whois.expanduser().resolve(strict=True)
        run_script('scripts/import_mudlet_whois_archive.py', whois)
    if args.historical or args.whois:
        run_script('scripts/build_whois_queue.py')
    run_script('scripts/validate_data.py')
    if not args.export_only:
        for script in ('report_whois_descriptor_classification.py',
                       'report_whois_social_and_formatting.py',
                       'build_immortal_evidence.py', 'build_player_affiliation_evidence.py',
                       'build_derived_character_classification.py', 'export_whois_evidence_files.py'):
            run_script('scripts/' + script)
        if args.whois:
            # Use the explicitly imported capture for its formatted evidence too.
            old_cwd = Path.cwd()
            try:
                os.chdir(ROOT)
                module = runpy.run_path(str(ROOT / 'scripts/export_whois_display_from_mudlet_archive.py'))
                module['main'].__globals__['ARCHIVE_CANDIDATES'] = [whois]
                module['main']()
            finally:
                os.chdir(old_cwd)
        run_script('scripts/build_character_pages_manifest.py')
        run_script('scripts/validate_data.py')
    # Generate and validate a temporary export before replacing the current one.
    with tempfile.TemporaryDirectory(prefix='deck-build-') as temporary:
        export = Path(temporary) / 'deck-data.js'
        run_script('site/deck-of-chars/scripts/export_deck_data_from_archive.py', ROOT, export)
        value = export.read_text(encoding='utf-8')
        data = json.loads(value.removeprefix('window.DECK_CHARS = ').removesuffix(';\n'))
        if not data.get('characters'):
            raise ValueError('Refusing to publish an empty character archive.')
        if shutil.which('node'):
            subprocess.run(['node', '--check', str(export)], check=True)
            subprocess.run(['node', '--check', str(SITE / 'deck-of-chars.js')], check=True)
        destination = SITE / 'assets/data/deck-data.js'
        staging_data = destination.with_suffix('.js.tmp')
        shutil.copyfile(export, staging_data)
        staging_data.replace(destination)
    stage = ROOT / 'dist/deck-of-chars'
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    for name in ('index.html', 'bree-theme.css', 'deck-of-chars.css', 'deck-of-chars.js', '.htaccess'):
        shutil.copy2(SITE / name, stage / name)
    shutil.copytree(SITE / 'assets', stage / 'assets')
    archive = shutil.make_archive(str(ROOT / 'dist/deck-of-chars'), 'zip', ROOT / 'dist', 'deck-of-chars')
    print(f'Built {len(data["characters"])} characters. Upload package: {archive}', flush=True)
    build_plugin()
    if isinstance(deploy, dict):
        deck_wordpress_api.publish(deploy, data, args.dry_run)
        return
    if deploy:
        target, remote = deploy
        if not args.dry_run:
            subprocess.run(['ssh', target, f'mkdir -p -- {remote}'], check=True)
        command = ['rsync', '-rz', '--delay-updates', '--itemize-changes', '-e', 'ssh']
        if args.dry_run:
            command.append('--dry-run')
        # No --delete: existing server files are never removed.
        subprocess.run([*command, str(stage) + '/', f'{target}:{remote}/'], check=True)
        print('Upload preview complete.' if args.dry_run else 'Deck of Chars published.', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print(f'Deck build/publish stopped: {exc}', file=sys.stderr)
        sys.exit(1)
