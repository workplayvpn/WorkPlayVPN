# Direct-first Mobile auto route: closed iPhone pilot

The optional endpoint `/sub/auto/{mobile-token}` issues one experimental Happ
JSON profile for the first active device. It uses that device's existing Direct
Reality and separate CDN XHTTP credentials. Ordinary Basic and Mobile feed
URLs remain unchanged. By default `HAPP_AUTO_ROUTE_USER_IDS` is empty, so the
endpoint is unavailable to everyone. It accepts only an exact comma-separated
list of internal user IDs; `*` is deliberately unsupported. The caller must
also hold a valid Mobile-scoped token and an active Mobile subscription.

A separate appearance experiment, `/sub/auto/network/{mobile-token}`, issues
two JSON entries named `🇳🇱 Нидерланды — Wi-Fi only WiFi` and
`🇳🇱 Нидерланды — Mobile only Mobile`. Both contain exactly the same Direct-first
fallback policy and work on either network. Happ documents automatic *list*
filtering for `only WiFi` and `only Mobile` names in Premium subscriptions.
Test this with the actual iOS build: the visible list changing does not prove
that the already running tunnel was reselected. Keep `/sub/auto/{mobile-token}`
as the working one-entry pilot during this appearance test.

The generated Xray balancer observes only `vpn-direct`. It selects Direct when
the local probe marks it healthy and `vpn-cdn` as the fallback for new
connections. The probe is issued on the client device over Direct; the backend
cannot measure reachability from a subscriber's cellular network. The profile
does not switch specifically on Wi-Fi/LTE: Direct remains preferred on either
network when reachable. Probes are not routed through CDN.

The generated JSON passed `xray run -test -config stdin:` on the server's
Xray 26.9.9. This only validates syntax. Happ iOS import and actual fallback
remain unverified. Happ passes JSON configurations to Xray as supplied, so
the current Happ Smart Routing rules are not applied to this profile. Do not
replace the working Mobile feed or roll this out beyond the pilot yet.

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
5. Recreate the current Smart Routing rules in JSON and validate on the
   actual Happ iOS build before considering this a replacement for the
   normal Mobile feed.

To close the endpoint, clear `HAPP_AUTO_ROUTE_USER_IDS` and recreate the
backend. Existing Basic and Mobile URLs are unaffected.

Do not print, commit, or paste generated JSON: it contains both device UUIDs,
the CDN address, and its private path.

References: Happ JSON passthrough documentation, Xray routing `fallbackTag`
and `leastPing`, and Xray observatory `subjectSelector`/`probeUrl`.
