# HAPP dual-profile rollout

The HAPP subscription feed supports two explicit access modes per VPN node:

- `wifi` — the normal direct profile;
- `mobile` — a separately tested mobile edge/CDN profile.

Both links are built from the same `VpnDevice.xray_uuid`, so they consume one
device slot and follow the same account-level region selection.

## Profile settings

Access mode and optional HAPP overrides are stored in the existing
`vpn_node_profiles.settings` JSON object:

```json
{
  "happ_access_mode": "mobile",
  "happ_server_address": "mobile.example.com",
  "happ_display_name": "Netherlands — Mobile"
}
```

Transport-specific settings such as `path`, `mode`, `fingerprint`,
`public_key`, and `short_id` continue to work as before.

The mobile profile must not be made active until its public endpoint, TLS,
origin routing, and real mobile-network behavior have been verified.

## Safe rollout

`HAPP_MOBILE_PROFILE_USER_IDS` controls who receives the mobile link:

- empty — disabled for everyone (default);
- `1` — enabled only for user 1;
- `1,33` — enabled for users 1 and 33;
- `*` — enabled for every HAPP subscriber.

The setting affects HAPP only. Generic and Hiddify subscription output is
unchanged.

## Backward compatibility

If no explicit `wifi` profile exists, HAPP keeps selecting the first active
legacy VLESS + XHTTP + TLS profile, exactly as before this change. An explicit
mobile profile is never returned unless the requesting user is allowed by the
rollout setting.
