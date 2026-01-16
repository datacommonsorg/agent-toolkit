import logging
from collections.abc import Awaitable, Callable

from datacommons_client import use_api_key
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class APIKeyMiddleware(BaseHTTPMiddleware):
    """
    Middleware to extract X-API-Key header and set it as the override API key
    for the Data Commons client context.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        api_key = request.headers.get("X-API-Key")
        if api_key:
            print("[DEBUG] Received X-API-Key header: ", api_key)
            try:
                with use_api_key(api_key):
                    return await call_next(request)
            except Exception as e:
                # We log and re-raise to ensure we don't swallow application errors,
                # but we want to know if the context manager itself failed.
                print("[DEBUG] Error during API key override context propagation: ", e)
                raise
        else:
            print(
                "[DEBUG] No X-API-Key header received, proceeding without override: ",
                request.headers,
            )
            return await call_next(request)
