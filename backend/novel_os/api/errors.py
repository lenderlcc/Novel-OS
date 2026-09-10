import logging
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from novel_os.api.schemas import ErrorBody, ErrorDetail, ErrorResponse
from novel_os.domain.errors import DatabaseUnavailableError

logger = logging.getLogger(__name__)


def error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: list[ErrorDetail] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    request_id = request.state.request_id
    body = ErrorResponse(
        error=ErrorBody(code=code, message=message, request_id=request_id, details=details or [])
    )
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(),
        headers={**(headers or {}), "X-Request-ID": request_id},
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DatabaseUnavailableError)
    async def database_unavailable(request: Request, exc: DatabaseUnavailableError) -> JSONResponse:
        logger.warning("database_unavailable", extra={"error_type": type(exc.__cause__).__name__})
        return error_response(request, 503, "DATABASE_UNAVAILABLE", "Database is unavailable")

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Do not echo input values, validator context, or exception messages.
        details = [
            ErrorDetail(location=list(error["loc"]), type=error["type"]) for error in exc.errors()
        ]
        return error_response(
            request, 422, "VALIDATION_ERROR", "Request validation failed", details
        )

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}.get(exc.status_code, "HTTP_ERROR")
        message = (
            HTTPStatus(exc.status_code).phrase
            if exc.status_code in HTTPStatus._value2member_map_
            else "HTTP error"
        )
        return error_response(request, exc.status_code, code, message, headers=exc.headers)

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # Starlette's outer error handler runs after the middleware resets ContextVar.
        logger.error(
            "request_failed",
            extra={"request_id": request.state.request_id, "error_type": type(exc).__name__},
        )
        return error_response(request, 500, "INTERNAL_ERROR", "Internal server error")
