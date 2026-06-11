# Copyright 2026 Google LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Client for interacting with the Data Commons Agent API.
"""

import logging
import time
from collections.abc import Callable
from functools import wraps
from typing import Any  # noqa: ANN401

import httpx

from datacommons_mcp.exceptions import AgentAPIError
from datacommons_mcp.version import __version__

logger = logging.getLogger(__name__)


def log_api_call(func: Callable[..., Any]) -> Callable[..., Any]:  # noqa: ANN401
    """Decorator to log URL, request payload, execution time, and errors for Agent API calls."""

    @wraps(func)
    async def wrapper(
        self: "AgentAPIClient",
        endpoint: str,
        payload: dict,
        *args: object,
        **kwargs: object,
    ) -> Any:  # noqa: ANN401
        url = f"{self.api_root}/{endpoint}"
        logger.info("AgentAPIClient POST request URL: %s, payload: %s", url, payload)
        start_time = time.perf_counter()
        try:
            result = await func(self, endpoint, payload, *args, **kwargs)
            elapsed_time = time.perf_counter() - start_time
            logger.info(
                "AgentAPIClient POST request to %s completed in %.3f seconds",
                url,
                elapsed_time,
            )
            return result
        except Exception as e:
            elapsed_time = time.perf_counter() - start_time
            logger.error(
                "AgentAPIClient POST request to %s failed after %.3f seconds with error: %s",
                url,
                elapsed_time,
                e,
            )
            raise

    return wrapper


class AgentAPIClient:
    """Async client for interacting with Data Commons agent endpoints."""

    def __init__(self, api_root: str, api_key: str | None = None) -> None:
        """Initialize the AgentAPIClient.

        Args:
            api_root: The base API root URL (e.g. 'https://api.datacommons.org/v2').
            api_key: Optional API key for authentication.
        """
        self.api_root = api_root.rstrip("/")
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json",
            "x-surface": f"mcp-{__version__}",
        }
        if api_key:
            self.headers["X-API-Key"] = api_key
        self.timeout = 30.0  # 30 seconds default timeout
        self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Lazily initialize the AsyncClient under the active event loop."""
        if self._client is None:
            self._client = httpx.AsyncClient(headers=self.headers, timeout=self.timeout)
        return self._client

    @log_api_call
    async def post(self, endpoint: str, payload: dict) -> dict:
        """Perform an asynchronous POST request to the specified endpoint.

        Args:
            endpoint: The API endpoint (e.g. 'agent/get_observations').
            payload: The dictionary to send as JSON payload.

        Returns:
            The parsed JSON response as a dictionary.
        """
        url = f"{self.api_root}/{endpoint}"
        try:
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            error_msg = f"Agent API call to {endpoint} failed with status {e.response.status_code}"
            raise AgentAPIError(
                error_msg, e.response.status_code, e.response.text
            ) from e

    async def close(self) -> None:
        """Close the underlying HTTP client if it was initialized."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
