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

The database at `/var/lib/workplayvpn/mobile-usage.sqlite` is private to
root. Include it in server backups. For displayed traffic in Happ, create a
backend sync endpoint and enforce ownership before exposing any user totals.
