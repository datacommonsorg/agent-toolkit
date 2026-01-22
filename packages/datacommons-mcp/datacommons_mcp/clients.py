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
"""
Clients module for interacting with Data Commons instances.
Provides classes for managing connections to both base and custom Data Commons instances.
"""

import asyncio
import logging
import re
from pathlib import Path

import requests
from datacommons_client.client import DataCommonsClient

from datacommons_mcp._constrained_vars import place_statvar_constraint_mapping
from datacommons_mcp.cache import LruCache
from datacommons_mcp.data_models.enums import SearchScope
from datacommons_mcp.data_models.observations import (
    ObservationApiResponse,
    ObservationRequest,
)
from datacommons_mcp.data_models.search import (
    NodeInfo,
    SearchIndicator,
    SearchTopic,
    SearchVariable,
)
from datacommons_mcp.data_models.settings import (
    BaseDCSettings,
    CustomDCSettings,
    DCSettings,
)
from datacommons_mcp.topics import TopicStore, create_topic_store, read_topic_caches
from datacommons_mcp.version import __version__

logger = logging.getLogger(__name__)

DCID_TOPIC_PREFIX = "topic/"

SURFACE_HEADER_VALUE = f"mcp-{__version__}"

# 'x-surface' indicates to DC APIs that this call is coming from the MCP server
SURFACE_HEADER: dict[str, str] = {"x-surface": SURFACE_HEADER_VALUE}


