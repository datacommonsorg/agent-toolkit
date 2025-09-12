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

from datacommons_client.models.observation import ByVariable

from datacommons_mcp.clients import DCClient
from datacommons_mcp.data_models.observations import (
    AlternativeSource,
    DateRange,
    FacetMetadata,
    Node,  # Re-import Node as it's still used directly
    ObservationApiResponse,
    ObservationDate,
    ObservationDateType,
    ObservationRequest,
    ObservationToolResponse,
    PlaceObservation,
    SourceProcessingResult,
    TimeSeriesPoint,
)
from datacommons_mcp.data_models.search import (
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
    source_override: str | None = None,
    date: str = ObservationDateType.LATEST.value,
    date_range_start: str | None = None,
    date_range_end: str | None = None,
) -> ObservationRequest:
    """Validates inputs and builds an ObservationRequest, resolving place names."""
    if not variable_dcid:
        raise ValueError("'variable_dcid' must be specified.")

    if not (place_name or place_dcid):
        raise ValueError("Specify either 'place_name' or 'place_dcid'.")

    parsed_date = ObservationDate(date=date)
    if parsed_date.date == ObservationDateType.RANGE:
        date_filter = DateRange(start_date=date_range_start, end_date=date_range_end)
        date_request_type = ObservationDateType.ALL
    elif parsed_date.date in [member.value for member in ObservationDateType]:
        date_filter = None
        date_request_type = parsed_date.date
    else:
        date_filter = DateRange(start_date=parsed_date.date, end_date=parsed_date.date)
        date_request_type = ObservationDateType.ALL

    if parsed_date.date != ObservationDateType.RANGE and (
        date_range_start or date_range_end
    ):
        raise ValueError("To specificy a date range, set `date` to 'range'.")

    resolved_place_dcid = place_dcid
    if not resolved_place_dcid:
        # Resolve place name to a DCID
        results = await client.search_places([place_name])
        resolved_place_dcid = results.get(place_name)
        if not resolved_place_dcid:
            raise DataLookupError(f"No place found matching '{place_name}'.")
    return ObservationRequest(
        variable_dcid=variable_dcid,
        place_dcid=resolved_place_dcid,
        child_place_type=child_place_type,
        source_ids=[source_override] if source_override else None,
        date_type=date_request_type,
        date_filter=date_filter,
    )


async def _fetch_all_metadata(
    client: DCClient,
    variable_dcid: str,
    api_response: ObservationApiResponse,
    parent_place_dcid: str | None,
) -> dict[str, Node]:
    """Fetches and combines names and types for all entities into a single map."""
    variable_data = api_response.byVariable.get(variable_dcid) if api_response else None
    dcids_names_to_fetch = {variable_dcid}
    dcids_types_to_fetch = set()

    if variable_data and variable_data.byEntity:
        # Always fetch names of all entities
        dcids_names_to_fetch.update(variable_data.byEntity.keys())

        if not parent_place_dcid:
            # Fetch type of single entity
            dcids_types_to_fetch.update(variable_data.byEntity.keys())
        else:
            # Fetch name and type of resolved parent entity
            dcids_types_to_fetch.add(parent_place_dcid)
            dcids_names_to_fetch.add(parent_place_dcid)

    if not (dcids_types_to_fetch or dcids_names_to_fetch):
        return {}

    names_task = client.fetch_entity_names(list(dcids_names_to_fetch))
    types_task = client.fetch_entity_types(list(dcids_types_to_fetch))
    names_map, types_map = await asyncio.gather(names_task, types_task)

    metadata_map = {}
    for dcid in dcids_names_to_fetch | dcids_types_to_fetch:
        metadata_map[dcid] = Node(
            dcid=dcid,
            name=names_map.get(dcid),
            type_of=types_map.get(dcid),
        )
    return metadata_map


