from app.domain.enums import ToolErrorCode


class AppError(Exception):
    code: ToolErrorCode = ToolErrorCode.internal_error
    http_status: int = 500

    def __init__(
        self,
        message: str,
        *,
        code: ToolErrorCode | None = None,
        http_status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if http_status is not None:
            self.http_status = http_status


class NotFoundError(AppError):
    code = ToolErrorCode.not_found
    http_status = 404


class OutOfStockError(AppError):
    code = ToolErrorCode.out_of_stock
    http_status = 409


class InvalidStateError(AppError):
    code = ToolErrorCode.invalid_state
    http_status = 409


class CartChangedError(AppError):
    code = ToolErrorCode.cart_changed
    http_status = 409


class TokenMismatchError(AppError):
    code = ToolErrorCode.token_mismatch
    http_status = 409


class ConflictError(AppError):
    code = ToolErrorCode.conflict
    http_status = 409


class ValidationAppError(AppError):
    code = ToolErrorCode.invalid_args
    http_status = 422


class ProviderError(AppError):
    code = ToolErrorCode.provider_error
    http_status = 502


class AllProvidersFailedError(AppError):
    code = ToolErrorCode.provider_error
    http_status = 503


class AgentLoopLimitError(AppError):
    code = ToolErrorCode.internal_error
    http_status = 500
