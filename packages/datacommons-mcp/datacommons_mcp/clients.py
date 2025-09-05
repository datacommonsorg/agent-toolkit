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

import json
import logging
import re

import requests
from datacommons_client.client import DataCommonsClient

from datacommons_mcp.cache import LruCache
from datacommons_mcp.data_models.enums import SearchScope
from datacommons_mcp.data_models.observations import (
    ObservationApiResponse,
    ObservationRequest,
)
from datacommons_mcp.data_models.search import SearchMode
from datacommons_mcp.data_models.settings import (
    BaseDCSettings,
    CustomDCSettings,
    DCSettings,
)
from datacommons_mcp.topics import TopicStore, create_topic_store, read_topic_cache

logger = logging.getLogger(__name__)


class DCClient:
    def __init__(
        self,
        dc: DataCommonsClient,
        search_scope: SearchScope = SearchScope.BASE_ONLY,
        base_index: str = "base_uae_mem",
        custom_index: str | None = None,
        sv_search_base_url: str = "https://datacommons.org",
        topic_store: TopicStore | None = None,
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

    async def fetch_obs(self, request: ObservationRequest) -> ObservationApiResponse:
        # Get the raw API response
        if request.child_place_type:
            return self.dc.observation.fetch_observations_by_entity_type(
                variable_dcids=request.variable_dcid,
                parent_entity=request.place_dcid,
                entity_type=request.child_place_type,
                date=request.observation_period,
                filter_facet_ids=request.source_ids,
            )
        return self.dc.observation.fetch(
            variable_dcids=request.variable_dcid,
            entity_dcids=request.place_dcid,
            date=request.observation_period,
            filter_facet_ids=request.source_ids,
        )

    def fetch_entity_names(self, dcids: list[str]) -> dict:
        response = self.dc.node.fetch_entity_names(entity_dcids=dcids)
        return {dcid: name.value for dcid, name in response.items()}

    def fetch_entity_types(self, dcids: list[str]) -> dict:
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

    async def search_svs(
        self, queries: list[str], *, skip_topics: bool = True, max_results: int = 10
    ) -> dict:
        results_map = {}
        skip_topics_param = "&skip_topics=true" if skip_topics else ""
        endpoint_url = f"{self.sv_search_base_url}/api/nl/search-vector"
        headers = {"Content-Type": "application/json"}

        # Use precomputed indices based on configured search scope
        indices = self.search_indices

        for query in queries:
            # Search all indices in a single API call using comma-separated list
            indices_param = ",".join(indices)
            api_endpoint = f"{endpoint_url}?idx={indices_param}{skip_topics_param}"
            payload = {"queries": [query]}

            try:
                response = requests.post(  # noqa: S113
                    api_endpoint, data=json.dumps(payload), headers=headers
                )
                response.raise_for_status()
                data = response.json()
                results = data.get("queryResults", {})

                if (
                    query in results
                    and "SV" in results[query]
                    and "CosineScore" in results[query]
                ):
                    sv_list = results[query]["SV"]
                    score_list = results[query]["CosineScore"]

                    # Return results in API order (no ranking)
                    all_results = [
                        {"SV": sv_list[i], "CosineScore": score_list[i]}
                        for i in range(len(sv_list))
                    ]
                    results_map[query] = all_results[
                        :max_results
                    ]  # Limit to max_results
                else:
                    results_map[query] = []

            except Exception as e:  # noqa: BLE001
                logger.error(
                    "An unexpected error occurred for query '%s': %s", query, e
                )
                results_map[query] = []

        return results_map

    async def child_place_type_exists(
        self, parent_place_dcid: str, child_place_type: str
    ) -> bool:
        response = self.dc.node.fetch_place_children(
            place_dcids=parent_place_dcid, children_type=child_place_type, as_dict=True
        )
        return len(response.get(parent_place_dcid, [])) > 0

    async def fetch_indicators(
        self,
        query: str,
        mode: SearchMode,
        place_dcids: list[str] = None,
        max_results: int = 10,
    ) -> dict:
        """
        Search for indicators matching a query, optionally filtered by place existence.
        When mode is SearchMode.LOOKUP, return variables only.
        When mode is SearchMode.BROWSE, return both topics and variables.
        When place_dcids are specified, filter the results by place existence.

        Returns:
            Dictionary with topics, variables, and lookups
        """
        # Search for more results than we need to ensure we get enough topics and variables.
        # The factor of 2 is arbitrary and we can adjust it (make it configurable?) as needed.
        max_search_results = max_results * 2
        # Search for indicators - it returns topics and / or variables based on the mode.
        search_results = await self._search_indicators(query, mode, max_search_results)

        # Separate topics and variables
        topics = search_results.get("topics", [])
        variables = search_results.get("variables", [])

        # Apply existence filtering if places are specified
        if place_dcids:
            # Ensure place variables are cached for all places
            for place_dcid in place_dcids:
                self._ensure_place_variables_cached(place_dcid)

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
        topic_members = self._get_topics_members_with_existence(topics, place_dcids)

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
        }

    async def _search_indicators(
        self, query: str, mode: SearchMode, max_results: int = 10
    ) -> dict:
        """
        Search for topics and variables using search_svs.
        When mode is SearchMode.LOOKUP, expand topics to variables.
        """
        logger.info(f"Searching for indicators with query: {query} and mode: {mode}")
        search_results = await self.search_svs(
            [query], skip_topics=False, max_results=max_results
        )
        results = search_results.get(query, [])

        topics = []
        variables = []
        # Track variables to avoid duplicates when expanding topics to variables in lookup mode.
        variable_set: set[str] = set()

        for result in results:
            sv_dcid = result.get("SV", "")
            if not sv_dcid:
                continue

            # Check if it's a topic (contains "/topic/")
            if "/topic/" in sv_dcid:
                # Only include topics that exist in the topic store
                if self.topic_store and sv_dcid in self.topic_store.topics_by_dcid:
                    # In lookup mode, expand topics to variables.
                    if mode == SearchMode.LOOKUP:
                        for variable in self.topic_store.get_topic_variables(sv_dcid):
                            if variable not in variable_set:
                                variables.append(variable)
                                variable_set.add(variable)
                    else:
                        topics.append(sv_dcid)
            else:
                variables.append(sv_dcid)
                variable_set.add(sv_dcid)

        return {"topics": topics, "variables": variables}

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

    def _filter_variables_by_existence(
        self, variable_dcids: list[str], place_dcids: list[str]
    ) -> list[dict]:
        """Filter variables by existence for the given places (OR logic)."""
        if not variable_dcids or not place_dcids:
            return []

        # Check which variables exist for any of the places
        existing_variables = []
        for var in variable_dcids:
            places_with_data = []
            for place_dcid in place_dcids:
                place_variables = self.variable_cache.get(place_dcid)
                if place_variables is not None and var in place_variables:
                    places_with_data.append(place_dcid)

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
                var in place_variables for var in topic_data.variables
            ):
                return True

        # Recursively check member topics
        for member_topic in topic_data.member_topics:
            if self._check_topic_exists_recursive(member_topic, place_dcids):
                return True

        return False

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
            place_variables = self.variable_cache.get(place_dcid)
            if place_variables is not None:
                matching_vars = [
                    var for var in topic_data.variables if var in place_variables
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

    def _get_topics_members_with_existence(
        self, topic_dcids: list[dict], place_dcids: list[str] = None
    ) -> dict:
        """Get member topics and variables for topics, filtered by existence if places specified."""
        if not topic_dcids or not self.topic_store:
            return {}

        result = {}

        for topic_info in topic_dcids:
            topic_dcid = topic_info["dcid"]
            topic_data = self.topic_store.topics_by_dcid.get(topic_dcid)
            if not topic_data:
                continue

            member_topics = topic_data.member_topics
            member_variables = topic_data.variables

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


def _create_base_dc_client(settings: BaseDCSettings) -> DCClient:
    """Create a base DC client from settings."""
    # Create topic store from path if provided else use default topic cache
    topic_store = None
    if settings.topic_cache_path:
        topic_store = read_topic_cache(settings.topic_cache_path)
    else:
        topic_store = read_topic_cache()

    # Create DataCommonsClient
    dc = DataCommonsClient(api_key=settings.api_key)

    # Create DCClient
    return DCClient(
        dc=dc,
        search_scope=SearchScope.BASE_ONLY,
        base_index=settings.base_index,
        custom_index=None,
        sv_search_base_url=settings.sv_search_base_url,
        topic_store=topic_store,
    )


def _create_custom_dc_client(settings: CustomDCSettings) -> DCClient:
    """Create a custom DC client from settings."""
    # Use search scope directly (it's already an enum)
    search_scope = settings.search_scope

    # Create DataCommonsClient
    dc = DataCommonsClient(url=settings.api_base_url)

    # Create topic store if root_topic_dcids provided
    topic_store = None
    if settings.root_topic_dcids:
        topic_store = create_topic_store(settings.root_topic_dcids, dc)

    # Create DCClient
    return DCClient(
        dc=dc,
        search_scope=search_scope,
        base_index=settings.base_index,
        custom_index=settings.custom_index,
        sv_search_base_url=settings.custom_dc_url,  # Use custom_dc_url as sv_search_base_url
        topic_store=topic_store,
    )