# Streamlined helper method for selecting the primary source
def _process_sources_and_filter_observations(
    variable_data: ByVariable, request: ObservationRequest, source_override: str | None
) -> SourceProcessingResult:
    """
    Selects a primary source, ranks alternatives, and filters observations.
    Returns: A SourceProcessingResult object.
    """

    # If a specific source is requested, process only that source and return early.
    if source_override:
        processed_data_by_place = {}
        for place_dcid, place_data in variable_data.byEntity.items():
            for facet_data in place_data.orderedFacets:
                if facet_data.facetId == source_override:
                    filtered_obs = filter_by_date(
                        facet_data.observations, request.date_filter
                    )
                    if filtered_obs:
                        processed_data_by_place[place_dcid] = (
                            SourceProcessingResult.ProcessedPlaceData(
                                facet=facet_data, observations=filtered_obs
                            )
                        )
                    break  # Found the overridden source for this place
        # TODO(clincoln8): Reconsider how to propagate "requested source not found" status to agent.
        return SourceProcessingResult(
            primary_source_id=source_override,
            alternative_source_counts={},
            processed_data_by_place=processed_data_by_place,
        )

    # Iterate all sources to select primary source and build metadata map
    source_places_found_counts = defaultdict(int)
    source_date_counts = defaultdict(int)
    source_latest_dates = defaultdict(lambda: datetime.min)
    source_indices = defaultdict(list)

    # First pass: gather statistics for all available sources to rank them.
    for place_data in variable_data.byEntity.values():
        for i, facet_data in enumerate(place_data.orderedFacets):
            source_id = facet_data.facetId
            filtered_obs = filter_by_date(facet_data.observations, request.date_filter)
            if filtered_obs:
                source_places_found_counts[source_id] += 1
                source_date_counts[source_id] += len(filtered_obs)
                latest_date_str = max(o.date for o in filtered_obs)
                # Store the index to calculate average rank later. Lower is better.
                source_indices[source_id].append(i)

                latest_date = ObservationDate.parse_date(latest_date_str)
                if latest_date > source_latest_dates[source_id]:
                    source_latest_dates[source_id] = latest_date

    if not source_places_found_counts:
        return SourceProcessingResult()

    # Calculate the average index for each source. A lower average is better.
    source_avg_indices = {
        src_id: sum(indices) / len(indices)
        for src_id, indices in source_indices.items()
    }

    primary_source = max(
        source_places_found_counts.keys(),
        key=lambda src_id: (
            source_places_found_counts[src_id],
            source_date_counts[src_id],
            source_latest_dates[src_id],
            # Lower index in the original OrderedFacets list is better, so we
            # negate it.
            -source_avg_indices.get(src_id, float("inf")),
            # Final tie-breaker
            src_id,
        ),
    )

    alternative_source_counts = {
        src_id: count
        for src_id, count in source_places_found_counts.items()
        if src_id != primary_source
    }

    # TODO(clincoln8): Encapsulate _build_processed_data(source_id, ...) to be used
    # in this case and for override logic.
    # Second pass: build the processed data using only the primary source.
    processed_data_by_place = {}
    for place_dcid, place_data in variable_data.byEntity.items():
        for facet_data in place_data.orderedFacets:
            if facet_data.facetId == primary_source:
                filtered_obs = filter_by_date(
                    facet_data.observations, request.date_filter
                )
                if filtered_obs:
                    processed_data_by_place[place_dcid] = (
                        SourceProcessingResult.ProcessedPlaceData(
                            facet=facet_data, observations=filtered_obs
                        )
                    )
                # Found the primary source for this place, no need to check others.
                break

    return SourceProcessingResult(
        primary_source_id=primary_source,
        alternative_source_counts=alternative_source_counts,
        processed_data_by_place=processed_data_by_place,
    )


def _create_place_observation(
    obs_place_dcid: str,
    preprocessed_data: SourceProcessingResult.ProcessedPlaceData | None,
    metadata_map: dict[str, Node],
) -> PlaceObservation:
    """
    Builds a PlaceObservation model using pre-processed data.
    """
    # Use the fully populated Node object from the metadata map.
    place_node = metadata_map.get(obs_place_dcid, Node(dcid=obs_place_dcid))
    if not preprocessed_data:
        return PlaceObservation(
            place=place_node,
            time_series=[],
        )

    time_series: list[TimeSeriesPoint] = [
        (o.date, o.value) for o in preprocessed_data.observations
    ]

    return PlaceObservation(
        place=place_node,
        time_series=time_series,
    )


