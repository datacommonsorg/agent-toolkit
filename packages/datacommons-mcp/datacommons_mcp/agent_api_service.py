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
Service layer for calling Agent APIs.
"""

from typing import Any

from datacommons_mcp.agent_api_client import AgentAPIClient
from datacommons_mcp.app import app


def _get_agent_api_client() -> AgentAPIClient:
    """Helper to get the initialized AgentAPIClient, raising RuntimeError if not set."""
    if app.agent_api_client is None:
        raise RuntimeError(
            "Agent API client is not initialized. Ensure DC_USE_AGENT_API is enabled."
        )
    return app.agent_api_client


async def get_observations(
    variable_dcid: str,
    place_dcid: str,
    child_place_type: str | None = None,
    source_override: str | None = None,
    date: str | None = None,
    date_range_start: str | None = None,
    date_range_end: str | None = None,
) -> dict[str, Any]:
    """Fetches observations via the Agent API agent/get_observations endpoint."""
    client = _get_agent_api_client()
    payload = {
        "variable_dcid": variable_dcid,
        "place_dcid": place_dcid,
        "child_place_type": child_place_type,
        "source_override": source_override,
        "date": date,
        "date_range_start": date_range_start,
        "date_range_end": date_range_end,
    }
    return await client.post("agent/get_observations", payload)


async def search_indicators(
    query: str,
    places: list[str] | None = None,
    parent_place: str | None = None,
    per_search_limit: int = 10,
    *,
    include_topics: bool = True,
) -> dict[str, Any]:
    """Searches for indicators via the Agent API agent/search_indicators endpoint."""
    client = _get_agent_api_client()
    payload = {
        "query": query,
        "places": places or [],
        "parent_place": parent_place,
        "per_search_limit": per_search_limit,
        "include_topics": include_topics,
    }
    return await client.post("agent/search_indicators", payload)


async def get_variable_metadata(
    variable_dcids: list[str],
    entity_dcids: list[str],
) -> dict[str, Any]:
    """Retrieves rich structural metadata (definitions, coverage, and provenances) for variables."""
    client = _get_agent_api_client()
    payload = {
        "variable_dcids": variable_dcids,
        "entity_dcids": entity_dcids,
    }
    return await client.post("agent/get_variable_metadata", payload)