class DCClient:
    def __init__(
        self,
        dc: DataCommonsClient,
        search_scope: SearchScope = SearchScope.BASE_ONLY,
        base_index: str = "base_uae_mem",
        custom_index: str | None = None,
        sv_search_base_url: str = "https://datacommons.org",
        topic_store: TopicStore | None = None,
        _place_like_constraints: list[str] | None = None,
    ) -> None:
        """
        Initialize the DCClient with a DataCommonsClient and search configuration.

        Args:
            dc: DataCommonsClient instance
            search_scope: SearchScope enum controlling search behavior
            base_index: Index to use for base DC searches
            custom_index: Index to use for custom DC searches (None for base DC)
            sv_search_base_url: Base URL for SV search endpoint
            topic_store: Optional TopicStore for caching

            # TODO(@jm-rivera): Remove this parameter once new endpoint is live.
            _place_like_constraints: Optional list of place-like constraints
        """
        self.dc = dc
        self.search_scope = search_scope
        self.base_index = base_index
        self.custom_index = custom_index
        # Precompute search indices to validate configuration at instantiation time
        self.search_indices = self._compute_search_indices()
        self.sv_search_base_url = sv_search_base_url
        self.variable_cache = LruCache(128)

        if topic_store is None:
            topic_store = TopicStore(topics_by_dcid={}, all_variables=set())
        self.topic_store = topic_store

        if _place_like_constraints:
            self._compute_place_like_statvar_store(constraints=_place_like_constraints)
        else:
            self._place_like_statvar_store = {}

    #
    # Initialization & Configuration
    #
    def _compute_search_indices(self) -> list[str]:
        """Compute and validate search indices based on the configured search_scope.

        Raises a ValueError immediately for invalid configurations (e.g., CUSTOM_ONLY
        without a custom_index).
        """
        indices: list[str] = []

        if self.search_scope in [SearchScope.CUSTOM_ONLY, SearchScope.BASE_AND_CUSTOM]:
            if self.custom_index is not None and self.custom_index != "":
                indices.append(self.custom_index)
            elif self.search_scope == SearchScope.CUSTOM_ONLY:
                raise ValueError(
                    "Custom index not configured but CUSTOM_ONLY search scope requested"
                )

        if self.search_scope in [SearchScope.BASE_ONLY, SearchScope.BASE_AND_CUSTOM]:
            indices.append(self.base_index)

        return indices

    def _compute_place_like_statvar_store(self, constraints: list[str]) -> None:
        """Compute and cache place-like to statistical variable mappings.
        # TODO (@jm-rivera): Remove once new endpoint is live.
        """
        self._place_like_statvar_store = place_statvar_constraint_mapping(
            client=self.dc, place_like_constraints=constraints
        )

    #
    # Core DC API Wrappers
    #
    async def fetch_obs(self, request: ObservationRequest) -> ObservationApiResponse:
        # Get the raw API response
        if request.child_place_type:
            return self.dc.observation.fetch_observations_by_entity_type(
                variable_dcids=request.variable_dcid,
                parent_entity=request.place_dcid,
                entity_type=request.child_place_type,
                date=request.date_type,
                filter_facet_ids=request.source_ids,
            )
        return self.dc.observation.fetch(
            variable_dcids=request.variable_dcid,
            entity_dcids=request.place_dcid,
            date=request.date_type,
            filter_facet_ids=request.source_ids,
        )

    async def fetch_entity_names(self, dcids: list[str]) -> dict:
        response = self.dc.node.fetch_entity_names(entity_dcids=dcids)
        return {dcid: name.value for dcid, name in response.items() if name}

    async def fetch_entity_infos(self, dcids: list[str]) -> dict[str, NodeInfo]:
        """Fetch entity information including name and type for a list of DCIDs."""

        # Fetch both name and typeOf properties in a single call
        response = self.dc.node.fetch_property_values(
            node_dcids=dcids, properties=["name", "typeOf"]
        )

        result = {}
        for dcid in dcids:
            # Extract name from nodes (name properties have .value attribute)
            name_nodes = response.extract_connected_nodes(dcid, "name")
            # Extract type from DCIDs (typeOf properties have .dcid attribute)
            type_dcids = response.extract_connected_dcids(dcid, "typeOf")

            if name_nodes and type_dcids:
                result[dcid] = NodeInfo(name=name_nodes[0].value, type_of=type_dcids)

        return result

    async def fetch_entity_types(self, dcids: list[str]) -> dict:
        response = self.dc.node.fetch_property_values(
            node_dcids=dcids, properties="typeOf"
        )
        return {
            dcid: list(response.extract_connected_dcids(dcid, "typeOf"))
            for dcid in response.get_properties()
        }

    async def search_places(self, names: list[str]) -> dict:
        results_map = {}
        response = self.dc.resolve.fetch_dcids_by_name(names=names)
        data = response.to_dict()
        entities = data.get("entities", [])
        for entity in entities:
            node, candidates = entity.get("node", ""), entity.get("candidates", [])
            if node and candidates:
                results_map[node] = candidates[0].get("dcid", "")
        return results_map

    async def child_place_type_exists(
        self, parent_place_dcid: str, child_place_type: str
    ) -> bool:
        response = self.dc.node.fetch_place_children(
            place_dcids=parent_place_dcid, children_type=child_place_type, as_dict=True
        )
        return len(response.get(parent_place_dcid, [])) > 0

    #
    # Search Indicators Helpers (Shared)
    #
    def _ensure_place_variables_cached(self, place_dcid: str) -> None:
        """Ensure variables for a place are cached."""
        if self.variable_cache.get(place_dcid) is None:
            # Fetch and cache variables for the place
            response = self.dc.observation.fetch_available_statistical_variables(
                entity_dcids=[place_dcid]
            )
            unfiltered_variables = response.get(place_dcid, [])
            # Filter out internal variables
            all_variables = {
                var
                for var in unfiltered_variables
                if self.topic_store.has_variable(var)
                or not re.fullmatch(r"dc/[a-z0-9]{10,}", var)
            }
            self.variable_cache.put(place_dcid, all_variables)

    def _get_variable_places_with_data(
        self, var_dcid: str, place_dcids: list[str]
    ) -> list[str]:
        places_with_data = []

        for place_dcid in place_dcids:
            # TODO (@jm-rivera): Remove place-like check once new search endpoint is live.
            place_variables = self.variable_cache.get(
                place_dcid
            ) | self._place_like_statvar_store.get(place_dcid, set())
            if place_variables is not None and var_dcid in place_variables:
                places_with_data.append(place_dcid)
        return places_with_data

    def _get_topic_places_with_data(
        self, topic_dcid: str, place_dcids: list[str]
    ) -> list[str]:
        """Get list of places where the topic has data."""
        if not self.topic_store or not place_dcids:
            return []

        topic_data = self.topic_store.topics_by_dcid.get(topic_dcid)
        if not topic_data:
            return []

        places_with_data = []

        # Check direct variables
        for place_dcid in place_dcids:
            # TODO (@jm-rivera): Remove place-like check once new search endpoint is live.
            place_variables = self.variable_cache.get(
                place_dcid
            ) | self._place_like_statvar_store.get(place_dcid, set())
            if place_variables is not None:
                matching_vars = [
                    var for var in topic_data.member_variables if var in place_variables
                ]
                if matching_vars:
                    places_with_data.append(place_dcid)

        # Check member topics recursively
        for member_topic in topic_data.member_topics:
            member_places = self._get_topic_places_with_data(member_topic, place_dcids)
            for place in member_places:
                if place not in places_with_data:
                    places_with_data.append(place)

        return places_with_data

    #
    # New Search Indicators Endpoint (/api/nl/search-indicators)
    #

    def _check_topic_exists_recursive(
        self, topic_dcid: str, place_dcids: list[str]
    ) -> bool:
        """Recursively check if any variable in the topic hierarchy exists for any of the places (OR logic)."""
        if not self.topic_store or not place_dcids:
            return False

        topic_data = self.topic_store.topics_by_dcid.get(topic_dcid)
        if not topic_data:
            return False

        # Check if any direct variable exists for any of the places
        for place_dcid in place_dcids:
            place_variables = self.variable_cache.get(place_dcid)
            if place_variables and any(
                var in place_variables for var in topic_data.member_variables
            ):
                return True

        # Recursively check member topics
        for member_topic in topic_data.member_topics:
            if self._check_topic_exists_recursive(member_topic, place_dcids):
                return True

        return False

    def _filter_indicators_by_existence(
        self, indicators: list[SearchIndicator], place_dcids: list[str]
    ) -> list[SearchIndicator]:
        # If no places are provided, no filtering is needed. Return all indicators.
        # Their places_with_data will remain as the default (empty list or None).
        if not place_dcids:
            return indicators

        filtered_indicators = []

        for indicator in indicators:
            if isinstance(indicator, SearchTopic):
                places_with_data = self._get_topic_places_with_data(
                    indicator.dcid, place_dcids
                )
            else:
                places_with_data = self._get_variable_places_with_data(
                    indicator.dcid, place_dcids
                )
            if places_with_data:
                indicator.places_with_data = places_with_data
                filtered_indicators.append(indicator)

        return filtered_indicators

    def _expand_topics_to_variables(
        self, indicators: list[SearchIndicator], place_dcids: list[str]
    ) -> list[SearchVariable]:
        """Expands topics in a list of indicators into their member variables."""
        expanded_variables = {}
        for indicator in indicators:
            if isinstance(indicator, SearchTopic):
                for var_dcid in indicator.member_variables:
                    if var_dcid in expanded_variables:
                        continue

                    # Re-check existence for each new variable.
                    places_with_data = []
                    if place_dcids:
                        places_with_data = self._get_variable_places_with_data(
                            var_dcid, place_dcids
                        )
                        if not places_with_data:
                            # Variable does not pass place filtering, do not add
                            continue
                    expanded_variables[var_dcid] = SearchVariable(
                        dcid=var_dcid, places_with_data=places_with_data
                    )

            elif indicator.dcid not in expanded_variables:
                expanded_variables[indicator.dcid] = indicator

        return list(expanded_variables.values())

    async def _call_search_indicators_temp(
        self, queries: list[str], *, max_results: int = 10
    ) -> dict:
        """
        Temporary method that mirrors search_svs but calls the new search-indicators endpoint.

        This method takes the same arguments and returns the same structure as search_svs,
        but uses the new /api/nl/search-indicators endpoint instead of /api/nl/search-vector.

        This method is temporary to create a minimal delta between the two endpoints to minimize the impact of the change.
        After the 1.0 release, this method should be removed in favor of a more complete implementation.

        Returns:
            Dictionary mapping query strings to lists of results with 'SV' and 'CosineScore' keys
        """
        results_map = {}
        endpoint_url = f"{self.sv_search_base_url}/api/nl/search-indicators"
        headers = {"Content-Type": "application/json", **SURFACE_HEADER}

        # Use precomputed indices based on configured search scope
        indices = self.search_indices

        for query in queries:
            # Prepare parameters for the new endpoint
            params = {
                "queries": [query],
                "limit_per_index": max_results,
                "index": indices,
            }

            try:
                response = await asyncio.to_thread(
                    requests.get,
                    endpoint_url,
                    params=params,
                    headers=headers,  # noqa: S113
                )
                response.raise_for_status()
                api_response = response.json()

                # Transform the response to match search_svs format
                transformed_results = self._transform_search_indicators_to_svs_format(
                    api_response, max_results=max_results
                )
                results_map[query] = transformed_results

            except Exception as e:  # noqa: BLE001
                logger.error(
                    "An unexpected error occurred for query '%s': %s", query, e
                )
                results_map[query] = []

        return results_map

    def _transform_search_indicators_to_svs_format(
        self, api_response: dict, *, max_results: int = 10
    ) -> list[dict]:
        """
        Transform search-indicators response to match search_svs format.

        Returns:
            List of dictionaries with 'SV' and 'CosineScore' keys
        """
        results = []
        query_results = api_response.get("queryResults", [])

        for query_result in query_results:
            for index_result in query_result.get("indexResults", []):
                for indicator in index_result.get("results", []):
                    dcid = indicator.get("dcid")
                    if not dcid:
                        continue

                    # Extract score (default to 0.0 if not present)
                    score = indicator.get("score", 0.0)

                    results.append(
                        {
                            "SV": dcid,
                            "CosineScore": score,
                            "description": indicator.get("description"),
                            "alternate_descriptions": indicator.get(
                                "search_descriptions"
                            ),
                        }
                    )

        # Sort by score descending, then limit results
        results.sort(key=lambda x: x["CosineScore"], reverse=True)
        return results[:max_results]

    async def fetch_indicators(
        self,
        query: str,
        place_dcids: list[str] = None,
        max_results: int = 10,
        *,
        include_topics: bool = True,
    ) -> dict:
        """
        Search for indicators matching a query, optionally filtered by place existence.
        When place_dcids are specified, filter the results by place existence.

        Returns:
            Dictionary with topics, variables, and lookups
        """
        query = query.strip()

        # An empty query is treated as a request to browse for root topics.
        if not query:
            if self.topic_store and self.topic_store.root_topic_dcids:
                search_results = {
                    "topics": self.topic_store.root_topic_dcids,
                }
            else:
                search_results = {}

        else:
            # Search for more results than we need to ensure we get enough topics and variables.
            # The factor of 2 is arbitrary and we can adjust it (make it configurable?) as needed.
            max_search_results = max_results * 2
            search_results = await self._search_vector(
                query=query,
                max_results=max_search_results,
                include_topics=include_topics,
            )

        # Separate topics and variables
        topics = search_results.get("topics", [])
        variables = search_results.get("variables", [])

        # Apply existence filtering if places are specified
        if place_dcids:
            # Ensure place variables are cached for all places in parallel
            await asyncio.gather(
                *(
                    asyncio.to_thread(self._ensure_place_variables_cached, place_dcid)
                    for place_dcid in place_dcids
                )
            )

            # Filter topics and variables by existence (OR logic)
            topics = self._filter_topics_by_existence(topics, place_dcids)
            variables = self._filter_variables_by_existence(variables, place_dcids)
        else:
            # No existence checks performed, convert to simple lists
            topics = [{"dcid": topic} for topic in topics]
            variables = [{"dcid": var} for var in variables]

        # Limit results
        topics = topics[:max_results]
        variables = variables[:max_results]

        # Get member information for topics
        topic_members = self._get_topics_members_with_existence(
            topics, include_topics=include_topics, place_dcids=place_dcids
        )

        # Build response structure
        return {
            "topics": [
                {
                    "dcid": topic_info["dcid"],
                    "member_topics": topic_members.get(topic_info["dcid"], {}).get(
                        "member_topics", []
                    ),
                    "member_variables": topic_members.get(topic_info["dcid"], {}).get(
                        "member_variables", []
                    ),
                    **(
                        {"places_with_data": topic_info["places_with_data"]}
                        if "places_with_data" in topic_info
                        else {}
                    ),
                }
                for topic_info in topics
            ],
            "variables": [
                {
                    "dcid": var_info["dcid"],
                    **(
                        {"places_with_data": var_info["places_with_data"]}
                        if "places_with_data" in var_info
                        else {}
                    ),
                }
                for var_info in variables
            ],
            "lookups": self._build_lookups(
                [topic_info["dcid"] for topic_info in topics]
                + [var_info["dcid"] for var_info in variables]
            ),
            "descriptions": search_results.get("descriptions", {}),
            "alternate_descriptions": search_results.get("alternate_descriptions", {}),
        }

    async def _search_vector(
        self, query: str, max_results: int = 10, *, include_topics: bool = True
    ) -> dict:
        """
        Search for topics and variables using the search-indicators or search-vector endpoint.
        """
        # Always include topics since we need to expand topics to variables.
        logger.info("Calling search-indicators endpoint for: '%s'", query)
        search_results = await self._call_search_indicators_temp(
            queries=[query],
            max_results=max_results,
        )

        results = search_results.get(query, [])

        topics = []
        variables = []
        descriptions: dict[str, str] = {}
        alternate_descriptions: dict[str, list[str]] = {}
        # Track variables to avoid duplicates when expanding topics to variables.
        variable_set: set[str] = set()

        for result in results:
            sv_dcid = result.get("SV", "")
            if not sv_dcid:
                continue

            # Check if it's a topic (contains "/topic/")
            if DCID_TOPIC_PREFIX in sv_dcid:
                # Only include topics that exist in the topic store
                if self.topic_store and sv_dcid in self.topic_store.topics_by_dcid:
                    # If topics are not included, expand topics to variables.
                    if not include_topics:
                        for variable in self.topic_store.get_topic_descendant_variables(
                            sv_dcid
                        ):
                            if variable not in variable_set:
                                variables.append(variable)
                                variable_set.add(variable)
                    else:
                        topics.append(sv_dcid)
            else:
                variables.append(sv_dcid)
                variable_set.add(sv_dcid)

            descriptions[sv_dcid] = result.get("description")
            alternate_descriptions[sv_dcid] = result.get("alternate_descriptions")

        return {
            "topics": topics,
            "variables": variables,
            "descriptions": descriptions,
            "alternate_descriptions": alternate_descriptions,
        }

    def _filter_variables_by_existence(
        self, variable_dcids: list[str], place_dcids: list[str]
    ) -> list[dict]:
        """Filter variables by existence for the given places (OR logic)."""
        if not variable_dcids or not place_dcids:
            return []

        # Check which variables exist for any of the places
        existing_variables = []
        for var in variable_dcids:
            places_with_data = self._get_variable_places_with_data(var, place_dcids)
            if places_with_data:
                existing_variables.append(
                    {"dcid": var, "places_with_data": places_with_data}
                )

        return existing_variables

    def _filter_topics_by_existence(
        self, topic_dcids: list[str], place_dcids: list[str]
    ) -> list[dict]:
        """Filter topics by existence using recursive checks."""
        if not topic_dcids:
            return []

        existing_topics = []
        for topic_dcid in topic_dcids:
            places_with_data = self._get_topic_places_with_data(topic_dcid, place_dcids)
            if places_with_data:
                existing_topics.append(
                    {"dcid": topic_dcid, "places_with_data": places_with_data}
                )

        return existing_topics

    def _get_topics_members_with_existence(
        self,
        topic_dcids: list[dict],
        *,
        include_topics: bool,
        place_dcids: list[str] = None,
    ) -> dict:
        """Get member topics and variables for topics, filtered by existence if places specified

        If include_topics is false, we return all descendant variables.
        If include_topics is true, we return member topics and member variables.
        """
        if not topic_dcids or not self.topic_store:
            return {}

        result = {}

        for topic_info in topic_dcids:
            topic_dcid = topic_info["dcid"]
            topic_data = self.topic_store.topics_by_dcid.get(topic_dcid)
            if not topic_data:
                continue

            member_topics: list[str] = []
            member_variables: list[str] = []

            if include_topics:
                member_topics = topic_data.member_topics
                member_variables = topic_data.member_variables
            else:
                member_topics = []
                member_variables = topic_data.descendant_variables

            # Filter by existence if places are specified
            if place_dcids:
                # Filter member variables by existence
                filtered_variables = self._filter_variables_by_existence(
                    member_variables, place_dcids
                )
                # Extract just the dcids from the filtered results
                member_variables = [var["dcid"] for var in filtered_variables]

                # Filter member topics by existence
                filtered_topics = self._filter_topics_by_existence(
                    member_topics, place_dcids
                )
                # Extract just the dcids from the filtered results
                member_topics = [topic["dcid"] for topic in filtered_topics]

            result[topic_dcid] = {
                "member_topics": member_topics,
                "member_variables": member_variables,
            }

        return result

    def _build_lookups(self, entities: list[str]) -> dict:
        """Build DCID-to-name mappings using TopicStore."""
        if not self.topic_store:
            return {}

        lookups = {}
        for entity in entities:
            name = self.topic_store.get_name(entity)
            if name:
                lookups[entity] = name

        return lookups


