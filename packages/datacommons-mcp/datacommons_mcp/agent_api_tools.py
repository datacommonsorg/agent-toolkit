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
Tool implementations for the Agent API-based Data Commons MCP server.
"""

from typing import Any

from datacommons_mcp.agent_api_service import (
    get_observations as agent_api_get_observations,
)
from datacommons_mcp.agent_api_service import (
    get_variable_metadata as agent_api_get_variable_metadata,
)
from datacommons_mcp.agent_api_service import (
    search_indicators as agent_api_search_indicators,
)
from datacommons_mcp.data_models.observations import ObservationDateType

# Instruction file constants
SEARCH_INDICATORS_INSTRUCTION_FILE = "tools/search_indicators.md"
SEARCH_CHILD_INDICATORS_INSTRUCTION_FILE = "tools/search_child_indicators.md"
GET_VARIABLE_METADATA_INSTRUCTION_FILE = "tools/get_variable_metadata.md"
GET_OBSERVATIONS_INSTRUCTION_FILE = "tools/get_observations.md"
GET_CHILD_OBSERVATIONS_INSTRUCTION_FILE = "tools/get_child_observations.md"


async def search_indicators(
    query: str,
    places: list[str] | None = None,
    per_search_limit: int = 10,
    *,
    include_topics: bool = True,
) -> dict[str, Any]:
    """Searches for statistical indicators matching a natural language query."""
    return await agent_api_search_indicators(
        query=query,
        places=places,
        parent_place=None,
        per_search_limit=per_search_limit,
        include_topics=include_topics,
    )


async def search_child_indicators(
    query: str,
    parent_place: str,
    sample_child_places: list[str],
    per_search_limit: int = 10,
    *,
    include_topics: bool = True,
) -> dict[str, Any]:
    """Searches for statistical indicators available at the child-place level."""
    return await agent_api_search_indicators(
        query=query,
        places=sample_child_places,
        parent_place=parent_place,
        per_search_limit=per_search_limit,
        include_topics=include_topics,
    )


async def get_variable_metadata(
    variable_dcids: list[str],
    entity_dcids: list[str],
) -> dict[str, Any]:
    """Retrieves definitions, coverage, and provenances for a list of variables."""
    return await agent_api_get_variable_metadata(
        variable_dcids=variable_dcids,
        entity_dcids=entity_dcids,
    )


async def get_observations(
    variable_dcid: str,
    place_dcid: str,
    source_override: str | None = None,
    date: str = ObservationDateType.LATEST.value,
    date_range_start: str | None = None,
    date_range_end: str | None = None,
) -> dict[str, Any]:
    """Fetches time-series observations for a statistical variable at a specific place."""
    return await agent_api_get_observations(
        variable_dcid=variable_dcid,
        place_dcid=place_dcid,
        child_place_type=None,
        source_override=source_override,
        date=date,
        date_range_start=date_range_start,
        date_range_end=date_range_end,
    )


async def get_child_observations(
    variable_dcid: str,
    parent_place_dcid: str,
    child_place_type: str,
    source_override: str | None = None,
    date: str = ObservationDateType.LATEST.value,
    date_range_start: str | None = None,
    date_range_end: str | None = None,
) -> dict[str, Any]:
    """Fetches time-series observations for a statistical variable across child places."""
    return await agent_api_get_observations(
        variable_dcid=variable_dcid,
        place_dcid=parent_place_dcid,
        child_place_type=child_place_type,
        source_override=source_override,
        date=date,
        date_range_start=date_range_start,
        date_range_end=date_range_end,
    )
