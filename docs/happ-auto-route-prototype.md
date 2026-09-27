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

## Isolated CDN fallback check

The temporary `/sub/auto/failover/{mobile-token}` endpoint is available only
to the same pilot user. It changes the Direct destination *inside the issued
client JSON* to `127.0.0.1:1` and labels the profile `WorkPlayVPN CDN fallback
test`. It does not change the real Direct node, its credentials, or any other
user's subscription. The CDN outbound and the balancer remain unchanged.

Import this as a separate subscription by inserting `/failover` after
`/sub/auto` in the existing pilot URL. Keep the working `Mobile Auto` profile.
After the probe has had time to mark Direct unhealthy, open a small web page.
If it loads, the only reachable outbound in this JSON is the CDN. If it does
not load, return to the working profile and inspect the pilot config before
doing any further tests. This proves fallback under forced failure, not
real-world performance or recovery on a restricted mobile network. Do not
stream video or perform large downloads during this CDN test. Remove this
temporary test subscription after the check.

Do not print, commit, or paste generated JSON: it contains both device UUIDs,
the CDN address, and its private path.

References: Happ JSON passthrough documentation, Xray routing `fallbackTag`
and `leastPing`, and Xray observatory `subjectSelector`/`probeUrl`.
