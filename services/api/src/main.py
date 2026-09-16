from fastapi import FastAPI

from src.api.artifacts import router as artifacts_router
from src.core.errors import register_error_handlers

app = FastAPI(title="HTML Office API", version="0.1.0")
register_error_handlers(app)
app.include_router(artifacts_router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
