"""
Builds a single copy-pasteable diagnostic block: recent log tails,
current app version, last git commit. Meant to be pasted straight into
a chat when something's failing, so debugging doesn't start with
"can you send me your logs".

Never includes secrets: only log content (which the logging setup never
lets carry secret values — see api/_logging_setup.py), the app version,
and git metadata.

Run: python scripts/diagnostic_bundle.py
"""

import json
import os
import subprocess
from datetime import datetime, timezone

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS_DIR = os.path.join(PROJECT_ROOT, 'logs')
TAIL_LINES = 200


def tail(path: str, n: int) -> str:
    if not os.path.exists(path):
        return '(no log file yet)'
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()
    return ''.join(lines[-n:]) or '(empty)'


def get_version() -> str:
    pkg_path = os.path.join(PROJECT_ROOT, 'package.json')
    try:
        with open(pkg_path, encoding='utf-8') as f:
            return json.load(f).get('version', 'unknown')
    except OSError:
        return 'unknown'


def get_git_info() -> str:
    try:
        commit = subprocess.check_output(
            ['git', 'log', '-1', '--format=%H %s (%ci)'], cwd=PROJECT_ROOT, text=True
        ).strip()
        branch = subprocess.check_output(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'], cwd=PROJECT_ROOT, text=True
        ).strip()
        dirty = subprocess.check_output(
            ['git', 'status', '--porcelain'], cwd=PROJECT_ROOT, text=True
        ).strip()
        suffix = ' (uncommitted changes present)' if dirty else ''
        return f'{branch} @ {commit}{suffix}'
    except Exception:
        return 'unavailable (not a git repo or git not installed)'


def build_bundle() -> str:
    parts = [
        '=== TrendPulse diagnostic bundle ===',
        f"Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f'Version: {get_version()}',
        f'Git: {get_git_info()}',
        '',
        f'--- logs/scraper.log (last {TAIL_LINES} lines) ---',
        tail(os.path.join(LOGS_DIR, 'scraper.log'), TAIL_LINES),
        '',
        f'--- logs/api.log (last {TAIL_LINES} lines) ---',
        tail(os.path.join(LOGS_DIR, 'api.log'), TAIL_LINES),
    ]
    return '\n'.join(parts)


def main():
    bundle = build_bundle()

    os.makedirs(LOGS_DIR, exist_ok=True)
    out_path = os.path.join(LOGS_DIR, 'diagnostic_bundle.txt')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(bundle)

    print(bundle)
    print(f'\n(Also saved to {out_path} — paste either the above or that file.)')


if __name__ == '__main__':
    main()
