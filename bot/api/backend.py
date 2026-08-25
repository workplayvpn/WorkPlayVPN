import httpx

from config import backend_url


async def backend_get(
    path: str,
) -> httpx.Response:
    async with httpx.AsyncClient(
        timeout=10.0,
    ) as client:
        return await client.get(
            f"{backend_url}{path}"
        )


async def backend_post(
    path: str,
    payload: dict,
) -> httpx.Response:
    async with httpx.AsyncClient(
        timeout=10.0,
    ) as client:
        return await client.post(
            f"{backend_url}{path}",
            json=payload,
        )


async def backend_delete(
    path: str,
) -> httpx.Response:
    async with httpx.AsyncClient(
        timeout=10.0,
    ) as client:
        return await client.delete(
            f"{backend_url}{path}"
        )