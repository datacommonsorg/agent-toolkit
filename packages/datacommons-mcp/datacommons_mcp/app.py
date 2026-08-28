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
Core application module for the DC MCP server.
"""

import json
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastmcp import FastMCP
from fastmcp.tools.tool import Tool
from pydantic import ValidationError

from datacommons_mcp.client import AgentAPIClient
from datacommons_mcp.data_models.settings import DCSettings
from datacommons_mcp.utils import read_external_content, read_package_content
from datacommons_mcp.version import __version__

# Configure logging
logger = logging.getLogger(__name__)

MCP_SERVER_NAME = "DC MCP Server"
DEFAULT_INSTRUCTIONS_PACKAGE = "datacommons_mcp.instructions"
SERVER_INSTRUCTIONS_FILE = "server.md"


class DCApp:
    """Core application wrapper for Data Commons MCP."""

    def __init__(self) -> None:
        """Initialize the application."""
        # Load settings
        try:
            self.settings = DCSettings()
            settings_dict = self.settings.model_dump(mode="json")
            settings_dict["api_key"] = (
                "<SET>" if settings_dict.get("api_key") else "<NOT_SET>"
            )
            logger.info("Loaded DC settings:\n%s", json.dumps(settings_dict, indent=2))
        except ValidationError as e:
            logger.error("Settings error: %s", e)
            raise

        # Create Agent API client
        search_scope = self.settings.search_scope
        search_scope_str = (
            search_scope.value if hasattr(search_scope, "value") else search_scope
        )
        self.client = AgentAPIClient(
            api_root=self.settings.agent_api_root,
            api_key=self.settings.api_key,
            search_scope=search_scope_str,
        )

        # Load Server Instructions
        server_instructions = self._load_instructions(SERVER_INSTRUCTIONS_FILE)

        @asynccontextmanager
        async def lifespan(_server: FastMCP) -> AsyncIterator[dict[str, Any]]:
            yield {}
            if self.client:
                logger.info("Closing Data Commons client...")
                await self.client.close()

        self.mcp = FastMCP(
            MCP_SERVER_NAME,
            version=__version__,
            instructions=server_instructions,
            lifespan=lifespan,
        )

    def _load_instructions(self, filename: str) -> str:
        """Loads markdown content relative to the instructions directory.

        Priority:
        1. DC_INSTRUCTIONS_DIR/{filename} (if set and exists)
        2. Package default: datacommons_mcp/instructions/{filename}
        """
        # Check specific override
        if self.settings.instructions_dir:
            content = read_external_content(self.settings.instructions_dir, filename)
            if content is not None:
                logger.info(
                    "Loaded custom instructions for %s from %s",
                    filename,
                    self.settings.instructions_dir,
                )
                return content
            logger.debug(
                "Custom instructions file %s not found in %s, falling back to default.",
                filename,
                self.settings.instructions_dir,
            )

        # Fallback to package resources
        return read_package_content(DEFAULT_INSTRUCTIONS_PACKAGE, filename)

    def register_tool(self, func: Callable[..., Any], instruction_file: str) -> None:
        """Register a tool with instructions loaded from a file.

        Args:
            func: The tool function to register.
            instruction_file: Path to instructions file relative to instructions dir.
        """
        description = self._load_instructions(instruction_file)
        if not description:
            logger.warning(
                "No description found for tool %s from file %s",
                func.__name__,
                instruction_file,
            )

        # Create tool from function and add description
        tool = Tool.from_function(func, description=description)
        self.mcp.add_tool(tool)


# Create global app instance
app = DCApp()
