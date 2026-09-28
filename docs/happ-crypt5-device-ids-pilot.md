# Happ encrypted links, routing and device labels: closed pilot

Apply Alembic migration `9b2de7634a10` before deploying the new backend. It
backfills a random `WP-` public ID for each existing device; internal integer
primary keys and existing feed paths remain stable. New devices get a random
public ID at insertion. The Mini App and the private Mobile usage report show
the new ID.

For the existing pilot user, set these values in the server's private `.env`:

```dotenv
HAPP_AUTO_ROUTE_USER_IDS=174
HAPP_SMART_ROUTING_USER_IDS=174
HAPP_CRYPT5_USER_IDS=174
```

Keep the current Provider ID and hidden settings flags. `HAPP_CRYPT5_USER_IDS`
uses exact internal user IDs, with an empty default. Launch links for both
Basic and Mobile call Happ's `crypto.happ.su/api-v2.php` over HTTPS and redirect
to its `happ://crypt5/` result. Happ's service receives the personal subscription
URL to produce that link. A failure returns 503 instead of an unencrypted
fallback. Previously imported subscriptions stay as they were: remove and
import each anew from the Mini App to test crypt5. The backend's feed URL
still contains a bearer token; do not copy it into logs or chat.

Basic sends Happ's Smart Routing header for the pilot. The Mobile single JSON
profile already includes equivalent RU/private bypass and its Direct/CDN
balancer; it now also sends the Happ routing header when the same pilot flag is
set. Check on an iPhone that both imports load, domestic traffic stays direct,
international traffic follows the VPN, and the Mobile CDN fallback still works
when Direct is unavailable. A crypt5 import should keep updating after adding.
If Happ's additional routing profile interferes with Mobile, clear
`HAPP_SMART_ROUTING_USER_IDS` and recreate the backend; Mobile's built-in RU
routing remains in its JSON configuration.

The Mini App detects an OS family from the WebView user agent and, where
available, an Android model. iOS/iPadOS do not reliably expose an exact model.
The connection sheet lets the user check or enter the model. Existing generic
names remain until they are changed by a separate rename flow; device public
IDs update on migration without changing credentials.

Local verification from project root:

```sh
docker compose --profile testing run --rm tests
```

Server sequence after local tests: pull the revision, run
`docker compose exec -T backend alembic upgrade head` (or the project's normal
migration command), recreate backend with `docker compose up -d --build
--no-deps --wait backend`, and check `/health`. Run the migration before the
backend restart. Do not run the migration on the wrong database.
