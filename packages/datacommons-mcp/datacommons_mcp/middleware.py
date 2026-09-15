import logging
from collections.abc import Awaitable, Callable
from typing import Any

from fastmcp.server.dependencies import get_http_headers
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from mcp import McpError
from mcp.types import INVALID_PARAMS, ErrorData
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from datacommons_mcp.client import use_api_key

logger = logging.getLogger(__name__)

DOCUMENTATION_HEADER = "X-DC-Enable-Documentation"


class DocumentationMiddleware(Middleware):
    """Enable documentation guidance only when the HTTP client opts in."""

    def __init__(
        self, *, base_instructions: str, documentation_instructions: str
    ) -> None:
        self._base_instructions = base_instructions
        self._documentation_instructions = documentation_instructions

    def _enabled(self) -> bool:
        value = get_http_headers().get(DOCUMENTATION_HEADER.lower())
        if value is None:
            return False
        value = value.strip().lower()
        if value not in ("true", "false"):
            raise McpError(
                ErrorData(
                    code=INVALID_PARAMS,
                    message=f"{DOCUMENTATION_HEADER} must be true or false",
                )
            )
        return value == "true"

    async def on_request(self, context: MiddlewareContext, call_next: CallNext) -> Any:  # noqa: ANN401
        self._enabled()  # Validate the preference on every request.
        return await call_next(context)

    async def on_initialize(
        self, context: MiddlewareContext, call_next: CallNext
    ) -> Any:  # noqa: ANN401
        instructions = (
            self._documentation_instructions
            if self._enabled()
            else self._base_instructions
        )
        session = context.fastmcp_context.session
        # FastMCP 3.4.2 sends initialization before middleware returns. Copy the
        # session options before dispatch; never mutate the shared options.
        session._init_options = session._init_options.model_copy(
            update={"instructions": instructions}
        )
        return await call_next(context)


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Middleware to extract X-API-Key header and set it as the override API key
    for the Data Commons client context.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        api_key = request.headers.get("X-API-Key")
        if api_key:
            logger.debug("Received X-API-Key header, applying override.")
            try:
                with use_api_key(api_key):
                    return await call_next(request)
            except Exception as e:
                # We log and re-raise to ensure we don't swallow application errors,
                # but we want to know if the context manager itself failed.
                logger.error("Error during API key override context propagation: %s", e)
                raise
        else:
            return await call_next(request)
