# Direct-first Mobile auto route: closed iPhone pilot

The optional endpoint `/sub/auto/{mobile-token}` issues one experimental Happ
JSON profile for the first active device. It uses that device's existing Direct
Reality and separate CDN XHTTP credentials. Ordinary Basic and Mobile feed
URLs remain unchanged. By default `HAPP_AUTO_ROUTE_USER_IDS` is empty, so the
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

## Enable and inspect the pilot

1. Deploy only after the local automated suite passes. On the server, add
   `HAPP_AUTO_ROUTE_USER_IDS=174` to the private `.env` (replace `174` with
   the internal user ID of the pilot); recreate only the backend container.
   Keep `HAPP_MOBILE_NETWORK_HINT_USER_IDS=` empty.
2. On the pilot's device, take the existing personal **Mobile** subscription
   URL and insert `/auto` after `/sub`: `https://connect.workplayvpn.ru/sub/auto/<same-mobile-token>`.
   Keep this URL private. The Basic token must not work at this path.
3. Add it to Happ as a **separate** subscription. Keep the existing working
   Mobile and Basic subscriptions installed. If Happ rejects the JSON, stop
   here and keep using the original Mobile subscription.
4. Confirm Happ accepts the profile, provides a working VPN connection, and
   uses the supplied local SOCKS inbound. Inspect actual traffic on the node:
   Wi-Fi, unrestricted LTE, LTE with Direct unreachable, restored Direct,
   switching Wi-Fi/LTE while connected, and reconnection after a switch.
   Check CDN billed bytes against the node's CDN credential counters. Existing
   TCP connections may need to reconnect when the outbound changes.
5. Verify the separate routed JSON candidate and its DNS and GEO resources on
   Happ iOS before considering a replacement for the normal Mobile feed.

To close the endpoint, clear `HAPP_AUTO_ROUTE_USER_IDS` and recreate the
backend. Existing Basic and Mobile URLs are unaffected.

Do not print, commit, or paste generated JSON: it contains both device UUIDs,
the CDN address, and its private path.

References: Happ JSON passthrough documentation, Xray routing `fallbackTag`
and `leastPing`, and Xray observatory `subjectSelector`/`probeUrl`.
