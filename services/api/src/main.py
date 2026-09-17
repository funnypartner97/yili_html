from fastapi import FastAPI

from src.api.artifacts import router as artifacts_router
from src.api.commands import router as commands_router
from src.api.documents import router as documents_router
from src.api.exports import router as exports_router
from src.api.files import router as files_router
from src.api.jobs import router as jobs_router
from src.api.plans import router as plans_router
from src.core.errors import register_error_handlers
from src.files.limits import UploadBodyLimitMiddleware

app = FastAPI(title="HTML Office API", version="0.1.0")
app.add_middleware(UploadBodyLimitMiddleware)
register_error_handlers(app)
app.include_router(artifacts_router)
app.include_router(files_router)
app.include_router(plans_router)
app.include_router(jobs_router)
app.include_router(documents_router)
app.include_router(commands_router)
app.include_router(exports_router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
