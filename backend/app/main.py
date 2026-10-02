from fastapi import FastAPI, HTTPException
from app.api.referrals import router as referrals_router
from sqlalchemy import text

from app.api.activation_page import router as activation_page_router
from app.api.happ_mobile_readiness import (
    router as happ_mobile_readiness_router,
)
from app.api.happ_connect import router as happ_connect_router
from app.api.happ_auto_route import router as happ_auto_route_router
from app.api.mini_app import router as mini_app_router
from app.api.catalog import router as catalog_router
from app.api.device_activations import router as device_activations_router
from app.api.devices import router as devices_router
from app.api.test_payments import router as test_payments_router
from app.api.payment_webhooks import router as payment_webhooks_router
from app.api.payments import router as payments_router
from app.api.payment_redirects import router as payment_redirects_router
from app.api.subscription_feed import router as subscription_feed_router
from app.api.subscription_tokens import router as subscription_tokens_router
from app.api.subscriptions import router as subscriptions_router
from app.api.users import router as users_router
from app.db.session import engine



app = FastAPI(
    title="Work&PlayVPN API",
    version="0.1.0",
)

app.include_router(referrals_router)
app.include_router(catalog_router)
app.include_router(users_router)
app.include_router(subscriptions_router)
app.include_router(happ_mobile_readiness_router)
app.include_router(happ_connect_router)
app.include_router(mini_app_router)
app.include_router(devices_router)
app.include_router(device_activations_router)
app.include_router(test_payments_router)
app.include_router(activation_page_router)
app.include_router(subscription_tokens_router)
app.include_router(subscription_feed_router)
app.include_router(happ_auto_route_router)
app.include_router(payments_router)
app.include_router(payment_redirects_router)
app.include_router(payment_webhooks_router)


@app.get("/")
async def root():
    return {
        "project": "Work&PlayVPN",
        "status": "online",
        "version": "0.1.0",
    }


@app.get("/health")
def health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable",
        ) from exc

    return {
        "status": "healthy",
        "database": "connected",
    }