async def _build_final_response(
    request: ObservationRequest,
    api_response: ObservationApiResponse,
    metadata_map: dict[str, Node],
) -> ObservationToolResponse:
    """
    Builds the final ObservationToolResponse model from API data and metadata.
    """
    variable_data = api_response.byVariable.get(request.variable_dcid, ByVariable({}))
    source_result = _process_sources_and_filter_observations(
        variable_data, request, (request.source_ids or [None])[0]
    )

    primary_source = None
    if source_result.primary_source_id and (
        source_result.primary_source_id in api_response.facets
    ):
        facet_metadata = api_response.facets[source_result.primary_source_id]
        primary_source = FacetMetadata(
            source_id=source_result.primary_source_id, **facet_metadata.to_dict()
        )

    final_response = ObservationToolResponse(
        variable=metadata_map.get(request.variable_dcid),
        child_place_type=request.child_place_type,
        source_metadata=primary_source
        if primary_source
        else FacetMetadata(source_id="unknown"),
    )

    if request.child_place_type:
        parent_metadata = metadata_map.get(request.place_dcid)
        final_response.resolved_parent_place = parent_metadata

    # Iterate over all places from the original API response to ensure all child
    # places are included in the final result, even if they have no data from
    # the primary source.
    all_places_in_response = variable_data.byEntity.keys()
    for obs_place_dcid in all_places_in_response:
        preprocessed_data = source_result.processed_data_by_place.get(obs_place_dcid)
        place_observation = _create_place_observation(
            obs_place_dcid=obs_place_dcid,
            preprocessed_data=preprocessed_data,
            metadata_map=metadata_map,
        )
        final_response.place_observations.append(place_observation)

    for alt_source_id, count in source_result.alternative_source_counts.items():
        facet_metadata = api_response.facets.get(alt_source_id)

        # If there's only one place in the response, set count to None
        places_found_count = (
            count if len(source_result.processed_data_by_place) > 1 else None
        )

        if facet_metadata:
            final_response.alternative_sources.append(
                AlternativeSource(
                    source_id=alt_source_id,
                    places_found_count=places_found_count,
                    **facet_metadata.to_dict(),
                )
            )

    return final_response


