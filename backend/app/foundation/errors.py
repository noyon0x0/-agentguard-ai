"""Stable, non-sensitive API errors."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from .telegram import send_telegram


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {"field": ".".join(str(part) for part in issue["loc"]), "message": issue["msg"]}
            for issue in exc.errors()
        ]
        return JSONResponse(status_code=422, content={"error": {"code": "VALIDATION_ERROR", "details": errors}})

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
        # Details belong in internal diagnostics, never in client responses.
        settings = getattr(request.app.state, "settings", None)
        if settings is not None:
            send_telegram(settings, "BACKEND_FAILURE", f"request {getattr(request.state, 'request_id', 'unknown')} failed")
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred"}},
        )

    @app.exception_handler(HTTPException)
    async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail
        code = detail.get("code", "HTTP_ERROR") if isinstance(detail, dict) else "HTTP_ERROR"
        message = detail.get("message") if isinstance(detail, dict) else str(detail)
        body = {"error": {"code": code}}
        if message:
            body["error"]["message"] = message
        return JSONResponse(status_code=exc.status_code, content=body, headers=exc.headers)

    @app.exception_handler(SQLAlchemyError)
    async def database_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={"error": {"code": "SECURITY_CHECK_UNAVAILABLE", "message": "Security storage is unavailable"}},
        )
