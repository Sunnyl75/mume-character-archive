#!/bin/bash
cd -- "$(dirname -- "$0")" || exit 1
for deck_python in /usr/local/bin/python3 /opt/homebrew/bin/python3 python3; do
  if command -v "$deck_python" >/dev/null 2>&1 && "$deck_python" -c 'import sys; sys.exit(sys.version_info < (3, 10))' >/dev/null 2>&1; then
    exec "$deck_python" scripts/deck_workbench.py
  fi
done
printf '%s\n' 'Deck Workbench needs Python 3.10 or newer.' 'Install Python from https://www.python.org/downloads/macos/ and open this launcher again.'
read -r -p 'Press Return to close.' deck_reply
