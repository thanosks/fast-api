from fastapi import FastAPI
from app.core.config import settings
from app.routers import folders

app = FastAPI()
app.include_router(folders.router)


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.app_name}
