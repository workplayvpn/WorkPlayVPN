from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from app.api.users import router as users_router
from app.api.catalog import router as catalog_router
from app.api.subscriptions import router as subscriptions_router

from app.db.session import engine


app = FastAPI(
    title="Work&PlayVPN API",
    version="0.1.0",
)

app.include_router(catalog_router)
app.include_router(users_router)
app.include_router(catalog_router)
app.include_router(subscriptions_router)
app.include_router(users_router)


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