#
# Client Factory Functions
#
# TODO(keyurva): For custom dc client, load both custom and base dc topic stores and merge them.
# Since this is not the case currently, base topics are not returned for custom dc (in base_only and base_and_custom modes).
def create_dc_client(settings: DCSettings) -> DCClient:
    """
    Factory function to create a single DCClient based on settings.

    Args:
        settings: DCSettings object containing client settings

    Returns:
        DCClient instance configured according to the provided settings

    Raises:
        ValueError: If required fields are missing or settings is invalid
    """
    if isinstance(settings, BaseDCSettings):
        return _create_base_dc_client(settings)
    if isinstance(settings, CustomDCSettings):
        return _create_custom_dc_client(settings)

    raise ValueError(
        f"Invalid settings type: {type(settings)}. Must be BaseDCSettings or CustomDCSettings"
    )


def _create_base_topic_store(settings: DCSettings) -> TopicStore:
    """Create a topic store from settings."""
    if settings.topic_cache_paths:
        paths = [Path(path) for path in settings.topic_cache_paths]
        topic_store = read_topic_caches(paths)
    else:
        topic_store = read_topic_caches()

    # Set base root topic DCIDs, they are separately specified in the settings.
    topic_store.root_topic_dcids = settings.base_root_topic_dcids

    logger.info("Base DC topic store loaded")

    return topic_store


