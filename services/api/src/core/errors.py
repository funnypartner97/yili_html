from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException


class DomainError(Exception):
    def __init__(self, code: str, message: str, *, status_code: int = 422,
                 details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def domain_error(request: Request, error: DomainError):
        return JSONResponse(status_code=error.status_code, content={
            "code": error.code, "message": error.message, "details": error.details,
        })

    @app.exception_handler(IntegrityError)
    async def integrity_error(request: Request, error: IntegrityError):
        # Never expose SQL, bound values, driver messages, or constraint internals.
        return JSONResponse(status_code=409, content={
            "code": "integrity_conflict", "message": "The change conflicts with stored data.",
            "details": {},
        })

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError):
        return JSONResponse(status_code=422, content={
            "code": "validation_error", "message": "The request is invalid.",
            "details": {"errors": [{"location": list(item["loc"]), "type": item["type"],
                                     "message": item["msg"]} for item in error.errors()]},
        })

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException):
        return JSONResponse(status_code=error.status_code, headers=error.headers, content={
            "code": "not_found" if error.status_code == 404 else "http_error",
            "message": str(error.detail), "details": {},
        })
