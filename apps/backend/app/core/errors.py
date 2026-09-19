"""Domain exceptions and FastAPI exception handlers."""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

log = get_logger("errors")


class QLootError(Exception):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "bad_request"

    def __init__(self, message: str = "Bad request", *, detail: object | None = None):
        super().__init__(message)
        self.message = message
        self.detail = detail


class NotFoundError(QLootError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class ConflictError(QLootError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"


class ValidationError(QLootError):
    status_code = 422
    code = "validation_error"


class AuthError(QLootError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthenticated"


class ForbiddenError(QLootError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "forbidden"


class RateLimitedError(QLootError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "rate_limited"


class ChainError(QLootError):
    status_code = status.HTTP_502_BAD_GATEWAY
    code = "chain_error"


class AIProviderError(QLootError):
    status_code = status.HTTP_502_BAD_GATEWAY
    code = "ai_provider_error"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(QLootError)
    async def _qlooot_handler(_: Request, exc: QLootError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message, "detail": exc.detail}},
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Request validation failed",
                    "detail": exc.errors(),
                }
            },
        )

    @app.exception_handler(Exception)
    async def _unhandled_handler(_: Request, exc: Exception) -> JSONResponse:
        log.error("unhandled_exception", error=str(exc), exc_type=type(exc).__name__)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {"code": "internal_error", "message": "An unexpected error occurred"}
            },
        )
