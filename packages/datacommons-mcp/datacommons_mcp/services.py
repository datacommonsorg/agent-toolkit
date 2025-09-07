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

import asyncio
import logging

from datacommons_mcp.clients import DCClient
from datacommons_mcp.data_models.observations import (
    DateRange,
    ObservationPeriod,
    ObservationToolRequest,
    ObservationToolResponse,
)
from datacommons_mcp.data_models.search import (
    SearchMode,
    SearchModeType,
    SearchResponse,
    SearchResult,
    SearchTask,
    SearchTopic,
    SearchVariable,
)
from datacommons_mcp.exceptions import DataLookupError

logger = logging.getLogger(__name__)


async def _build_observation_request(
    client: DCClient,
    variable_dcid: str,
    place_dcid: str | None = None,
    place_name: str | None = None,
    child_place_type: str | None = None,
    source_id_override: str | None = None,
    period: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> ObservationToolRequest:
    """
    Creates an ObservationRequest from the raw inputs provided by a tool call.
    This method contains the logic to resolve names to DCIDs and structure the data.
    """
    # 0. Perform inital validations
    if not variable_dcid:
        raise ValueError("'variable_dcid' must be specified.")

    if not (place_name or place_dcid):
        raise ValueError("Specify either 'place_name' or 'place_dcid'.")

    if (not period) and (bool(start_date) ^ bool(end_date)):
        raise ValueError(
            "Both 'start_date' and 'end_date' are required to specify a custom date range."
        )

    # 2. Get observation period and date filters
    date_filter = None
    if not (period or (start_date and end_date)):
        observation_period = ObservationPeriod.LATEST
    elif period:
        observation_period = ObservationPeriod(period)
    else:  # A date range is provided
        observation_period = ObservationPeriod.ALL
        date_filter = DateRange(start_date=start_date, end_date=end_date)

    # 3. Resolve place DCID
    if not place_dcid:
        results = await client.search_places([place_name])
        place_dcid = results.get(place_name)
    if not place_dcid:
        raise DataLookupError(f"No place found matching '{place_name}'.")

    # 3. Return an instance of the class
    return ObservationToolRequest(
        variable_dcid=variable_dcid,
        place_dcid=place_dcid,
        child_place_type=child_place_type,
        source_ids=[source_id_override] if source_id_override else None,
        observation_period=observation_period,
        date_filter=date_filter,
    )


async def get_observations(
    client: DCClient,
    variable_dcid: str,
    place_dcid: str | None = None,
    place_name: str | None = None,
    child_place_type: str | None = None,
    source_id_override: str | None = None,
    period: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> ObservationToolResponse:
    """
    Builds the request, fetches the data, and returns the final response.
    This is the main entry point for the observation service.
    """
    observation_request = await _build_observation_request(
        client=client,
        variable_dcid=variable_dcid,
        place_dcid=place_dcid,
        place_name=place_name,
        child_place_type=child_place_type,
        source_id_override=source_id_override,
        period=period,
        start_date=start_date,
        end_date=end_date,
    )

    return await client.fetch_obs(observation_request)


async def search_indicators(
    client: DCClient,
    query: str,
    places: list[str] | None = None,
    include_topics: bool = True,
    include_bilateral: bool = False,
    per_search_limit: int = 10,
) -> SearchResponse:
    """Search for topics and/or variables based on mode."""
    # Validate parameters
    _validate_search_parameters(
        places=places,
        include_bilateral=include_bilateral,
        per_search_limit=per_search_limit,
    )

    # Resolve place names to DCIDs
    place_dcids_map = await _resolve_places(client, places=places)

    # Create search tasks based on place parameters
    search_tasks = _create_search_tasks(
        query=query,
        places=places,
        place_dcids_map=place_dcids_map,
        include_bilateral=include_bilateral,
    )

    search_result = await _search_indicators(
        client=client,
        search_tasks=search_tasks,
        include_topics=include_topics,
        per_search_limit=per_search_limit,
    )

    # Collect all DCIDs for lookups
    all_dcids = _collect_all_dcids(
        search_result=search_result, search_tasks=search_tasks
    )

    # Fetch lookups
    lookups = await _fetch_and_update_lookups(client, list(all_dcids))

    # Create unified response
    return SearchResponse(
        status="SUCCESS",
        dcid_name_mappings=lookups,
        topics=list(search_result.topics.values()),
        variables=list(search_result.variables.values()),
    )


def _create_search_tasks(
    query: str,
    places: list[str] | None,
    place_dcids_map: dict[str, str],
    include_bilateral: bool,
) -> list[SearchTask]:
    """Create search tasks based on place parameters.

    Args:
        query: The search query
        places: List of place names
        place_dcids_map: Mapping of place names to DCIDs
        include_bilateral: Whether to include bilateral search

    Returns:
        List of SearchTask objects
    """
    search_tasks = []

    if places:
        # Single search task with all place DCIDs (no query rewriting)
        place_dcids = [
            place_dcid for name in places if (place_dcid := place_dcids_map.get(name))
        ]
        search_tasks.append(SearchTask(query=query, place_dcids=place_dcids))

        if include_bilateral:
            for p in places:
                search_tasks.append(
                    SearchTask(
                        query=f"{query} {p}",
                        place_dcids=place_dcids if len(place_dcids) > 1 else [],
                    )
                )

    else:
        # No places: single search task with no place constraints
        search_tasks.append(SearchTask(query=query, place_dcids=[]))

    return search_tasks


def _validate_search_parameters(
    places: list[str] | None,
    include_bilateral: bool,
    per_search_limit: int,
) -> None:
    """Validate search parameters

    Args:
        places: List of place names (mutually exclusive with bilateral_places)
        include_bilateral: Whether to include bilateral search
        per_search_limit: Maximum results per search

    Raises:
        ValueError: If any parameter validation fails
    """
    # Validate per_search_limit parameter
    if not 1 <= per_search_limit <= 100:
        raise ValueError("per_search_limit must be between 1 and 100")

    # Validate place parameters
    if not places and include_bilateral:
        raise ValueError("Cannot specify `include_bilateral` without `places`")


async def _resolve_places(
    client: DCClient,
    places: list[str] | None,
) -> dict[str, str]:
    """Resolve place names to DCIDs.

    Args:
        client: DCClient instance for place resolution
        places: List of place names (mutually exclusive with bilateral_places)

    Returns:
        Dictionary mapping place names to DCIDs

    Raises:
        DataLookupError: If place resolution fails
    """
    place_names = places or []

    if not place_names:
        return {}

    try:
        return await client.search_places(place_names)
    except Exception as e:
        msg = "Error resolving place names"
        logger.error(f"{msg}: {e}")
        raise DataLookupError(msg) from e


def _collect_all_dcids(
    search_result: SearchResult, search_tasks: list[SearchTask]
) -> set[str]:
    """Collect all DCIDs that need to be looked up.

    Args:
        search_result: The search result containing topics and variables
        search_tasks: List of search tasks containing place DCIDs

    Returns:
        Set of all DCIDs that need lookup (topics, variables, and places)
    """
    all_dcids = set()

    # Add topic DCIDs and their members
    for topic in search_result.topics.values():
        all_dcids.add(topic.dcid)
        all_dcids.update(topic.member_topics)
        all_dcids.update(topic.member_variables)

    # Add variable DCIDs
    all_dcids.update(search_result.variables.keys())

    # Add place DCIDs
    for search_task in search_tasks:
        all_dcids.update(search_task.place_dcids)

    return all_dcids


async def _search_indicators(
    client: DCClient,
    search_tasks: list[SearchTask],
    include_topics: bool = True,
    per_search_limit: int = 10,
) -> SearchResult:
    """Search for indicators matching a query, optionally filtered by place existence.

    Returns:
        SearchResult: Typed result with topics and variables dictionaries
    """
    # Execute parallel searches
    tasks = []
    for search_task in search_tasks:
        task = client.fetch_indicators(
            query=search_task.query,
            place_dcids=search_task.place_dcids,
            include_topics=include_topics,
            max_results=per_search_limit,
        )
        tasks.append(task)

    # Wait for all searches to complete
    results = await asyncio.gather(*tasks)

    return await _merge_search_results(results)


async def _fetch_and_update_lookups(client: DCClient, dcids: list[str]) -> dict:
    """Fetch names for all DCIDs and return as lookups dictionary."""
    if not dcids:
        return {}

    try:
        return client.fetch_entity_names(dcids)
    except Exception:  # noqa: BLE001
        # If fetching fails, return empty dict (not an error)
        return {}


async def _merge_search_results(results: list[dict]) -> SearchResult:
    """Union results from multiple search calls."""

    # Collect all topics and variables
    all_topics: dict[str, SearchTopic] = {}
    all_variables: dict[str, SearchVariable] = {}

    for result in results:
        # Union topics
        for topic in result.get("topics", []):
            topic_dcid = topic["dcid"]
            if topic_dcid not in all_topics:
                all_topics[topic_dcid] = SearchTopic(
                    dcid=topic["dcid"],
                    member_topics=topic.get("member_topics", []),
                    member_variables=topic.get("member_variables", []),
                    places_with_data=topic.get("places_with_data"),
                )

        # Union variables
        for variable in result.get("variables", []):
            var_dcid = variable["dcid"]
            if var_dcid not in all_variables:
                all_variables[var_dcid] = SearchVariable(
                    dcid=variable["dcid"],
                    places_with_data=variable.get("places_with_data", []),
                )

    return SearchResult(topics=all_topics, variables=all_variables)
