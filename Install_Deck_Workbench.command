#!/bin/bash
for deck_python in /usr/local/bin/python3 /opt/homebrew/bin/python3 python3; do
  if command -v "$deck_python" >/dev/null 2>&1 && "$deck_python" -c 'import sys; sys.exit(sys.version_info < (3, 10))' >/dev/null 2>&1; then
    "$deck_python" - <<'PY'
import datetime
import fcntl
import io
import os
from pathlib import Path, PurePosixPath
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile

def dialog(message):
    return subprocess.run(['osascript', '-e', 'on run argv', '-e',
        'display dialog (item 1 of argv) buttons {"Cancel", "Install"} default button "Install"',
        '-e', 'end run', message], capture_output=True).returncode == 0

try:
    root = Path.home() / 'mume-character-archive'
    if not (root / 'data/working/characters.csv').is_file():
        selected = subprocess.run(['osascript', '-e', 'POSIX path of (choose folder with prompt "Choose your existing mume-character-archive folder")'], check=True, text=True, capture_output=True).stdout.strip()
        root = Path(selected)
    if not (root / 'data/working/characters.csv').is_file() or not (root / '.git').exists():
        raise ValueError('Choose the existing character archive Git repository containing data/working/characters.csv.')
    lockfile = open(root / '.deck-workbench.lock', 'a+')
    os.chmod(lockfile.name, 0o600)
    try:
        fcntl.flock(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise ValueError('Close the running Deck Workbench launcher window before updating its code.')
    if not dialog('Install Deck Workbench in:\n' + str(root) + '\n\nThis downloads code from your Sunnyl75 repository and backs up files before replacing them. Your existing archive data, captures, portraits and publishing key are preserved. Missing bundled reference/source tables are added only if absent. Your current Git branch is not switched.'):
        sys.exit(0)
    print('Downloading the workbench code…', flush=True)
    subprocess.run(['git', '-C', str(root), 'fetch', 'https://github.com/Sunnyl75/mume-character-archive.git', 'feature/workbench-review-export'], check=True)
    commit = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'FETCH_HEAD'], text=True).strip()
    scopes = ['scripts', 'workbench', 'site/deck-of-chars', 'site/date-indicators', 'research', 'integrations/wordpress/bree-mume-date-indicators', 'integrations/wordpress/bree-deck-of-chars',
              'data/reference', 'data/incoming/player_affiliations', 'Open Deck Workbench.command',
              'docs/deck-workbench.md', 'docs/historical-evidence-workflow.md']
    content = subprocess.check_output(['git', '-C', str(root), 'archive', '--format=tar', commit, *scopes])
    backup = Path.home() / 'Library/Application Support/MUME Deck Workbench/installation-backups' / datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    changed, added = [], []
    with tarfile.open(fileobj=io.BytesIO(content)) as archive:
        files = []
        for member in archive.getmembers():
            p = PurePosixPath(member.name)
            if not member.isfile() or p.is_absolute() or '..' in p.parts:
                continue
            name = member.name
            code = (name.startswith(('workbench/', 'integrations/wordpress/bree-deck-of-chars/', 'integrations/wordpress/bree-mume-date-indicators/', 'site/date-indicators/', 'docs/'))
                    or name == 'research/epoch-responses/rules.json'
                    or name == 'research/date_indicators.json' and not (root / name).exists()
                    or name == 'Open Deck Workbench.command'
                    or name.startswith('scripts/') and name.endswith('.py')
                    or name.startswith('site/deck-of-chars/') and '/assets/' not in name
                       and p.suffix in {'.html', '.css', '.js', '.py'}
                    or name == 'site/deck-of-chars/.htaccess')
            missing_reference = name.startswith(('data/reference/', 'data/incoming/player_affiliations/')) and not (root / name).exists()
            if code or missing_reference:
                files.append((member, root / name))
        try:
            for member, target in files:
                if target.is_symlink():
                    raise ValueError('An installation target is a symbolic link: ' + str(target))
                if target.exists():
                    saved = backup / target.relative_to(root)
                    saved.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(target, saved)
                    changed.append((target, saved))
                else:
                    added.append(target)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.extractfile(member).read())
                target.chmod(member.mode)
        except BaseException:
            for target, saved in reversed(changed):
                shutil.copy2(saved, target)
            for target in added:
                target.unlink(missing_ok=True)
            raise
    backup.mkdir(parents=True, exist_ok=True)
    (backup / 'installed-commit.txt').write_text(commit + '\n')
    # The root lock is ignored by the app's normal repository rules too.
    git_exclude = subprocess.check_output(['git', '-C', str(root), 'rev-parse', '--git-path', 'info/exclude'], text=True).strip()
    exclude = Path(git_exclude)
    if not exclude.is_absolute():
        exclude = root / exclude
    exclude.parent.mkdir(parents=True, exist_ok=True)
    existing = exclude.read_text() if exclude.exists() else ''
    if '/.deck-workbench.lock' not in existing:
        exclude.write_text(existing + '\n/.deck-workbench.lock\n')
    desktop = Path.home() / 'Desktop/Deck of Chars Workbench.command'
    if desktop.parent.exists() and not desktop.exists():
        desktop.write_text('#!/bin/bash\nexec /bin/bash ' + shlex.quote(str(root / 'Open Deck Workbench.command')) + '\n')
        desktop.chmod(0o755)
    lockfile.close()
    print('Installed from commit ' + commit, flush=True)
    print('Previous code files: ' + str(backup), flush=True)
    print('Open the Desktop launcher or Open Deck Workbench.command inside your archive folder next time.', flush=True)
    subprocess.Popen([sys.executable, str(root / 'scripts/deck_workbench.py')], cwd=root)
except Exception as exc:
    print('\nInstallation stopped: ' + str(exc), file=sys.stderr)
    print('Your archive data has not been replaced.', file=sys.stderr)
    input('Press Return to close.')
    sys.exit(1)
PY
    exit $?
  fi
done
printf '%s\n' 'Deck Workbench needs Python 3.10 or newer.' 'Install Python from https://www.python.org/downloads/macos/ and open this installer again.'
read -r -p 'Press Return to close.' deck_reply
