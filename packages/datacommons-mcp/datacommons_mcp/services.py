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
    SearchTask,
    SearchResponse,
    SearchVariable,
    SearchTopic,
    SearchResult,
    SearchMode,
    SearchModeType,
)
from datacommons_mcp.exceptions import NoDataFoundError


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
        raise NoDataFoundError(f"No place found matching '{place_name}'.")

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
        except ValueError:
            raise ValueError(f"mode must be either '{SearchMode.BROWSE.value}' or '{SearchMode.LOOKUP.value}'")
    
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
            logging.error(f"Error resolving place names: {e}")
            raise e

    place1_dcid = place_dcids_map.get(place1_name) if place1_name else None
    place2_dcid = place_dcids_map.get(place2_name) if place2_name else None

    # Automatic fallback to browse mode if lookup mode is requested but no places are provided
    if search_mode == SearchMode.LOOKUP and not place_names:
        search_mode = SearchMode.BROWSE
        logging.info(f"Lookup mode requested but no places provided. Automatically switching to browse mode for query: {query}")

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
        place1_place_dcids = [place2_dcid] if place2_dcid else []
        search_tasks.append(SearchTask(query=f"{query} {place1_name}", place_dcids=place1_place_dcids))

    # Place2 query: search for query + place2_name, filter by place1_dcid
    if place2_dcid:
        place2_place_dcids = [place1_dcid] if place1_dcid else []
        search_tasks.append(SearchTask(query=f"{query} {place2_name}", place_dcids=place2_place_dcids))

    if search_mode == SearchMode.LOOKUP:
        # For lookup mode, use simplified logic with query rewriting
        search_result = await _search_indicators_lookup_mode(
            client, search_tasks, per_search_limit
        )
    else:
        # For browse mode, use the existing search_topics_and_variables logic
        search_result = await _search_indicators_browse_mode(
            client, search_tasks, per_search_limit
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
        topics=list(search_result.topics.values()) if search_mode == SearchMode.BROWSE else None,
        variables=list(search_result.variables.values()),
    )


async def _search_indicators_browse_mode(
    client: DCClient,
    search_tasks: list[SearchTask],
    per_search_limit: int = 10,
) -> SearchResult:
    """Search for topics and variables matching a query, optionally filtered by place existence.

    Args:
        client: DCClient instance to use for data operations
        search_tasks: List of SearchTask objects for parallel searches
        per_search_limit: Maximum results per search (default 10, max 100)

    Returns:
        SearchResult: Typed result with topics and variables dictionaries
    """
    # Execute parallel searches
    tasks = []
    for search_task in search_tasks:
        task = client.fetch_topics_and_variables(
            query=search_task.query, place_dcids=search_task.place_dcids, max_results=per_search_limit
        )
        tasks.append(task)

    # Wait for all searches to complete
    results = await asyncio.gather(*tasks)

    # Merge and deduplicate results
    # Extract all place DCIDs from search tasks
    all_place_dcids = set()
    for search_task in search_tasks:
        all_place_dcids.update(search_task.place_dcids)
    valid_place_dcids = list(all_place_dcids)
    
    merged_result = await _merge_search_results(results, valid_place_dcids, client)

    return merged_result





async def _fetch_and_update_lookups(client: DCClient, dcids: list[str]) -> dict:
    """Fetch names for all DCIDs and return as lookups dictionary."""
    if not dcids:
        return {}

    try:
        result = client.fetch_entity_names(dcids)
        return result
    except Exception:
        # If fetching fails, return empty dict (not an error)
        return {}


async def _merge_search_results(
    results: list[dict], place_dcids: list[str] = None, client: DCClient = None
) -> SearchResult:
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
                    places_with_data=topic.get("places_with_data")
                )

        # Union variables
        for variable in result.get("variables", []):
            var_dcid = variable["dcid"]
            if var_dcid not in all_variables:
                all_variables[var_dcid] = SearchVariable(
                    dcid=variable["dcid"],
                    places_with_data=variable.get("places_with_data", [])
                )

    return SearchResult(
        topics=all_topics,
        variables=all_variables
    )


async def _search_indicators_lookup_mode(
    client: DCClient,
    search_tasks: list[SearchTask],
    per_search_limit: int = 10,
) -> SearchResult:
    """Search for variables only in lookup mode with query rewriting.
    
    Args:
        client: DCClient instance to use for data operations
        search_tasks: List of SearchTask objects for parallel searches
        per_search_limit: Maximum results per search (default 10, max 100)
    
    Returns:
        SearchResult: Typed result with variables dictionary only
    """
    # Execute parallel searches for each query/place combination
    all_variables: dict[str, SearchVariable] = {}  # Map of variable_dcid -> SearchVariable
    all_place_dcids = set()

    for search_task in search_tasks:
        all_place_dcids.update(search_task.place_dcids)
        
        # For each place, search for variables
        for place_dcid in search_task.place_dcids:
            try:
                variable_data = await client.fetch_topic_variables(
                    place_dcid, topic_query=search_task.query
                )
                
                # Extract variable DCIDs and track which place found each variable
                variable_dcids = variable_data.get("topic_variable_ids", [])
                for var_dcid in variable_dcids:
                    if var_dcid not in all_variables:
                        all_variables[var_dcid] = SearchVariable(
                            dcid=var_dcid,
                            places_with_data=[]
                        )
                    all_variables[var_dcid].places_with_data.append(place_dcid)
                
            except Exception as e:
                logging.error(f"Error fetching variables for place {place_dcid}: {e}")
                continue
    
    # Limit results if needed
    if per_search_limit and len(all_variables) > per_search_limit:
        # Convert to list, limit, then back to dict
        limited_variables = {}
        for i, (var_dcid, var_obj) in enumerate(all_variables.items()):
            if i >= per_search_limit:
                break
            limited_variables[var_dcid] = var_obj
        all_variables = limited_variables

    return SearchResult(
        topics={},  # No topics in lookup mode
        variables=all_variables
    )



