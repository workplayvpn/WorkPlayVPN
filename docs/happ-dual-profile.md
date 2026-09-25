# HAPP dual-profile rollout

The HAPP subscription feed supports two explicit access modes per VPN node:

- `wifi` — the normal direct profile;
- `mobile` — a separately tested mobile edge/CDN profile.

Paid Mobile uses `VpnDevice.xray_uuid` for the direct profile and a separate
`VpnDevice.mobile_xray_uuid` for the CDN profile. Both belong to one device
slot. Existing canary accounts without a Mobile credential retain the
original shared UUID during the pilot only.

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

Transport-specific settings such as `path`, `mode`, `alpn`, `fingerprint`,
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

HAPP prefers the direct VLESS Reality profile, then falls back to the existing
Wi-Fi or legacy XHTTP profile. A Basic subscription shows only the direct link,
without a Wi-Fi suffix. A Mobile subscription shows two links. Mobile sales
must remain disabled until the CDN service, SSH gateway, and backend credential
lifecycle are deployed and verified together.
