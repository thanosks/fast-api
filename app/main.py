from fastapi import FastAPI
from app.core.config import Settings

app = FastAPI()
settings = Settings()


@app.get("/health")
def health():

    return {"status": "ok", "app": settings.app_name}
