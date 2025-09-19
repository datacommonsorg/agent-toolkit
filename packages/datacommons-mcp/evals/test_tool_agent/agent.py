"""
Agent implementation for interacting with Data Commons using a LLM model.

This module contains the main agent implementation that uses a LLM model to fetch
and respond to queries. It uses MCP tools to interact with Data Commons.
"""

import os

from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import (
    MCPToolset,
    StdioConnectionParams,
    StdioServerParameters,
)

from .instructions import AGENT_INSTRUCTIONS

# Environment variables for agent configuration
DC_API_KEY = os.environ.get("DC_API_KEY")

if not DC_API_KEY:
    raise ValueError("Required environment variable DC_API_KEY is not set")

# Model for the agent
AGENT_MODEL = "gemini-2.5-flash"

# Initialize the agent
root_agent = LlmAgent(
    model=AGENT_MODEL,
    name="test_tool_agent",
    instruction=AGENT_INSTRUCTIONS,
    tools=[
        MCPToolset(
            connection_params=StdioConnectionParams(
                timeout=10,
                server_params=StdioServerParameters(
                    command="uv",
                    args=["run", "datacommons-mcp", "serve", "stdio"],
                    env={"DC_API_KEY": DC_API_KEY},
                ),
            )
        )
    ],
)