async def get_observations(
    client: DCClient,
    variable_dcid: str,
    place_dcid: str | None = None,
    place_name: str | None = None,
    child_place_type: str | None = None,
    source_override: str | None = None,
    date: str = ObservationDateType.LATEST.value,
    date_range_start: str | None = None,
    date_range_end: str | None = None,
) -> ObservationToolResponse:
    """Fetches statistical observations from Data Commons.

    This service orchestrates the retrieval of observation data by handling
    input validation, place name resolution, data fetching from the client,
    source selection, and metadata enrichment to produce a structured response.

    **Core Logic & Rules**

    - **Mode Selection**:
        - **Single Place Mode**: Fetches data for a single place by providing
          `variable_dcid` and a place identifier (`place_dcid` or `place_name`).
        - **Hierarchy Mode**: Fetches data for all child places of a specific
          type within a parent place (e.g., all counties in a state) by also
          providing `child_place_type`.

    - **Date Filtering**: The tool filters observations by date using the
      following priority:
        1.  **`date` parameter**: This is the primary filter. It can be:
            - A specific date string like '2023', '2023-05', or '2023-05-15'.
              The tool fetches data for the interval represented by the string.
            - A special keyword:
                - `'latest'`: Fetches only the most recent observation.
                - `'all'`: Fetches all available observations.
                - `'range'`: Requires `date_range_start` and/or `date_range_end`.
        2.  **Date Range**: If `date` is set to `'range'`, you must specify a
            date range using `date_range_start` and/or `date_range_end`.
        3.  **Default**: If no date parameters are provided, the tool defaults
            to fetching the `'latest'` observation.

    - **Source Selection**: If multiple data sources (facets) exist for a
      variable, the service automatically selects a "primary source" based on
      which one provides the most comprehensive data. Other sources are listed
      in `alternative_sources`. This can be overridden with `source_override`.

    Args:
        client: An instance of `DCClient` for interacting with Data Commons.
        variable_dcid: The DCID of the statistical variable to fetch.
        place_dcid: The DCID of the place. Takes precedence over `place_name`.
        place_name: The common name of the place (e.g., "California").
        child_place_type: The type of child places to fetch data for.
        source_override: A facet ID to force the use of a specific data source.
        date: A date filter. Accepts 'all', 'latest', 'range', or a date string.
        date_range_start: The start date for a range (inclusive).
        date_range_end: The end date for a range (inclusive).

    Returns:
        An `ObservationToolResponse` object containing the structured data.

    Raises:
        ValueError: If required parameters are missing or invalid.
        DataLookupError: If a `place_name` cannot be resolved to a DCID.
        InvalidDateRangeError: If `start_date` is after `end_date`.
        InvalidDateFormatError: If date strings are in an unsupported format.

    **Example Output (Single Place Call):**
    ```json
    {
      "variable_dcid": "Count_Person",
      "source_metadata": {
        "source_id": "source1",
        "import_name": "US Census"
      },
      "place_observations": [
        {
          "place": {
            "dcid": "country/USA",
            "name": "United States",
            "type_of": ["Country"]
          },
          "time_series": [
            ["2022", 333287557.0],
            ["2021", 332031554.0]
          ]
        }
      ]
    }
    ```

    **Example Output (Hierarchy Call):**
    ```json
    {
      "variable_dcid": "Count_Person",
      "resolved_parent_place": {
        "dcid": "geoId/06",
        "name": "California",
        "type_of": ["State"]
      },
      "child_place_type": "County",
      "place_observations": [
        {
          "place": { "dcid": "geoId/06001", "name": "Alameda County", "type_of": ["County"] },
          "time_series": [["2022", 1628997.0]]
        },
        {
          "place": { "dcid": "geoId/06037", "name": "Los Angeles County", "type_of": ["County"] },
          "time_series": [["2022", 9721138.0]]
        }
      ],
      "source_metadata": { "source_id": "source1", "import_name": "US Census" },
      "alternative_sources": [
        {
          "source_id": "source2",
          "import_name": "Another Census Source",
          "places_found_count": 1
        }
      ]
    }
    """
    observation_request = await _validate_and_build_request(
        client=client,
        variable_dcid=variable_dcid,
        place_dcid=place_dcid,
        place_name=place_name,
        child_place_type=child_place_type,
        source_override=source_override,
        date=date,
        date_range_start=date_range_start,
        date_range_end=date_range_end,
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
    places: list[str] | None = None,
    include_topics: bool = True,
    maybe_bilateral: bool = False,
    per_search_limit: int = 10,
) -> SearchResponse:
    """Search for topics and/or variables."""
    # Validate parameters
    _validate_search_parameters(per_search_limit)

    # Resolve place names to DCIDs
    place_dcids_map = await _resolve_places(client, places)

    # Create search tasks based on place parameters
    search_tasks = _create_search_tasks(query, places, maybe_bilateral, place_dcids_map)

    # Use search-indicators endpoint
    if client.use_search_indicators_endpoint:
        return await client.search_indicators(
            search_tasks, per_search_limit, include_topics=include_topics
        )

    # Use search-vector endpoint
    search_result = await _search_vector(
        client=client,
        include_topics=include_topics,
        search_tasks=search_tasks,
        per_search_limit=per_search_limit,
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
    maybe_bilateral: bool,
    place_dcids_map: dict[str, str],
) -> list[SearchTask]:
    """Create search tasks based on place parameters.

    Args:
        query: The search query
        places: List of place names
        maybe_bilateral: Whether to include bilateral relationship searches
        place_dcids_map: Mapping of place names to DCIDs

    Returns:
        List of SearchTask objects
    """
    search_tasks = []
    place_dcids = (
        [place_dcids_map.get(name) for name in places if place_dcids_map.get(name)]
        if places and place_dcids_map
        else []
    )

    if places and maybe_bilateral:
        # Place-specific searches first (one per place)
        for place_name in places:
            place_dcid = place_dcids_map.get(place_name)
            if place_dcid:
                # Rewrite query to include place name and include all place DCIDs
                search_tasks.append(
                    SearchTask(query=f"{query} {place_name}", place_dcids=place_dcids)
                )

        # Original query search last
        search_tasks.append(SearchTask(query=query, place_dcids=place_dcids))

    elif places:
        # Single search task with all place DCIDs (no query rewriting)
        search_tasks.append(SearchTask(query=query, place_dcids=place_dcids))

    else:
        # No places: single search task with no place constraints
        search_tasks.append(SearchTask(query=query, place_dcids=[]))

    return search_tasks


def _validate_search_parameters(
    per_search_limit: int,
) -> None:
    """Validate search parameters

    Args:
        per_search_limit: Maximum results per search

    Raises:
        ValueError: If any parameter validation fails
    """
    # Validate per_search_limit parameter
    if not 1 <= per_search_limit <= 100:
        raise ValueError("per_search_limit must be between 1 and 100")


async def _resolve_places(
    client: DCClient,
    places: list[str] | None,
) -> dict[str, str]:
    """Resolve place names to DCIDs.

    Args:
        client: DCClient instance for place resolution
        places: List of place names

    Returns:
        Dictionary mapping place names to DCIDs

    Raises:
        DataLookupError: If place resolution fails
    """

    if not places:
        return {}

    try:
        return await client.search_places(places)
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


async def _search_vector(
    client: DCClient,
    search_tasks: list[SearchTask],
    include_topics: bool,
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
