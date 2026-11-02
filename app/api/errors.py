import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.schemas import ErrorResponse
from app.domain.errors import AppError

logger = logging.getLogger(__name__)


def exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    def _app_error(request: Request, exc: AppError) -> JSONResponse:
        error = ErrorResponse(
            code=exc.code.value,
            message=exc.message,
            request_id=getattr(request.state, "request_id", None),
        )
        return JSONResponse(status_code=exc.http_status, content=error.model_dump())

    @app.exception_handler(RequestValidationError)
    def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        error = ErrorResponse(
            code="invalid_args",
            message="Invalid request body or parameters.",
            request_id=getattr(request.state, "request_id", None),
        )
        return JSONResponse(status_code=422, content=error.model_dump())

    @app.exception_handler(Exception)
    def _unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Request failed unexpectedly", exc_info=exc)
        request_id = getattr(request.state, "request_id", None)
        error = ErrorResponse(
            code="internal_error", message="An unexpected error occurred.", request_id=request_id
        )
        return JSONResponse(
            status_code=500,
            content=error.model_dump(),
            headers={"X-Request-ID": request_id} if request_id else {},
        )
