#!/usr/bin/env python3
"""Create the small Mac bootstrap installer; contains no archive or credentials."""
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    dest = ROOT / 'releases/Deck_Workbench_Setup.zip'
    dest.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(dest, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, content, mode in [
            ('Install_Deck_Workbench.command', (ROOT / 'Install_Deck_Workbench.command').read_bytes(), 0o100755),
            ('START_HERE.md', (ROOT / 'docs/deck-workbench.md').read_bytes(), 0o100644),
        ]:
            info = zipfile.ZipInfo(name, (2026, 11, 5, 0, 0, 0))
            info.create_system = 3
            info.external_attr = mode << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, content)
    print(dest)


if __name__ == '__main__':
    main()
