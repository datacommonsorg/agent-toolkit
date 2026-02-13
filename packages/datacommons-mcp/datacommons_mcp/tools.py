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
Tool implementations for the Data Commons MCP server.
"""

from typing import TYPE_CHECKING

from datacommons_mcp.app import app
from datacommons_mcp.data_models.observations import (
    ObservationDateType,
    ObservationToolResponse,
)
from datacommons_mcp.services import (
    get_observations as get_observations_service,
)
from datacommons_mcp.services import (
    search_indicators as search_indicators_service,
)

if TYPE_CHECKING:
    from datacommons_mcp.data_models.search import (
        SearchResponse,
    )


async def get_observations(
    variable_dcid: str,
    place_dcid: str,
    child_place_type: str | None = None,
    source_override: str | None = None,
    date: str = ObservationDateType.LATEST.value,
    date_range_start: str | None = None,
    date_range_end: str | None = None,
) -> dict:
    """Fetches observations for a statistical variable from Data Commons."""
    response: ObservationToolResponse = await get_observations_service(
        client=app.client,
        variable_dcid=variable_dcid,
        place_dcid=place_dcid,
        place_name=None,
        child_place_type=child_place_type,
        source_override=source_override,
        date=date,
        date_range_start=date_range_start,
        date_range_end=date_range_end,
    )
    return response.model_dump(exclude_none=True)


async def search_indicators(
    query: str,
    places: list[str] | None = None,
    parent_place: str | None = None,
    per_search_limit: int = 10,
    *,
    include_topics: bool = True,
    maybe_bilateral: bool = False,
) -> dict:
    """Searches for indicators (topics and variables) in Data Commons."""
    response: SearchResponse = await search_indicators_service(
        client=app.client,
        query=query,
        places=places,
        parent_place=parent_place,
        per_search_limit=per_search_limit,
        include_topics=include_topics,
        maybe_bilateral=maybe_bilateral,
    )
    return response.model_dump(exclude_none=True)
