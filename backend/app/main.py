from fastapi import FastAPI

app = FastAPI(
    title="Work&PlayVPN API",
    version="0.1.0",
)

@app.get("/")
async def root():
    return {
        "project": "Work&PlayVPN",
        "status": "online",
        "version": "0.1.0",
    }