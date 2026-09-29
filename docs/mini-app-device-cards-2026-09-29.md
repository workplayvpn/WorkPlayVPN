# Device list and Telegram session recovery

The Mini App lists each device with a full, wrapping model/OS label and its
public ID. The region is shown once above the list. The bottom **Подключить
устройство** button opens a chooser for an existing device and its available
Basic/Mobile connection, or starts a new device activation if a slot is free.
The chooser remains usable when all slots are occupied; it does not create an
extra device for a reconnection.

The displayed denominator comes from `/mini-app/me` (`devices.total_limit`).
The backend's `shared_device_limit` computes the maximum active plan limit plus
`users.extra_device_slots`, counting shared physical devices only once across
Basic and Mobile. A future paid-slot fulfillment must update
`extra_device_slots` transactionally and idempotently and then refresh the
Mini App; adding a button alone would not sell or provision extra slots.

Telegram Mini App `initData` is accepted for five minutes. The frontend checks
its timestamp on resume and redirects users to the bot when it expires. A 401
response also shows the relaunch path. Reusing or retrying expired init data
cannot authenticate: reopen the Mini App through Telegram for new init data.

Pilot checks: update a subscription in HAPP, inspect the device card for the
full `iPhone 14 Pro Max (iOS)` label, use the bottom button to reopen either
existing tier without consuming a slot, fill all slots and repeat, lock the
phone for more than five minutes then confirm the bot link is actionable.
