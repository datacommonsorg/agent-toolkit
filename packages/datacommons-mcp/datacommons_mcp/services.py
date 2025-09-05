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
    DataSeries,
    DateRange,
    EntityMetadata,
    ObservationApiResponse,
    ObservationPeriod,
    ObservationRequest,
    ObservationToolResponse,
    PlaceObservation,
    ResolvedPlace,
    SeriesMetadata,
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
) -> ObservationRequest:
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
    return ObservationRequest(
        variable_dcid=variable_dcid,
        place_dcid=place_dcid,
        child_place_type=child_place_type,
        source_ids=[source_id_override] if source_id_override else None,
        observation_period=observation_period,
        date_filter=date_filter,
    )


async def _fetch_observation_metadata(
    client: DCClient,
    variable_dcid: str,
    api_response: ObservationApiResponse,
    parent_place_dcid: str | None = None,
) -> dict[str, EntityMetadata]:
    """Fetches names and types for all relevant DCIDs and returns a unified map."""
    all_dcids_to_fetch = {variable_dcid}
    api_variable_data = api_response.byVariable.get(variable_dcid)
    if api_variable_data:
        all_dcids_to_fetch.update(api_variable_data.byEntity.keys())

    if parent_place_dcid:
        all_dcids_to_fetch.add(parent_place_dcid)

    if not all_dcids_to_fetch:
        return {}

    dcids_list = list(all_dcids_to_fetch)
    names_map_task = client.fetch_entity_names(dcids_list)
    types_map_task = client.fetch_entity_types(dcids_list)
    names_map, types_map = await asyncio.gather(names_map_task, types_map_task)

    # Combine into a single metadata map
    metadata_map: dict[str, EntityMetadata] = {}
    for dcid in dcids_list:
        metadata_map[dcid] = EntityMetadata(
            name=names_map.get(dcid, ""),
            type_of=types_map.get(dcid),  # This will be None if not in map
        )
    return metadata_map


def _build_observation_tool_response(
    api_response: ObservationApiResponse,
    observation_request: ObservationRequest,
    metadata_map: dict[str, EntityMetadata],
) -> ObservationToolResponse:
    """Builds the final ObservationToolResponse from the API response."""
    variable_dcid = observation_request.variable_dcid
    variable_metadata = metadata_map.get(
        variable_dcid, EntityMetadata(name="", type_of=None)
    )
    final_response = ObservationToolResponse(
        variable_dcid=variable_dcid, variable_name=variable_metadata.name
    )

    if observation_request.child_place_type:
        parent_dcid = observation_request.place_dcid
        parent_metadata = metadata_map.get(
            parent_dcid, EntityMetadata(name="", type_of=None)
        )
        final_response.resolved_parent_place = ResolvedPlace(
            dcid=parent_dcid,
            name=parent_metadata.name,
            place_type=(parent_metadata.type_of or [None])[0],
        )

    api_variable_data = api_response.byVariable.get(variable_dcid)
    if not api_variable_data:
        return final_response

    for obs_place_dcid, api_place_data in api_variable_data.byEntity.items():
        if not api_place_data.orderedFacets:
            continue

        all_series_data = []
        for facet_data in api_place_data.orderedFacets:
            # Check if source is already added to avoid duplicates
            if not any(
                s.source_id == facet_data.facetId for s in final_response.source_info
            ):
                facet_metadata = api_response.facets.get(facet_data.facetId)
                if facet_metadata:
                    final_response.source_info.append(
                        Source(
                            **facet_metadata.model_dump(), source_id=facet_data.facetId
                        )
                    )

            filtered_obs = filter_by_date(
                facet_data.observations, observation_request.date_filter
            )
            series_metadata = SeriesMetadata(
                source_id=facet_data.facetId,
                earliest_date=facet_data.earliestDate,
                latest_date=facet_data.latestDate,
                observation_count=len(filtered_obs),
            )
            all_series_data.append((series_metadata, filtered_obs))

        _add_place_observation(
            final_response, all_series_data, obs_place_dcid, metadata_map
        )

    return final_response


def _add_place_observation(
    response: ObservationToolResponse,
    all_series_data: list[tuple[SeriesMetadata, list]],
    obs_place_dcid: str,
    metadata_map: dict[str, EntityMetadata],
) -> None:
    """Finds the primary series and adds a PlaceObservation to the response."""
    primary_series_metadata = None
    primary_observations = []
    alternative_series_metadata = []

    found_primary = False
    for metadata, obs in all_series_data:
        if not found_primary and obs:
            primary_series_metadata = metadata
            primary_observations = obs
            found_primary = True
        else:
            alternative_series_metadata.append(metadata)

    if not found_primary and all_series_data:
        primary_series_metadata, _ = all_series_data[0]
        alternative_series_metadata = [s[0] for s in all_series_data[1:]]

    if not primary_series_metadata:
        return

    place_metadata = metadata_map.get(
        obs_place_dcid, EntityMetadata(name="", type_of=None)
    )
    place_observation = PlaceObservation(
        place=ResolvedPlace(
            dcid=obs_place_dcid,
            name=place_metadata.name,
            place_type=(place_metadata.type_of or [None])[0],
        ),
        primary_series=DataSeries(
            source_id=primary_series_metadata.source_id,
            observations=primary_observations,
        ),
        alternative_series_metadata=alternative_series_metadata,
    )
    response.observations_by_place.append(place_observation)


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

    Response Structure Example:
      {
        "variable_dcid": "Count_Person",
        "variable_name": "Count of Person",
        "resolved_parent_place": null,
        "observations_by_place": [
          {
            "place": {
              "dcid": "country/USA",
              "name": "United States",
              "place_type": "Country"
            },
            "primary_series": {
              "source_id": "source1",
              "observations": [
                {"date": "2021", "value": 332000000},
                {"date": "2022", "value": 333000000}
              ]
            },
            "alternative_series_metadata": [
              {
                "source_id": "source2",
                "earliest_date": "2019",
                "latest_date": "2021",
                "observation_count": 3
              }
            ]
          }
        ],
        "source_info": [
          {
            "source_id": "source1",
            "importName": "U.S. Census Bureau",
            "url": "https://www.census.gov/"
          },
          {
            "source_id": "source2",
            "importName": "World Bank",
            "url": "https://www.worldbank.org/"
          }
        ]
      }
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

    api_response = await client.fetch_obs(observation_request)

    parent_place_dcid = observation_request.place_dcid if child_place_type else None
    metadata_map = await _fetch_observation_metadata(
        client, variable_dcid, api_response, parent_place_dcid
    )

    return _build_observation_tool_response(
        api_response, observation_request, metadata_map
    )


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
