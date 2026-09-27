# Mobile network candidates for a Happ pilot

`HAPP_MOBILE_NETWORK_HINT_USER_IDS` is empty by default. For an explicitly
listed database user ID with an active Mobile subscription, the Happ feed
offers these candidates in order:

1. Direct Reality: `only WiFi`.
2. The same Direct Reality credential: `only Mobile`.
3. The separate CDN credential: `only Mobile`.

The Basic feed, other users, and non-Happ clients retain their current output.
If the CDN credential or profile is missing, the feed stays unchanged so the
Direct entry remains usable on cellular networks.

Happ documents name-based filtering in Premium subscriptions. This does not
prove automatic reconnection of a running tunnel when Wi-Fi changes to LTE,
and it does not test whether Reality is reachable on a particular operator.
No probe result or central outage flag controls this feed.

Before widening the canary, check on the pilot iPhone with a Premium Happ
subscription: import/update, Wi-Fi, LTE with direct access, LTE while the
direct route is unavailable, LTE to Wi-Fi while connected, and app relaunch.
Record which route was actually used and whether the tunnel reconnected.
Keep the field empty to restore the existing two-entry Mobile feed.
