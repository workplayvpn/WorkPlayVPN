from fastapi import (
    APIRouter,
    Depends,
    Request,
)
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.services.cloudpayments_webhook import (
    cloudpayments_webhook_service,
)
from app.services.robokassa_webhook import (
    robokassa_webhook_service,
)


router = APIRouter(
    prefix="/webhooks",
    tags=["payment-webhooks"],
)


@router.post("/cloudpayments/pay")
async def cloudpayments_pay_webhook(
    request: Request,
    database: Session = Depends(get_db),
):
    raw_body = await request.body()

    cloudpayments_webhook_service.verify_signature(
        raw_body=raw_body,
        x_content_hmac=request.headers.get(
            "X-Content-HMAC"
        ),
        content_hmac=request.headers.get(
            "Content-HMAC"
        ),
    )

    payload = (
        cloudpayments_webhook_service.parse_payload(
            raw_body
        )
    )

    cloudpayments_webhook_service.handle_pay(
        database=database,
        payload=payload,
    )

    return {
        "code": 0,
    }


@router.post(
    "/robokassa",
    response_class=PlainTextResponse,
)
async def robokassa_webhook(
    request: Request,
    database: Session = Depends(get_db),
):
    raw_body = await request.body()

    payload = robokassa_webhook_service.parse_payload(
        raw_body
    )

    robokassa_webhook_service.verify_signature(
        payload
    )

    payment = robokassa_webhook_service.handle_result(
        database=database,
        payload=payload,
    )

    return PlainTextResponse(
        content=f"OK{payload['InvId']}",
    )
