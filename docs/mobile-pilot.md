# Closed Mobile purchase pilot

The migrations create five Mobile plans, all with three devices and
`is_active=false`. Applying them alone does not change the customer catalog.

| Code | Days | Pilot price (RUB) |
| --- | ---: | ---: |
| `mobile_7d` | 7 | 99 |
| `mobile_1m` | 30 | 249 |
| `mobile_3m` | 90 | 699 |
| `mobile_6m` | 180 | 1299 |
| `mobile_12m` | 365 | 2290 |

Longer-duration prices are provisional. Confirm usage and CDN bills before
activating long-duration plans; changing a price later does not alter prior
purchases. The first live canary can still use only `mobile_1m`.

The backend Compose variable `MOBILE_PILOT_USER_IDS` is a comma-separated list
of internal database user IDs; the default is empty. Only those signed users
can see an *active* Mobile plan in Mini App and start its payment. The public
bot catalog continues to list Basic plans only. Both Mini App and the internal
payment API use the same server-side purchase check.

Pilot gate, after tests and deployment:

1. Select a disposable user with no paid Basic subscription. A user on the
   free one-day trial can buy Mobile at full price; their unused trial time is
   kept and the separate Mobile credential is added to each active device.
   Changing from an active paid Basic subscription still needs a separate
   prorated upgrade flow.
2. Set `MOBILE_PILOT_USER_IDS` in the server's private `.env`, recreate the
   backend container so Compose receives the updated environment, and verify
   the value from application settings without printing personal credentials.
3. Activate only the `mobile_1m` database row. Verify a non-pilot signed user
   does not see Mobile and receives 404 when attempting direct payment.
4. Verify the pilot sees 249 RUB, creates an idempotent test payment, receives
   distinct Direct and Mobile UUIDs, and can connect over both networks.
5. Compare the local Xray usage snapshot with CDN billing. Keep the plan
   limited to the pilot while measuring actual consumption.

To close new Mobile purchases immediately, remove all IDs from
`MOBILE_PILOT_USER_IDS` and recreate the backend. Existing active users retain
their keys until expiry. This gate does not revoke existing subscriptions.
