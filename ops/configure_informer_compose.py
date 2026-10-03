"""Add informer service while preserving server-local DB, mounts and domains."""
import argparse
from pathlib import Path
import re


def configure(text):
    match = re.search(r'(?ms)^  payment-fulfillment-worker:\n.*?(?=^  [a-zA-Z0-9_-]+:|^[a-zA-Z0-9_-]+:|\Z)', text)
    if not match or '    environment:\n' not in match[0]:
        raise ValueError('payment-fulfillment-worker environment not found')
    section = match[0]
    for key, value in [('PAYMENT_MODE', '${PAYMENT_MODE:-test}'), ('ROBOKASSA_IS_TEST', '${ROBOKASSA_IS_TEST:-true}')]:
        if not re.search(r'(?m)^      '+key+r':', section):
            section = section.replace('    environment:\n', f'    environment:\n      {key}: "{value}"\n', 1)
    text = text[:match.start()] + section + text[match.end():]
    if re.search(r'(?m)^  informer-worker:', text):
        return text
    marker = text.index('  payment-fulfillment-worker:')
    service = '''  # workplay-informer: inherits the server's actual DB and worker settings
  informer-worker:
    extends:
      service: payment-fulfillment-worker
    container_name: workplayvpn-informer-worker
    command: ["python", "-m", "app.workers.informer"]
    environment:
      INFORMER_BOT_TOKEN: ${INFORMER_BOT_TOKEN:-}
      INFORMER_OWNER_TELEGRAM_ID: ${INFORMER_OWNER_TELEGRAM_ID:-2027613435}
    restart: unless-stopped

'''
    return text[:marker] + service + text[marker:]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    path = Path('docker-compose.yml')
    original = path.read_text()
    updated = configure(original)
    if args.apply:
        path.write_text(updated)
        print('Informer service configured; existing server settings preserved')
    else:
        print('Ready to configure informer service; use --apply')


if __name__ == '__main__':
    main()
