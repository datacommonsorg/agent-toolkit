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
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.server.providers.skills import SkillsDirectoryProvider
from starlette.requests import Request
from starlette.responses import JSONResponse

import datacommons_mcp.tools as tools
from datacommons_mcp.app import DCApp, app
from datacommons_mcp.version import __version__

# Configure logging
logger = logging.getLogger(__name__)


# Expose the FastMCP instance for the CLI
mcp = app.mcp


# Health check endpoint
@mcp.custom_route("/mcp/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:  # noqa: ARG001 request param required for decorator
    return JSONResponse({"status": "OK", "version": __version__})


# Register tools
app.register_tool(
    tools.search_indicators,
    tools.SEARCH_INDICATORS_INSTRUCTION_FILE,
)
app.register_tool(
    tools.search_child_indicators,
    tools.SEARCH_CHILD_INDICATORS_INSTRUCTION_FILE,
)
app.register_tool(
    tools.get_variable_metadata,
    tools.GET_VARIABLE_METADATA_INSTRUCTION_FILE,
)
app.register_tool(
    tools.get_observations,
    tools.GET_OBSERVATIONS_INSTRUCTION_FILE,
)
app.register_tool(
    tools.get_child_observations,
    tools.GET_CHILD_OBSERVATIONS_INSTRUCTION_FILE,
)
app.register_tool(
    tools.get_multi_entity_observations,
    tools.GET_MULTI_ENTITY_OBSERVATIONS_INSTRUCTION_FILE,
)


def _register_skills(mcp_server: FastMCP, app_instance: DCApp) -> None:
    """Configures and registers the native FastMCP SkillsDirectoryProvider."""
    skills_roots = []
    if app_instance.settings.instructions_dir:
        if app_instance.settings.instructions_dir.startswith("gs://"):
            logger.warning(
                "GCS paths are not supported for loading custom skills: %s. Skipping.",
                app_instance.settings.instructions_dir,
            )
        else:
            custom_skills = Path(app_instance.settings.instructions_dir) / "skills"
            if custom_skills.exists():
                skills_roots.append(custom_skills)

    default_skills = Path(__file__).parent / "instructions" / "skills"
    if default_skills.exists():
        skills_roots.append(default_skills)

    if skills_roots:
        mcp_server.add_provider(SkillsDirectoryProvider(roots=skills_roots))


# Call provider registration on startup
_register_skills(mcp, app)
