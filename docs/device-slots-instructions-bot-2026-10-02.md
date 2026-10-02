# Shared device slots, instruction theme and bot navigation

Based on 082f7c7. Prices: +1 = 249 RUB, +2 = 449 RUB, +3 = 649 RUB.
Bot and Mini App get offers from the same authenticated server service. Prices
come from seeded database plans, never client input. Requires an active Basic or
Mobile subscription. Extra slots belong to the user, persist through renewal,
and are counted while at least one subscription remains active.

Migration b7e402d91a63 (parent 8e7a1c4b902d) adds three device_slots plans, hidden
from the subscription catalogue. Slot payment is delivered atomically under
payment/user row locks. It creates no VPN entitlement/device, changes no expiry,
and repeated callbacks must not credit twice, including stale ORM sessions.
A delivered fulfillment record is written synchronously; there is no Telegram
fulfillment message for slot purchases. Existing payment mode is unchanged.

Device UI renders occupied/vacant slots, including 3/10. Manual model input is
removed; new connection uses the existing client_instance_id registration API
without manual input. Happ later reports model/OS. Add limit is separate from
Connect through Happ on the subscription card. Instruction theme is updated.
Bot Mobile first with primary accent and emoji; Basic neutral. Terms include
product descriptions, compact duration buttons, and Back opens the catalogue.

Validation: 19 offline bot tests; local SQLite database scenarios (not a substitute
for PostgreSQL locks), JS syntax and DOM slot checks. Run full PostgreSQL suite.
Deploy after tests/commit/push: pull, build backend/bot, run
`docker compose run --rm --no-deps backend alembic upgrade head`, verify current,
then recreate backend and bot. Static files are bind mounted by Caddy.
No production payments or migrations were performed while preparing this patch.
