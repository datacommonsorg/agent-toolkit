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

import logging
from collections.abc import Callable
from typing import Any

from fastmcp import FastMCP
from fastmcp.tools.tool import Tool
from pydantic import ValidationError

from datacommons_mcp import settings
from datacommons_mcp.clients import create_dc_client
from datacommons_mcp.utils import read_external_content, read_package_content
from datacommons_mcp.version import __version__

# Configure logging
logger = logging.getLogger(__name__)

MCP_SERVER_NAME = "DC MCP Server"
DEFAULT_INSTRUCTIONS_PACKAGE = "datacommons_mcp.instructions"
SERVER_INSTRUCTION_FILE = "server.md"


class DCApp:
    """Core application wrapper for Data Commons MCP."""

    def __init__(self) -> None:
        """Initialize the application."""
        # Load settings
        try:
            self.settings = settings.get_dc_settings()
            logger.info(
                "Loaded DC settings:\n%s", self.settings.model_dump_json(indent=2)
            )
        except ValidationError as e:
            logger.error("Settings error: %s", e)
            raise

        # Create client
        try:
            self.client = create_dc_client(self.settings)
        except Exception as e:
            logger.error("Failed to create DC client: %s", e)
            raise

        # Load Server Instructions
        server_instructions = self._load_instruction(SERVER_INSTRUCTION_FILE)

        self.mcp = FastMCP(
            MCP_SERVER_NAME,
            version=__version__,
            instructions=server_instructions,
        )

    def _load_instruction(self, filename: str) -> str:
        """
        Loads markdown content.
        Priority:
        1. DC_INSTRUCTIONS_DIR/{filename} (if set and exists)
        2. Package default: datacommons_mcp/instructions/{filename}
        """
        # Check specific override
        if self.settings.instructions_dir:
            content = read_external_content(self.settings.instructions_dir, filename)
            if content is not None:
                logger.info(
                    "Loaded custom instruction for %s from %s",
                    filename,
                    self.settings.instructions_dir,
                )
                return content
            logger.debug(
                "Custom instruction file %s not found in %s, falling back to default.",
                filename,
                self.settings.instructions_dir,
            )

        # Fallback to package resources
        return read_package_content(DEFAULT_INSTRUCTIONS_PACKAGE, filename)

    def register_tool(self, func: Callable[..., Any], instruction_file: str) -> None:
        """Register a tool with instructions loaded from a file.

        Args:
            func: The tool function to register.
            instruction_file: Path to instruction file relative to instructions dir.
        """
        description = self._load_instruction(instruction_file)
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
