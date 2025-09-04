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
    place1_name: str | None = None,
    place2_name: str | None = None,
    per_search_limit: int = 10,
) -> SearchResponse:
    """Search for topics and/or variables based on mode.

    Args:
        client: DCClient instance to use for data operations
        query: The search query for indicators
        mode: "browse" (topics + variables) or "lookup" (variables only)
        place1_name: First place name for filtering and existence checks
        place2_name: Second place name for filtering and existence checks
        per_search_limit: Maximum results per search (default 10, max 100)

    Returns:
        dict: Dictionary with topics, variables, and lookups (browse mode) or variables only (lookup mode)
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

    # Resolve all place names to DCIDs in a single call
    place_names = [name for name in [place1_name, place2_name] if name]
    place_dcids_map = {}

    if place_names:
        try:
            place_dcids_map = await client.search_places(place_names)
        except Exception as e:
            msg = "Error resolving place names"
            logger.error("%s: %s", msg, e)
            raise DataLookupError(msg) from e

    place1_dcid = place_dcids_map.get(place1_name) if place1_name else None
    place2_dcid = place_dcids_map.get(place2_name) if place2_name else None

    # Construct search queries with their corresponding place DCIDs for filtering
    search_tasks = []

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

    search_result = await _search_indicators(
        client, search_mode, search_tasks, per_search_limit
    )

    # Collect all DCIDs for lookups
    all_dcids = set()

    # Add topic DCIDs and their members
    for topic in search_result.topics.values():
        all_dcids.add(topic.dcid)
        all_dcids.update(topic.member_topics)
        all_dcids.update(topic.member_variables)

    # Add variable DCIDs
    all_dcids.update(search_result.variables.keys())

    # Add place DCIDs
    all_place_dcids = set()
    for search_task in search_tasks:
        all_place_dcids.update(search_task.place_dcids)
    all_dcids.update(all_place_dcids)

    # Fetch lookups
    lookups = await _fetch_and_update_lookups(client, list(all_dcids))

    # Create unified response
    return SearchResponse(
        status="SUCCESS",
        lookups=lookups,
        topics=list(search_result.topics.values()),
        variables=list(search_result.variables.values()),
    )


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
