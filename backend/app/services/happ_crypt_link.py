"""Create Happ crypt5 import links without exposing the feed URL in redirects."""

import re

import httpx


CRYPTO_API = "https://crypto.happ.su/api-v2.php"
CRYPT5_PATTERN = re.compile(r"^happ://crypt5/[A-Za-z0-9_+/%=.-]+$")


def encrypted_happ_link(subscription_url: str) -> str:
    response = httpx.post(
        CRYPTO_API,
        json={"url": subscription_url},
        timeout=6.0,
        follow_redirects=False,
    )
    response.raise_for_status()
    if len(response.content) > 16384:
        raise ValueError("Happ crypto response too large")
    try:
        payload = response.json()
    except ValueError:
        payload = response.text.strip()
    if isinstance(payload, dict):
        payload = next(
            (payload[key] for key in ("url", "link", "result", "encrypted_url",
                                     "encrypted_link", "encryptedUrl")
             if isinstance(payload.get(key), str)),
            None,
        )
    if not isinstance(payload, str) or not CRYPT5_PATTERN.fullmatch(payload.strip()):
        raise ValueError("Unexpected Happ crypto response")
    return payload.strip()
