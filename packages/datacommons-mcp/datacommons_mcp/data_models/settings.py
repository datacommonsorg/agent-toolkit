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
Pydantic settings for configuring the Data Commons MCP server.
"""

from pydantic import Field
from pydantic_settings import BaseSettings

from .enums import SearchScope


class DCSettings(BaseSettings):
    """Pydantic settings for configuring the Data Commons MCP server."""

    model_config = {"env_file": ".env", "extra": "ignore"}

    api_key: str = Field(
        default="",
        alias="DC_API_KEY",
        description="API key for Data Commons",
    )
    agent_api_root: str = Field(
        default="https://api.datacommons.org/v2",
        alias="DC_AGENT_API_ROOT",
        description="API root URL for Data Commons Agent API endpoints",
    )
    search_scope: SearchScope | None = Field(
        default=None,
        alias="DC_SEARCH_SCOPE",
        description="Search scope for queries (e.g., 'custom_only', 'base_and_custom')",
    )
    instructions_dir: str | None = Field(
        default=None,
        alias="DC_INSTRUCTIONS_DIR",
        description="Directory containing custom instruction files (markdown overrides)",
    )
