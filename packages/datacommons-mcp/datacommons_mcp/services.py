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
    mode: SearchModeType | None = None,
    places: list[str] | None = None,
    bilateral_places: list[str] | None = None,
    per_search_limit: int = 10,
) -> SearchResponse:
    """Search for topics and/or variables based on mode."""
    # Validate parameters and convert mode to enum
    search_mode = _validate_search_parameters(
        mode, places, bilateral_places, per_search_limit
    )

    # Resolve place names to DCIDs
    place_dcids_map = await _resolve_places(client, places, bilateral_places)

    # Create search tasks based on place parameters
    search_tasks = _create_search_tasks(
        query, places, bilateral_places, place_dcids_map
    )

    search_result = await _search_indicators(
        client, search_mode, search_tasks, per_search_limit
    )

    # Collect all DCIDs for lookups
    all_dcids = _collect_all_dcids(search_result, search_tasks)

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
    bilateral_places: list[str] | None,
    place_dcids_map: dict[str, str],
) -> list[SearchTask]:
    """Create search tasks based on place parameters.

    Args:
        query: The search query
        places: List of place names (mutually exclusive with bilateral_places)
        bilateral_places: List of exactly 2 place names (mutually exclusive with places)
        place_dcids_map: Mapping of place names to DCIDs

    Returns:
        List of SearchTask objects
    """
    search_tasks = []

    if places:
        # Single search task with all place DCIDs (no query rewriting)
        place_dcids = [
            place_dcids_map.get(name) for name in places if place_dcids_map.get(name)
        ]
        search_tasks.append(SearchTask(query=query, place_dcids=place_dcids))

    elif bilateral_places:
        # Three search tasks with query rewriting (same as current behavior)
        place1_name, place2_name = bilateral_places
        place1_dcid = place_dcids_map.get(place1_name)
        place2_dcid = place_dcids_map.get(place2_name)

        # Base query: search for the original query, filter by all available places
        base_place_dcids = []
        if place1_dcid:
            base_place_dcids.append(place1_dcid)
        if place2_dcid:
            base_place_dcids.append(place2_dcid)

        search_tasks.append(SearchTask(query=query, place_dcids=base_place_dcids))

        # Place1 query: search for query + place1_name, filter by place2_dcid
        if place1_dcid:
            search_tasks.append(
                SearchTask(
                    query=f"{query} {place1_name}",
                    place_dcids=[place2_dcid] if place2_dcid else [],
                )
            )

        # Place2 query: search for query + place2_name, filter by place1_dcid
        if place2_dcid:
            search_tasks.append(
                SearchTask(
                    query=f"{query} {place2_name}",
                    place_dcids=[place1_dcid] if place1_dcid else [],
                )
            )

    else:
        # No places: single search task with no place constraints
        search_tasks.append(SearchTask(query=query, place_dcids=[]))

    return search_tasks


def _validate_search_parameters(
    mode: SearchModeType | None,
    places: list[str] | None,
    bilateral_places: list[str] | None,
    per_search_limit: int,
) -> SearchMode:
    """Validate search parameters and convert mode to enum.

    Args:
        mode: Search mode string or None
        places: List of place names (mutually exclusive with bilateral_places)
        bilateral_places: List of exactly 2 place names (mutually exclusive with places)
        per_search_limit: Maximum results per search

    Returns:
        SearchMode enum value

    Raises:
        ValueError: If any parameter validation fails
    """
    # Convert string mode to enum for validation and comparison, defaulting to browse if not specified
    if not mode:
        search_mode = SearchMode.BROWSE
    else:
        try:
            search_mode = SearchMode(mode)
        except ValueError as e:
            raise ValueError(
                f"mode must be either '{SearchMode.BROWSE.value}' or '{SearchMode.LOOKUP.value}'"
            ) from e

    # Validate per_search_limit parameter
    if not 1 <= per_search_limit <= 100:
        raise ValueError("per_search_limit must be between 1 and 100")

    # Validate place parameters
    if places is not None and bilateral_places is not None:
        raise ValueError("Cannot specify both 'places' and 'bilateral_places'")

    if bilateral_places is not None and len(bilateral_places) != 2:
        raise ValueError("bilateral_places must contain exactly 2 place names")

    return search_mode


async def _resolve_places(
    client: DCClient,
    places: list[str] | None,
    bilateral_places: list[str] | None,
) -> dict[str, str]:
    """Resolve place names to DCIDs.

    Args:
        client: DCClient instance for place resolution
        places: List of place names (mutually exclusive with bilateral_places)
        bilateral_places: List of exactly 2 place names (mutually exclusive with places)

    Returns:
        Dictionary mapping place names to DCIDs

    Raises:
        DataLookupError: If place resolution fails
    """
    place_names = places or bilateral_places or []

    if not place_names:
        return {}

    try:
        return await client.search_places(place_names)
    except Exception as e:
        msg = "Error resolving place names"
        logger.error("%s: %s", msg, e)
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
    mode: SearchMode,
    search_tasks: list[SearchTask],
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
            mode=mode,
            place_dcids=search_task.place_dcids,
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
