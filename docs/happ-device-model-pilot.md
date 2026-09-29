# Happ device model and OS: closed pilot

Happ 5.9.0 sends `X-Device-Model` and `X-Device-OS` when it requests a
subscription. An observed iPhone request identified `iPhone 14 Pro Max` and
`iOS`. The Telegram Mini App itself cannot determine an exact iPhone model;
the card is updated after Happ refreshes a per-device subscription link.

Apply Alembic migration `6ac0e95b2d41` before restarting the backend. It
adds optional device model, OS and a keyed digest of Happ's HWID. The raw HWID
is never stored. A device's public `WP-...` ID remains visible only in Mini App,
not in Happ's configuration name. Device labels are not proof of identity:
clients can forge HTTP headers. Do not use them for authorization, billing or
device-limit enforcement.

For a device with a Basic entitlement, Mini App now presents a Basic link bound
to that device. The existing per-device Mobile link remains. The user must
import the corresponding per-device link in Happ and refresh it. Old shared
Basic and Mobile subscription URLs continue working, but with several devices
the server does not guess which device made a shared-link request: it records
the label only when exactly one device is active or a previously associated
HWID digest identifies one device. New per-device links validate both the
subscription token and ownership of the active device.

After an import or refresh, reload the Mini App device list. It should display
`iPhone 14 Pro Max (iOS)` or the OS version if Happ supplies a valid one,
followed by its stable `WP-...` ID. For a device not yet observed via Happ, the
user-entered name stays visible. Repeat for a second device to confirm the
first card does not change. Exact identification depends on the installed
Happ client sending these headers; it cannot be guaranteed for every client.

Keep `SUBSCRIPTION_CLIENT_DIAGNOSTICS=false` in the server's private `.env` and
recreate the backend if temporary diagnostics were enabled. Do not publish
personal subscription links, HWIDs or request logs. The older shared links do
not need to be revoked. Deleting a device deletes its metadata with the row.

Local verification from the project root:

```sh
docker compose --profile testing run --rm tests
```

On the server, pull the tested commit and run `docker compose exec -T backend
alembic upgrade head` while the old backend is running. Then run
`docker compose up -d --build --no-deps --wait backend` and verify `/health`.
