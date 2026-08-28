# Copyright 2025 Google LLC.
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
Exceptions for Data Commons MCP server.
"""


class _ErrorStrMixin:
    """A mixin to provide a descriptive __str__ representation for exceptions."""

    def __str__(self) -> str:
        """Returns a string representation of the exception."""
        message = self.args[0] if self.args else ""
        return f"{self.__class__.__name__}: {message}"


class APIKeyValidationError(_ErrorStrMixin, Exception):
    """Base class for API key validation errors."""


class InvalidAPIKeyError(APIKeyValidationError):
    """Raised when the API key is determined to be invalid."""


class AgentAPIError(Exception):
    """Raised when the Data Commons Agent API returns an error."""

    def __init__(self, message: str, status_code: int, body: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body

    def __str__(self) -> str:
        base = super().__str__()
        if self.body:
            truncated_body = (
                self.body
                if len(self.body) <= 500
                else f"{self.body[:500]}... [truncated]"
            )
            return f"{base} - Body: {truncated_body}"
        return base
