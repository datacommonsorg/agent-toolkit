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
Server module for the DC MCP server.
"""

import logging

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

import datacommons_mcp.settings as settings
import datacommons_mcp.tools as tools
from datacommons_mcp.app import app
from datacommons_mcp.version import __version__

# Configure logging
logger = logging.getLogger(__name__)


# Expose the FastMCP instance for the CLI
mcp = app.mcp


@mcp.custom_route("/mcp/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:  # noqa: ARG001 request param required for decorator
    return JSONResponse({"status": "OK", "version": __version__})


# Register tools
app.register_tool(tools.get_observations, "tools/get_observations.md")
app.register_tool(tools.search_indicators, "tools/search_indicators.md")
