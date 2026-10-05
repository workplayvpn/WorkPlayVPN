from fastapi import APIRouter, Depends, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.services.payment_redirect_service import (
    payment_redirect_service,
)


router = APIRouter(
    prefix="/pay",
    tags=["payment-redirects"],
)


@router.get("/return", include_in_schema=False)
def return_to_telegram() -> RedirectResponse:
    # Browser return is navigation only; it never confirms or fulfils a payment.
    return RedirectResponse(
        url="https://t.me/workplayvpn_bot?start=payment_return",
        status_code=status.HTTP_302_FOUND,
        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
    )


@router.get(
    "/{token}",
    include_in_schema=False,
)
def redirect_to_payment(
    token: str,
    database: Session = Depends(get_db),
) -> RedirectResponse:
    confirmation_url = (
        payment_redirect_service.resolve_confirmation_url(
            database=database,
            raw_token=token,
        )
    )

    return RedirectResponse(
        url=confirmation_url,
        status_code=status.HTTP_302_FOUND,
        headers={
            "Cache-Control": "no-store",
            "Pragma": "no-cache",
            "Referrer-Policy": "no-referrer",
            "X-Robots-Tag": (
                "noindex, nofollow, noarchive"
            ),
        },
    )
