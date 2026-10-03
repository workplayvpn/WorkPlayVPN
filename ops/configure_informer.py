"""Store the separate bot token in a private server .env without echoing it."""
import getpass
import os
from pathlib import Path
import re


def main():
    path = Path('.env')
    if not path.is_file():
        raise SystemExit('Run from the project root containing .env')
    token = getpass.getpass('Informer bot token (hidden): ').strip()
    if not re.fullmatch(r'[0-9]{5,20}:[A-Za-z0-9_-]{20,200}', token):
        raise SystemExit('Invalid token format; no changes')
    values = {'INFORMER_BOT_TOKEN': token, 'INFORMER_OWNER_TELEGRAM_ID': '2027613435'}
    lines = path.read_text().splitlines()
    output = [line for line in lines if not any(re.match(r'^\s*'+key+r'\s*=', line) for key in values)]
    output += [key+'='+value for key, value in values.items()]
    temp = path.with_name('.env.informer.tmp')
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write('\n'.join(output)+'\n')
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()
    print('Informer configured for owner 2027613435. Token not displayed.')


if __name__ == '__main__':
    main()
