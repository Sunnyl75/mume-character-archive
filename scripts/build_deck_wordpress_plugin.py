#!/usr/bin/env python3
"""Package the current public Deck as an installable WordPress plugin."""
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def build_plugin():
    site = ROOT / 'site/deck-of-chars'
    data = json.loads((site / 'assets/data/deck-data.js').read_text().removeprefix('window.DECK_CHARS = ').removesuffix(';\n'))
    if not data.get('characters'):
        raise ValueError('The Deck has no characters. Rebuild it before packaging.')
    stage = ROOT / 'dist/wordpress/bree-deck-of-chars'
    if stage.exists():
        shutil.rmtree(stage)
    shutil.copytree(ROOT / 'integrations/wordpress/bree-deck-of-chars', stage)
    public = stage / 'public'
    public.mkdir()
    for name in ('index.html', 'bree-theme.css', 'deck-of-chars.css', 'deck-of-chars.js'):
        shutil.copy2(site / name, public / name)
    shutil.copytree(site / 'assets', public / 'assets')
    (ROOT / 'dist/deck-data.json').write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    archive = shutil.make_archive(str(ROOT / 'dist/bree-deck-of-chars-1.0.0'), 'zip', stage.parent, stage.name)
    print(f'WordPress plugin: {archive}', flush=True)
    return archive


if __name__ == '__main__':
    build_plugin()
