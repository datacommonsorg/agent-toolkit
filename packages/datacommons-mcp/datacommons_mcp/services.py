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
from collections import defaultdict
from datetime import datetime
from typing import Any

from datacommons_client.models.observation import ByVariable

from datacommons_mcp.clients import DCClient
from datacommons_mcp.data_models.observations import (
    AlternativeSource,
    DateRange,
    EntityMetadata,
    ObservationApiResponse,
    ObservationPeriod,
    ObservationRequest,
    ObservationToolResponse,
    PlaceObservation,
    ResolvedPlace,
    Source,
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
from datacommons_mcp.utils import filter_by_date

logger = logging.getLogger(__name__)


async def _validate_and_build_request(
    client: DCClient,
    variable_dcid: str,
    place_dcid: str | None = None,
    place_name: str | None = None,
    child_place_type: str | None = None,
    source_id_override: str | None = None,
    period: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> ObservationRequest:
    """Validates inputs and builds an ObservationRequest, resolving place names."""
    if not variable_dcid:
        raise ValueError("'variable_dcid' must be specified.")

    if not (place_name or place_dcid):
        raise ValueError("Specify either 'place_name' or 'place_dcid'.")

    if not period and (start_date is None) != (end_date is None):
        raise ValueError(
            "Both 'start_date' and 'end_date' are required for a date range."
        )

    resolved_place_dcid = place_dcid
    if not resolved_place_dcid:
        # Resolve place name to a DCID
        results = await client.search_places([place_name])
        resolved_place_dcid = results.get(place_name)
        if not resolved_place_dcid:
            raise DataLookupError(f"No place found matching '{place_name}'.")

    # Determine the observation period and date filter
    date_filter = None
    observation_period = ObservationPeriod.LATEST
    if period:
        observation_period = ObservationPeriod(period)
    elif start_date and end_date:
        observation_period = ObservationPeriod.ALL
        date_filter = DateRange(start_date=start_date, end_date=end_date)

    return ObservationRequest(
        variable_dcid=variable_dcid,
        place_dcid=resolved_place_dcid,
        child_place_type=child_place_type,
        source_ids=[source_id_override] if source_id_override else None,
        observation_period=observation_period,
        date_filter=date_filter,
    )


async def _fetch_all_metadata(
    client: DCClient,
    variable_dcid: str,
    api_response: ObservationApiResponse,
    parent_place_dcid: str | None,
) -> dict[str, EntityMetadata]:
    """Fetches and combines names and types for all entities into a single map."""
    variable_data = (
        api_response.byVariable.get(variable_dcid)
        if api_response and api_response.byVariable
        else None
    )
    dcids_to_fetch = set()
    if variable_data:
        dcids_to_fetch.update(variable_data.byEntity.keys())

    if parent_place_dcid:
        dcids_to_fetch.add(parent_place_dcid)

    if not dcids_to_fetch:
        return {}

    dcids_list = list(dcids_to_fetch)
    names_task = client.fetch_entity_names(dcids_list)  # Now an awaitable coroutine
    types_task = client.fetch_entity_types(dcids_list)
    names_map, types_map = await asyncio.gather(names_task, types_task)

    metadata_map = {}
    for dcid in dcids_list:
        metadata_map[dcid] = EntityMetadata(
            name=names_map.get(dcid, ""),
            type_of=types_map.get(dcid),
        )
    return metadata_map


# Streamlined helper method for selecting the primary source
def _select_primary_source(
    variable_data: ByVariable, request: ObservationRequest
) -> tuple[str | None, dict[str, int], dict[str, Any]]:
    """
    Selects the primary source and returns pre-processed data for each place.
    Returns: (primary_source_id, alt_source_counts, processed_data_by_place)
    """
    source_place_counts = defaultdict(int)
    source_date_counts = defaultdict(int)
    source_latest_dates = defaultdict(lambda: datetime.min)

    processed_data_by_place = {}

    for place_dcid, place_data in variable_data.byEntity.items():
        if not place_data.orderedFacets:
            continue

        best_facet = None
        best_filtered_obs = []
        for facet_data in place_data.orderedFacets:
            filtered_obs = filter_by_date(facet_data.observations, request.date_filter)
            if (
                filtered_obs
                and not best_facet
                or len(filtered_obs) > len(best_filtered_obs)
            ):
                best_facet = facet_data
                best_filtered_obs = filtered_obs

        if best_facet:
            processed_data_by_place[place_dcid] = {
                "facet": best_facet,
                "observations": best_filtered_obs,
            }

            source_id = best_facet.facetId
            source_place_counts[source_id] += 1
            source_date_counts[source_id] += len(best_filtered_obs)

            latest_date_str = max(o.date for o in best_filtered_obs)
            # TODO: handle non year-only dates
            latest_date = datetime.strptime(latest_date_str, "%Y")
            if latest_date > source_latest_dates[source_id]:
                source_latest_dates[source_id] = latest_date

    if not source_place_counts:
        return None, {}, {}

    primary_source = max(
        source_place_counts.keys(),
        key=lambda src_id: (
            source_place_counts[src_id],
            source_date_counts[src_id],
            source_latest_dates[src_id],
            src_id,  # Final deterministic tie-breaker
        ),
    )

    alternative_source_counts = {
        src_id: count
        for src_id, count in source_place_counts.items()
        if src_id != primary_source
    }

    return primary_source, alternative_source_counts, processed_data_by_place


def _create_place_observation(
    obs_place_dcid: str,
    preprocessed_data: dict[str, Any],
    metadata_map: dict[str, EntityMetadata],
) -> PlaceObservation | None:
    """
    Builds a PlaceObservation model using pre-processed data.
    """
    if not preprocessed_data:
        return None

    selected_facet = preprocessed_data["facet"]
    filtered_obs = preprocessed_data["observations"]

    observations = [{o.date: o.value} for o in filtered_obs]

    place_metadata = metadata_map.get(obs_place_dcid)
    resolved_place = ResolvedPlace(
        dcid=obs_place_dcid,
        name=place_metadata.name if place_metadata else "",
        place_type=(place_metadata.type_of or [None])[0] if place_metadata else None,
    )

    return PlaceObservation(
        place=resolved_place,
        source_id=selected_facet.facetId,
        observations=observations,
    )


async def _build_final_response(
    request: ObservationRequest,
    api_response: ObservationApiResponse,
    metadata_map: dict[str, EntityMetadata],
) -> ObservationToolResponse:
    """
    Builds the final ObservationToolResponse model from API data and metadata.
    """
    variable_data = api_response.byVariable.get(request.variable_dcid, ByVariable({}))
    primary_source_id, alternative_source_counts, processed_data_by_place = (
        _select_primary_source(variable_data, request)
    )

    primary_source = None
    if primary_source_id and primary_source_id in api_response.facets:
        facet_metadata = api_response.facets[primary_source_id]
        primary_source = Source(source_id=primary_source_id, **facet_metadata.to_dict())

    final_response = ObservationToolResponse(
        variable_dcid=request.variable_dcid,
        child_place_type=request.child_place_type,
        source=primary_source,
    )

    if request.child_place_type:
        parent_metadata = metadata_map.get(request.place_dcid)
        final_response.resolved_parent_place = ResolvedPlace(
            dcid=request.place_dcid,
            name=parent_metadata.name if parent_metadata else "",
            place_type=(parent_metadata.type_of or [None])[0]
            if parent_metadata
            else None,
        )

    if processed_data_by_place:
        for obs_place_dcid, preprocessed_data in processed_data_by_place.items():
            place_observation = _create_place_observation(
                obs_place_dcid=obs_place_dcid,
                preprocessed_data=preprocessed_data,
                metadata_map=metadata_map,
            )
            if place_observation:
                final_response.observations_by_place.append(place_observation)

    for alt_source_id, count in alternative_source_counts.items():
        facet_metadata = api_response.facets.get(alt_source_id)

        # If there's only one place in the response, set count to None
        num_places = count if len(processed_data_by_place) > 1 else None

        if facet_metadata:
            final_response.alternative_sources.append(
                AlternativeSource(
                    source_id=alt_source_id,
                    num_available_places=num_places,
                    **facet_metadata.to_dict(),
                )
            )

    return final_response


# Main function to get observations
async def get_observations(
    client: DCClient,
    variable_dcid: str,
    place_dcid: str | None = None,
    place_name: str | None = None,
    child_place_type: str | None = None,
    source_override: str | None = None,
    period: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> ObservationToolResponse:
    observation_request = await _validate_and_build_request(
        client=client,
        variable_dcid=variable_dcid,
        place_dcid=place_dcid,
        place_name=place_name,
        child_place_type=child_place_type,
        source_override=source_override,
        period=period,
        start_date=start_date,
        end_date=end_date,
    )

    api_response = await client.fetch_obs(observation_request)

    metadata_map = await _fetch_all_metadata(
        client, variable_dcid, api_response, observation_request.place_dcid
    )

    return await _build_final_response(
        request=observation_request,
        api_response=api_response,
        metadata_map=metadata_map,
    )


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
        return await client.fetch_entity_names(dcids)
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
