from fastapi import APIRouter, HTTPException, Request, status


router = APIRouter(
    prefix="/webhooks",
    tags=["payment-webhooks"],
)


@router.post("/cloudpayments")
async def cloudpayments_webhook(
    request: Request,
):
    # ВАЖНО:
    # Пока не реализована проверка подписи CloudPayments,
    # webhook не имеет права менять состояние платежей.
    #
    # Позже здесь будет:
    # 1. чтение raw body;
    # 2. проверка подписи;
    # 3. проверка статуса платежа;
    # 4. поиск нашего Payment;
    # 5. payment_service.mark_succeeded(...).

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="CloudPayments webhook is not configured",
    )


@router.post("/robokassa")
async def robokassa_webhook(
    request: Request,
):
    # ВАЖНО:
    # Пока не реализована проверка подписи Robokassa,
    # webhook не имеет права менять состояние платежей.
    #
    # Позже здесь будет:
    # 1. получение параметров callback;
    # 2. проверка SignatureValue;
    # 3. поиск нашего Payment;
    # 4. payment_service.mark_succeeded(...);
    # 5. корректный ответ Robokassa.

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Robokassa webhook is not configured",
    )