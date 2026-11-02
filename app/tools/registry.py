import logging
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ValidationError

from app.domain.enums import ToolErrorCode
from app.domain.errors import AppError
from app.llm.types import ToolSpec
from app.tools.context import ToolContext
from app.tools.types import ToolResult

logger = logging.getLogger(__name__)
Handler = Callable[[Any, ToolContext], ToolResult]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, tuple[ToolSpec, type[BaseModel], Handler]] = {}

    def register(self, spec: ToolSpec, args_model: type[BaseModel], handler: Handler) -> None:
        if spec.name in self._tools:
            raise ValueError(f"Duplicate tool: {spec.name}")
        self._tools[spec.name] = (spec, args_model, handler)

    def specs(self) -> list[ToolSpec]:
        return [entry[0] for entry in self._tools.values()]

    def execute(self, name: str, arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
        entry = self._tools.get(name)
        if entry is None:
            return ToolResult(
                ok=False, error_code=ToolErrorCode.unknown_tool, message="Unknown tool"
            )
        _, model, handler = entry
        try:
            args = model.model_validate(arguments)
        except ValidationError as exc:
            details = "; ".join(
                f"{'.'.join(map(str, e['loc'])) or 'arguments'}: {e['msg']}"
                for e in exc.errors(include_input=False)
            )
            return ToolResult(ok=False, error_code=ToolErrorCode.invalid_args, message=details)
        try:
            return handler(args, ctx)
        except AppError as exc:
            return ToolResult(ok=False, error_code=exc.code, message=exc.message)
        except Exception:
            logger.exception("Tool failed unexpectedly")
            return ToolResult(
                ok=False,
                error_code=ToolErrorCode.internal_error,
                message="Tool failed unexpectedly.",
            )