def _create_base_dc_client(settings: BaseDCSettings) -> DCClient:
    """Create a base DC client from settings."""
    # Create topic store from path if provided else use default topic cache
    topic_store = _create_base_topic_store(settings)

    # Create DataCommonsClient, conditionally adding api_root
    dc_client_args = {
        "api_key": settings.api_key,
        "surface_header_value": SURFACE_HEADER_VALUE,
    }
    if settings.api_root:
        logger.info("Using API root for base DC: %s", settings.api_root)
        logger.info("Using search root for base DC: %s", settings.search_root)
        dc_client_args["url"] = settings.api_root
    dc = DataCommonsClient(**dc_client_args)

    # Create DCClient
    return DCClient(
        dc=dc,
        search_scope=SearchScope.BASE_ONLY,
        base_index=settings.base_index,
        custom_index=None,
        sv_search_base_url=settings.search_root,
        topic_store=topic_store,
    )


def _create_custom_dc_client(settings: CustomDCSettings) -> DCClient:
    """Create a custom DC client from settings."""
    # Use search scope directly (it's already an enum)
    search_scope = settings.search_scope

    # Create DataCommonsClient
    dc = DataCommonsClient(
        url=settings.api_base_url,
        surface_header_value=SURFACE_HEADER_VALUE,
    )

    # Create topic store if root_topic_dcids provided
    topic_store: TopicStore | None = None
    if settings.root_topic_dcids:
        topic_store = create_topic_store(settings.root_topic_dcids, dc)

    if search_scope == SearchScope.BASE_AND_CUSTOM:
        base_topic_store = _create_base_topic_store(settings)
        topic_store = (
            topic_store.merge(base_topic_store) if topic_store else base_topic_store
        )

    if topic_store:
        logger.info("Custom DC topic store loaded")

    # Create DCClient
    return DCClient(
        dc=dc,
        search_scope=search_scope,
        base_index=settings.base_index,
        custom_index=settings.custom_index,
        sv_search_base_url=settings.custom_dc_url,  # Use custom_dc_url as sv_search_base_url
        topic_store=topic_store,
        # TODO (@jm-rivera): Remove place-like parameter new search endpoint is live.
        _place_like_constraints=settings.place_like_constraints,
    )
