"""
Basic Agent implementation for interacting with Data Commons over MCP.
"""

import os

from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import (
    MCPToolset,
    StreamableHTTPConnectionParams
)

from .instructions import AGENT_INSTRUCTIONS

# Environment variables for agent configuration
DC_API_KEY = os.environ.get("DC_API_KEY")

if not DC_API_KEY:
    raise ValueError("Required environment variable DC_API_KEY is not set")

# Model for the agent
AGENT_MODEL = os.environ.get("AGENT_MODEL", "gemini-2.5-flash")

# Initialize the agent
root_agent = LlmAgent(
    model=AGENT_MODEL,
    name="basic_agent",
    instruction=AGENT_INSTRUCTIONS,
    tools=[
        MCPToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=f"https://api.datacommons.org/mcp",
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                    "X-API-Key": DC_API_KEY
                },
            ),
        )
    ],
)
