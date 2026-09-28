# Direct-first Mobile auto route: closed iPhone pilot

The optional endpoint `/sub/auto/{mobile-token}` issues one experimental Happ
JSON profile for the first active device. It uses that device's existing Direct
Reality and separate CDN XHTTP credentials. By default `HAPP_AUTO_ROUTE_USER_IDS` is empty, so the
endpoint is unavailable to everyone. It accepts only an exact comma-separated
list of internal user IDs; `*` is deliberately unsupported. The caller must
also hold a valid Mobile-scoped token and an active Mobile subscription.

The generated Xray balancer observes only `vpn-direct`. It selects Direct when
the local probe marks it healthy and `vpn-cdn` as the fallback for new
connections. The probe is issued on the client device over Direct; the backend
cannot measure reachability from a subscriber's cellular network. The profile
does not switch specifically on Wi-Fi/LTE: Direct remains preferred on either
network when reachable. Probes are not routed through CDN.

The original JSON passed `xray run -test -config stdin:` on the server's Xray
26.9.9. On the first iPhone pilot, CDN counters stayed flat after Wi-Fi
browsing, grew on LTE where the standalone Basic Direct profile did not load
sites, and then stayed flat again after returning to Wi-Fi. A separate forced
failure test reached the Netherlands over CDN. These observations cover one
device and two networks, not general rollout. Happ passes JSON configurations
to Xray as supplied, so the normal Happ Smart Routing profile does not apply
to the original JSON profile.

An additional pilot URL `/sub/auto/routed/{mobile-token}` builds a separate
JSON profile with the existing `geosite:category-ru`, `geoip:ru`/private,
and domestic DNS policies inside Xray. It requires the same Mobile token,
active Mobile entitlement, and exact pilot ID. The original `/sub/auto/` URL
remains unchanged. Test Xray syntax with geodata available to Happ, then
verify domestic sites use the local address and foreign sites use the VPN on
both Wi-Fi and LTE. If import, DNS, or domestic bypass fails, return to the
working pilot. Do not open the new URL to other users before device testing.

For a user listed in `HAPP_AUTO_ROUTE_USER_IDS`, the existing Mobile-scoped
`/sub/{mobile-token}` feed serves **one routed JSON configuration** when Happ
requests it. The Basic feed is unchanged. The original Mobile URL for users
outside the pilot still serves its two manual VLESS profiles. The old
`/sub/auto/` diagnostic URL remains available only to the same pilot IDs.

The Devices view offers a Mobile link for each provisioned active
device: `/sub/auto/routed/device/{device-id}/{mobile-token}`. The server checks
the pilot ID, Mobile entitlement, and device ownership/activity on every feed
refresh. Each generated profile uses that device's own Direct and CDN UUIDs.
The main Mobile button links to the first provisioned device. The earlier
unscoped pilot URL remains available for previously imported subscriptions.
Remove those old pilot subscriptions manually from Happ after confirming the
new Mobile profile works; backend cannot remove a Happ subscription on device.

Happ presents `Work&PlayVPN Basic` and `Work&PlayVPN Mobile` as separate
subscription titles. A short tier-specific announcement is sent as base64
UTF-8; Mobile shows one Netherlands server. The `subscription-userinfo`
response metadata contains only the correct tier's `expire` timestamp. It
omits traffic fields until complete counters are available. Verify on the
pilot iPhone that Happ displays the expiry with only this field. Server
subtitle customization needs a Happ Provider ID and is outside this rollout.

| Subscription | Announcement in Happ |
| --- | --- |
| Basic | Надёжное подключение для работы и отдыха. |
| Mobile (routed pilot) | Подключение для Wi-Fi и мобильной сети. Маршрут выбирается автоматически. |

The Mobile configuration name comes from the selected node's Direct Happ
profile label (without its Wi-Fi suffix). A later region change must update
the device's node and its profiles; the displayed country then follows that
profile instead of staying fixed to the Netherlands.

## Enable and inspect the pilot

1. Deploy only after the local automated suite passes. On the server, add
   `HAPP_AUTO_ROUTE_USER_IDS=174` to the private `.env` (replace `174` with
   the internal user ID of the pilot); recreate only the backend container.
   Keep `HAPP_MOBILE_NETWORK_HINT_USER_IDS=` empty.
2. Refresh the existing personal **Mobile** subscription in Happ. The user
   should see one Netherlands configuration under `Work&PlayVPN Mobile`.
   Keep a copy of the previously working Mobile link in a private place for
   a quick rollback. Basic remains separate.
3. Confirm Happ accepts the profile, provides a working VPN connection, and
   uses the supplied local SOCKS inbound. Inspect actual traffic on the node:
   Wi-Fi, unrestricted LTE, LTE with Direct unreachable, restored Direct,
   switching Wi-Fi/LTE while connected, and reconnection after a switch.
   Check CDN billed bytes against the node's CDN credential counters. Existing
   TCP connections may need to reconnect when the outbound changes.
4. Verify the expiry date and short description in Happ. Check the two
   per-device links issue different credentials. If a subscription previously
   imported from `/sub/auto/` remains, delete the duplicate pilot entry in Happ.

To revert a problematic Mobile feed for the pilot, clear
`HAPP_AUTO_ROUTE_USER_IDS` and recreate the backend. The existing Mobile URL
returns its two VLESS profiles again; previously imported per-device URLs
become unavailable until the pilot gate is restored. Basic is unaffected.

Do not print, commit, or paste generated JSON: it contains both device UUIDs,
the CDN address, and its private path.

References: Happ JSON passthrough documentation, Xray routing `fallbackTag`
and `leastPing`, and Xray observatory `subjectSelector`/`probeUrl`.
