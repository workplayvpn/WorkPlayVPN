"""Add same-origin help API routing without replacing a locally customized Caddyfile."""
import argparse
from datetime import datetime, UTC
from pathlib import Path
import re

parser = argparse.ArgumentParser()
parser.add_argument('--apply', action='store_true')
parser.add_argument('--caddyfile', type=Path, default=Path('caddy/Caddyfile'))
args = parser.parse_args()
path = args.caddyfile
text = path.read_text()
block = '\n        # workplay-help-access: same-origin backend routes\n        @help_access path /help-access/*\n        reverse_proxy @help_access backend:8000\n'
# Exact existing public virtual host, leaving other domains untouched.
match = re.search(r'(?m)^workplayvpn\.ru\s*\{', text)
if not match:
    raise SystemExit('Public workplayvpn.ru block not found; no files changed')
# Refuse ambiguous configurations instead of guessing where the API belongs.
if len(re.findall(r'(?m)^workplayvpn\.ru\s*\{', text)) != 1:
    raise SystemExit('Multiple public blocks found; no files changed')
if '        # workplay-help-access: same-origin backend routes' in text:
    print('Help routing is already configured')
    raise SystemExit(0)
if '@help_access' in text:
    raise SystemExit('Matcher name already exists; no files changed')
updated = text[:match.end()] + block + text[match.end():]
if not args.apply:
    print('Ready: add /help-access/* routing only to workplayvpn.ru; other domains stay intact')
else:
    backup = path.with_name(path.name + '.before-help-' + datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ'))
    backup.write_text(text)
    path.write_text(updated)
    print('Help routing added; validate and reload Caddy before opening the page')
