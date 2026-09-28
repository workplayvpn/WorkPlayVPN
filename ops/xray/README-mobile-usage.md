# Mobile traffic accounting rollout

This counts bytes for Xray clients whose email starts with `mobile_` on the
Yandex CDN Xray instance. It does not change links or enforce a quota. Compare
monthly totals with Yandex Cloud billing: VPN payload counters omit CDN HTTP
overhead, and traffic between polls for a removed client may be lost.

The candidate keeps the existing API, clients, and transport. Xray statistics
require `stats: {}`, level 0 user policy, and `StatsService`. Do not dump the
candidate JSON to terminal: it contains the static pilot client UUID.

1. Copy `prepare_mobile_stats.py`, `mobile_usage_collector.py` to the node.
2. On the node, as root, generate a private candidate from the running config:

   ```sh
   python3 /root/prepare_mobile_stats.py \
     /usr/local/etc/xray/yandex-cdn-test.json \
     /root/yandex-cdn-stats-candidate.json
   /usr/local/bin/xray run -test -config /root/yandex-cdn-stats-candidate.json
   ```

3. Back up the live config with restricted permissions. Install the tested
   candidate with the *same* owner/group/mode as the current live config. Then
   restart only `xray-yandex-cdn-test.service` and verify the restore hook and
   both Xray services. Stop here and restore the backup if the pilot fails.
4. Install collector at
   `/usr/local/lib/workplayvpn/mobile_usage_collector.py` with mode 0755,
   timer and unit at `/etc/systemd/system/`. Run `systemctl daemon-reload`,
   then a one-off `systemctl start workplayvpn-mobile-usage.service`. Check
   `journalctl -u workplayvpn-mobile-usage.service -n 20 --no-pager`. Enable
   the timer only after the one-off collection succeeds.
5. To view totals without exposing pseudonymous account names:

   ```sh
   python3 /usr/local/lib/workplayvpn/mobile_usage_collector.py --report
   ```

To view a seven-day UTC breakdown by anonymous Mobile key, install the updated
collector on the node and run:

```sh
python3 /usr/local/lib/workplayvpn/mobile_usage_collector.py --daily
```

`MOBILE_KEY_ID` is a short hash of the opaque Xray email. It groups traffic
for one credential but is **not** the Mini App device number. Daily history
starts with the first poll after installing this version; old cumulative
totals cannot be assigned to past dates. UTC day boundaries are based on the
time of collection, so bytes between polls near midnight may fall on the
next day. The collector updates its existing private database in place and
does not touch Xray configuration or enforce limits. Compare with Yandex CDN
billing, which may include additional HTTP transport bytes.

The database at `/var/lib/workplayvpn/mobile-usage.sqlite` is private to
root. Include it in server backups. For displayed traffic in Happ, create a
backend sync endpoint and enforce ownership before exposing any user totals.

## Private device reconciliation (administrator only)

After the backend is rebuilt with `app.cli.mobile_usage_report`, obtain the
`--daily` text on the NL node. Paste its header and rows as standard input to
this command on the FRA server (from the project root):

```sh
docker compose exec -T backend python -m app.cli.mobile_usage_report <<'REPORT'
UTC_DATE MOBILE_KEY_ID UPLINK_BYTES DOWNLINK_BYTES
REPORT
```

Replace the example input with the actual report. The command reads the
current `vpn_devices` table and prints UTC day, `WP-` device ID, internal user
ID, and counted bytes. It performs no database writes, and there is no public
endpoint. Run it only in an administrator's terminal; its output identifies
customers. `UNMATCHED` can mean a removed or rotated credential. Never guess
the device for an unmatched row. The daily counts reflect node counters, not
the CDN provider's billed bytes. This is an operator report, not a user-facing
quota or cost limit.
