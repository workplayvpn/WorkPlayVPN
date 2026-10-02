"""Set a numeric support owner ID without printing or changing other secrets."""
import argparse
import os
import re
from datetime import UTC, datetime
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--telegram-id',type=int,required=True)
p.add_argument('--apply',action='store_true')
args=p.parse_args()
if args.telegram_id<=0:p.error('Use your positive numeric Telegram user ID from /support_id')
path=Path('.env')
if not path.is_file():p.error('Run from the project directory containing .env')
text=path.read_text()
line=f'SUPPORT_ADMIN_TELEGRAM_ID={args.telegram_id}'
updated=re.sub(r'^SUPPORT_ADMIN_TELEGRAM_ID=.*$',line,text,flags=re.M) if re.search(r'^SUPPORT_ADMIN_TELEGRAM_ID=',text,re.M) else text.rstrip()+'\n'+line+'\n'
if not args.apply:
    print('Ready. Add --apply to save SUPPORT_ADMIN_TELEGRAM_ID; other settings will remain unchanged.')
else:
    backup=path.with_name('.env.before-support-'+datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ'))
    fd=os.open(backup,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as stream:stream.write(text)
    temporary=path.with_name('.env.support-tmp')
    fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as stream:stream.write(updated)
    temporary.replace(path)
    print('Support owner saved. Recreate bot to apply. Backup: '+str(backup))
