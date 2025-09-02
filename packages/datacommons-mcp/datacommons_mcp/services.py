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
from datacommons_mcp.exceptions import NoDataFoundError

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


async def search_topics_and_variables(
    client: DCClient,
    query: str,
    place1_name: str | None = None,
    place2_name: str | None = None,
    per_search_limit: int = 10,
) -> dict:
    """Search for topics and variables matching a query, optionally filtered by place existence.

    Args:
        client: DCClient instance to use for data operations
        query: The search query for indicators
        place1_name: First place name for filtering and existence checks
        place2_name: Second place name for filtering and existence checks
        per_search_limit: Maximum results per search (default 10, max 100)

    Returns:
        dict: Dictionary with topics, variables, and lookups
    """
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
            logger.error("Error resolving place names: %s", e)
            raise e

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

    search_tasks.append((query, base_place_dcids))

    # The following queries are not needed for bilateral relationships where we append the place name(s) to the query.

    # Place1 query: search for query + place1_name, filter by place2_dcid
    if place1_dcid:
        place1_place_dcids = [place2_dcid] if place2_dcid else []
        search_tasks.append((f"{query} {place1_name}", place1_place_dcids))

    # Place2 query: search for query + place2_name, filter by place1_dcid
    if place2_dcid:
        place2_place_dcids = [place1_dcid] if place1_dcid else []
        search_tasks.append((f"{query} {place2_name}", place2_place_dcids))

    # Execute parallel searches
    tasks = []
    for search_query, place_dcids in search_tasks:
        task = client.fetch_topics_and_variables(
            query=search_query, place_dcids=place_dcids, max_results=per_search_limit
        )
        tasks.append(task)

    # Wait for all searches to complete
    results = await asyncio.gather(*tasks)

    # Merge and deduplicate results
    # Filter out None place DCIDs
    valid_place_dcids = [
        dcid for dcid in [place1_dcid, place2_dcid] if dcid is not None
    ]
    return await _merge_search_results(results, valid_place_dcids, client)


def _collect_all_dcids(
    topics: list[dict], variables: list[str], place_dcids: list[str] = None
) -> list[str]:
    """Collect all DCIDs from topics, variables, and places."""
    all_dcids = set()

    # Collect topic DCIDs and their member DCIDs
    for topic in topics:
        all_dcids.add(topic["dcid"])
        # Handle member_topics - could be strings or dicts
        member_topics = topic.get("member_topics", [])
        for member in member_topics:
            if isinstance(member, dict):
                all_dcids.add(member["dcid"])
            else:
                all_dcids.add(member)
        # Handle member_variables - could be strings or dicts
        member_variables = topic.get("member_variables", [])
        for member in member_variables:
            if isinstance(member, dict):
                all_dcids.add(member["dcid"])
            else:
                all_dcids.add(member)

    # Collect variable DCIDs
    all_dcids.update(variables)

    # Collect place DCIDs if provided
    if place_dcids:
        all_dcids.update(place_dcids)

    # Filter out None values and empty strings
    return [dcid for dcid in all_dcids if dcid is not None and dcid.strip()]


async def _fetch_and_update_lookups(client: DCClient, dcids: list[str]) -> dict:
    """Fetch names for all DCIDs and return as lookups dictionary."""
    if not dcids:
        return {}

    try:
        return client.fetch_entity_names(dcids)
    except Exception:
        # If fetching fails, return empty dict (not an error)
        return {}


async def _merge_search_results(
    results: list[dict], place_dcids: list[str] = None, client: DCClient = None
) -> dict:
    """Union results from multiple search calls."""

    # Collect all topics and variables
    all_topics = {}
    all_variables = {}

    for result in results:
        # Union topics
        for topic in result.get("topics", []):
            topic_dcid = topic["dcid"]
            if topic_dcid not in all_topics:
                all_topics[topic_dcid] = topic

        # Union variables
        for variable in result.get("variables", []):
            var_dcid = variable["dcid"]
            if var_dcid not in all_variables:
                all_variables[var_dcid] = variable

    # Collect all DCIDs and fetch their names
    all_dcids = _collect_all_dcids(
        list(all_topics.values()), list(all_variables.keys()), place_dcids
    )

    # Fetch names for all DCIDs and use as lookups
    lookups = await _fetch_and_update_lookups(client, all_dcids)

    return {
        "topics": list(all_topics.values()),
        "variables": list(all_variables.values()),
        "lookups": lookups,
    }
