# Mobile access rollout (not yet enabled for purchase)

The active Basic catalog is unchanged. Plans have `access_tier=basic` by
default. A later Mobile plan can be activated only after the following gates.

1. Configure the CDN Xray with a loopback-only `HandlerService` at
   `127.0.0.1:10086`. Run the candidate through the installed Xray `-test`
   command before changing the live config. Back up the live config and
   verify that the pilot still works after the controlled CDN service restart.
2. Install `ops/xray/mobile-ssh-gateway` and
   `ops/xray/restore-mobile-users`. Create empty
   `/var/lib/workplayvpn/xray-mobile-users.tsv` and `.lock` owned by the same
   account as `xray-users.tsv`, mode `0600`. Add this dispatch to the existing
   `case "${action:-}" in` in `ssh-gateway`, leaving the other cases intact:

   ```bash
   add-mobile-user|remove-mobile-user|list-mobile-users)
       exec /usr/local/lib/workplayvpn/mobile-ssh-gateway
       ;;
   ```

3. Install `ops/xray/30-workplayvpn-mobile-restore.conf` under
   `/etc/systemd/system/xray-yandex-cdn-test.service.d/`, run
   `systemctl daemon-reload`, and restart **only**
   `xray-yandex-cdn-test.service`. The restore hook must succeed on a second
   restart after adding a disposable test client through the gateway.
4. Apply both Alembic revisions and deploy the backend. Run the test suite
   against `workplayvpn_test`, never the production database. Verify new
   device activation, deletion, subscription expiry, and restoration on a
   controlled Mobile test plan with only a canary user.
5. Inspect a Happ feed: the direct link uses the regular device UUID and
   the CDN link uses `mobile_xray_uuid`; the Basic feed has no CDN link.
   Confirm the CDN link's SNI, host, path, packet-up mode, and `alpn=h2`
   against the live CDN settings. Only then enable Mobile prices/catalog.

The pilot Xray config contains one static client. The new dynamic users are
stored separately and re-added through the local API after CDN restarts.
No script in this repository installs itself on the VPN node automatically.
