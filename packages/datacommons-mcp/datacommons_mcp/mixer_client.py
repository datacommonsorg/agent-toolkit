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
Client for interacting with the Data Commons Mixer service.
"""

import httpx

from datacommons_mcp.version import __version__


class MixerClient:
    """Async client for interacting with Mixer-side agent endpoints."""

    def __init__(self, api_root: str, api_key: str | None = None) -> None:
        """Initialize the MixerClient.

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

    async def post(self, endpoint: str, payload: dict) -> dict:
        """Perform an asynchronous POST request to the specified endpoint.

        Args:
            endpoint: The API endpoint (e.g. 'agent/get_observations').
            payload: The dictionary to send as JSON payload.

        Returns:
            The parsed JSON response as a dictionary.
        """
        url = f"{self.api_root}/{endpoint}"
        response = await self.client.post(url, json=payload)
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        """Close the underlying HTTP client if it was initialized."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
