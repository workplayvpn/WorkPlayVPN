"""Enable the existing Mobile features for all eligible subscribers on this server."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import re
import subprocess

KEYS = (
    'MOBILE_PILOT_USER_IDS', 'HAPP_AUTO_ROUTE_USER_IDS',
    'HAPP_SMART_ROUTING_USER_IDS', 'HAPP_MOBILE_NETWORK_HINT_USER_IDS',
    'HAPP_HIDDEN_SETTINGS_USER_IDS', 'HAPP_CRYPT5_USER_IDS',
)


def public_env(content):
    lines = [line for line in content.splitlines() if not any(
        re.match(r'^\s*(?:export\s+)?'+re.escape(key)+r'\s*=',line) for key in KEYS)]
    return '\n'.join(lines).rstrip()+'\n\n# Public Mobile rollout\n'+''.join(key+'=*\n' for key in KEYS)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    env = Path('.env')
    if not env.is_file():
        raise SystemExit('Run from the project root containing .env.')
    if not args.apply:
        print('No changes made. --apply sets these controls to *:')
        print('\n'.join(KEYS))
        return
    # Validate configuration and encrypted import service before changing anything.
    code = '''import httpx
from app.core.config import settings
from app.services.happ_crypt_link import encrypted_happ_link
with httpx.Client(timeout=15) as client:
    response = client.get("http://127.0.0.1:8000/internal/happ/mobile-readiness", headers={"Authorization": "Bearer " + settings.internal_api_secret})
    response.raise_for_status()
    if response.json().get("status") != "ready":
        raise SystemExit("Mobile configuration is not ready; rollout stopped.")
if not settings.happ_provider_id:
    raise SystemExit("Happ provider ID is missing; rollout stopped.")
encrypted_happ_link(settings.subscription_base_url.rstrip("/") + "/public-rollout-check")
print("MOBILE_READINESS_AND_IMPORT_OK")
'''
    check = subprocess.run(['docker','compose','exec','-T','backend','python','-c',code],capture_output=True,text=True)
    if check.returncode:
        # Do not expose runtime tracebacks, configuration or credentials.
        print('Mobile readiness/provider/crypt5 preflight failed. .env was not changed.')
        raise SystemExit(1)
    print('MOBILE_READINESS_AND_IMPORT_OK')
    content = env.read_text()
    backup = env.with_name('.env.before-public-mobile-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    backup.write_text(content)
    backup.chmod(0o600)
    env.write_text(public_env(content))
    print('Public settings saved. Backup: '+str(backup))
    print('Recreate backend to apply. Payment mode, prices, subscriptions and secrets were not changed.')


if __name__ == '__main__':
    main()
