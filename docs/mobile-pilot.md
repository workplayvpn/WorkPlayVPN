# Closed Mobile purchase pilot

The migrations create five Mobile plans, all with three devices. The pilot
durations migration enables the four previously inactive durations; the
30-day row is managed separately and is already active on the first canary.
The existing `MOBILE_PILOT_USER_IDS` gate still blocks everyone else from
seeing Mobile plans or starting their payments.

| Code | Days | Pilot price (RUB) |
| --- | ---: | ---: |
| `mobile_7d` | 7 | 99 |
| `mobile_1m` | 30 | 249 |
| `mobile_3m` | 90 | 699 |
| `mobile_6m` | 180 | 1299 |
| `mobile_12m` | 365 | 2290 |

Longer-duration prices are provisional. Confirm usage and CDN bills before
opening sales beyond the canary. Changing a price later does not alter prior
purchases. This migration opens the four additional durations only to pilot
users, including the existing canary.

The backend Compose variable `MOBILE_PILOT_USER_IDS` is a comma-separated list
of internal database user IDs; the default is empty. Only those signed users
can see an *active* Mobile plan in Mini App and start its payment. The public
bot catalog continues to list Basic plans only. Both Mini App and the internal
payment API use the same server-side purchase check.

Pilot gate, after tests and deployment:

1. Select a pilot user. An active paid Basic subscription can coexist with a
   separate Mobile subscription; buying Mobile preserves Basic's remaining
   time. A user on the free one-day trial can buy Mobile at full price; their
   unused trial time is kept and a separate Mobile credential is added to
   each active device.
2. Set `MOBILE_PILOT_USER_IDS` in the server's private `.env`, recreate the
   backend container so Compose receives the updated environment, and verify
   the value from application settings without printing personal credentials.
3. Apply the latest migration. Keep `mobile_1m` active if it was activated for
   the canary. Verify a non-pilot signed user does not see Mobile and receives
   404 when attempting direct payment.
4. Verify the pilot sees all five prices (including 249 RUB for 30 days),
   creates an idempotent test payment, receives distinct Direct and Mobile
   UUIDs, and can connect over both networks.
5. Compare the local Xray usage snapshot with CDN billing. Keep the plan
   limited to the pilot while measuring actual consumption.

To close new Mobile purchases immediately, remove all IDs from
`MOBILE_PILOT_USER_IDS` and recreate the backend. Existing active users retain
their keys until expiry. This gate does not revoke existing subscriptions.
