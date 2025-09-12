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
Unit tests for the DCClient class.

This file tests the DCClient wrapper class from `datacommons_mcp.clients`.
It specifically mocks the underlying `datacommons_client.client.DataCommonsClient`
to ensure that our wrapper logic calls the correct methods on the underlying client
without making actual network calls.
"""

import os
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
import requests
from datacommons_client.client import DataCommonsClient
from datacommons_mcp.clients import DCClient, create_dc_client
from datacommons_mcp.data_models.enums import SearchScope
from datacommons_mcp.data_models.observations import (
    ObservationDateType,
    ObservationRequest,
)
from datacommons_mcp.data_models.search import (
    SearchResult,
    SearchTask,
    SearchTopic,
    SearchVariable,
)
from datacommons_mcp.data_models.settings import BaseDCSettings, CustomDCSettings


@pytest.fixture
def mocked_datacommons_client():
    """
    Provides a mocked instance of the underlying `DataCommonsClient`.

    This fixture patches the `DataCommonsClient` constructor within the
    `datacommons_mcp.clients` module. Any instance of `DCClient` created
    in a test using this fixture will have its `self.dc` attribute set to
    this mock instance.
    """
    with patch("datacommons_mcp.clients.DataCommonsClient") as mock_constructor:
        mock_instance = Mock(spec=DataCommonsClient)
        # Manually add the client endpoints which aren't picked up by spec
        mock_instance.observation = Mock()

        mock_constructor.return_value = mock_instance
        yield mock_instance


class TestDCClientConstructor:
    """Tests for the DCClient constructor and search indices computation."""

    def test_dc_client_constructor_base_dc(self, mocked_datacommons_client):
        """
        Test base DC constructor with default parameters.
        """
        # Arrange: Create a base DC client with default parameters
        client_under_test = DCClient(dc=mocked_datacommons_client)

        # Assert: Verify the client is configured correctly
        assert client_under_test.dc == mocked_datacommons_client
        assert client_under_test.search_scope == SearchScope.BASE_ONLY
        assert client_under_test.base_index == "base_uae_mem"
        assert client_under_test.custom_index is None
        assert client_under_test.search_indices == ["base_uae_mem"]

    def test_dc_client_constructor_custom_dc(self, mocked_datacommons_client):
        """
        Test custom DC constructor with custom index.
        """
        # Arrange: Create a custom DC client with custom index
        client_under_test = DCClient(
            dc=mocked_datacommons_client,
            search_scope=SearchScope.CUSTOM_ONLY,
            base_index="medium_ft",
            custom_index="user_all_minilm_mem",
        )

        # Assert: Verify the client is configured correctly
        assert client_under_test.dc == mocked_datacommons_client
        assert client_under_test.search_scope == SearchScope.CUSTOM_ONLY
        assert client_under_test.base_index == "medium_ft"
        assert client_under_test.custom_index == "user_all_minilm_mem"
        assert client_under_test.search_indices == ["user_all_minilm_mem"]

    def test_dc_client_constructor_base_and_custom(self, mocked_datacommons_client):
        """
        Test constructor with BASE_AND_CUSTOM search scope.
        """
        # Arrange: Create a client that searches both base and custom indices
        client_under_test = DCClient(
            dc=mocked_datacommons_client,
            search_scope=SearchScope.BASE_AND_CUSTOM,
            base_index="medium_ft",
            custom_index="user_all_minilm_mem",
        )

        # Assert: Verify the client is configured correctly
        assert client_under_test.search_scope == SearchScope.BASE_AND_CUSTOM
        assert client_under_test.search_indices == ["user_all_minilm_mem", "medium_ft"]

    def test_compute_search_indices_validation_custom_only_without_index(
        self, mocked_datacommons_client
    ):
        """
        Test that CUSTOM_ONLY search scope without custom_index raises ValueError.
        """
        # Arrange & Act & Assert: Creating client with invalid configuration should raise ValueError
        with pytest.raises(
            ValueError,
            match="Custom index not configured but CUSTOM_ONLY search scope requested",
        ):
            DCClient(
                dc=mocked_datacommons_client,
                search_scope=SearchScope.CUSTOM_ONLY,
                custom_index=None,
            )

    def test_compute_search_indices_validation_custom_only_with_empty_index(
        self, mocked_datacommons_client
    ):
        """
        Test that CUSTOM_ONLY search scope with empty custom_index raises ValueError.
        """
        # Arrange & Act & Assert: Creating client with invalid configuration should raise ValueError
        with pytest.raises(
            ValueError,
            match="Custom index not configured but CUSTOM_ONLY search scope requested",
        ):
            DCClient(
                dc=mocked_datacommons_client,
                search_scope=SearchScope.CUSTOM_ONLY,
                custom_index="",
            )


class TestDCClientSearch:
    """Tests for the search_svs method of DCClient."""

    @pytest.mark.asyncio
    @patch("datacommons_mcp.clients.requests.post")
    async def test_search_svs_single_api_call(
        self, mock_post, mocked_datacommons_client
    ):
        """
        Test that search_svs makes a single API call with comma-separated indices.
        """
        # Arrange: Create client and mock response
        client_under_test = DCClient(
            dc=mocked_datacommons_client,
            search_scope=SearchScope.BASE_AND_CUSTOM,
            base_index="medium_ft",
            custom_index="user_all_minilm_mem",
        )

        mock_response = Mock()
        mock_response.json.return_value = {
            "queryResults": {
                "test query": {"SV": ["var1", "var2"], "CosineScore": [0.8, 0.6]}
            }
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        # Act: Call search_svs
        result = await client_under_test.search_svs(["test query"])

        # Assert: Verify single API call with comma-separated indices
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "idx=user_all_minilm_mem,medium_ft" in call_args[0][0]
        assert result["test query"] == [
            {"SV": "var1", "CosineScore": 0.8},
            {"SV": "var2", "CosineScore": 0.6},
        ]

    @pytest.mark.asyncio
    @patch("datacommons_mcp.clients.requests.post")
    async def test_search_svs_skip_topics(self, mock_post, mocked_datacommons_client):
        """
        Test that search_svs respects the skip_topics parameter.
        """
        # Arrange: Create client and mock response
        client_under_test = DCClient(dc=mocked_datacommons_client)

        mock_response = Mock()
        mock_response.json.return_value = {
            "queryResults": {"test query": {"SV": ["var1"], "CosineScore": [0.8]}}
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        # Act: Call search_svs with skip_topics=True
        await client_under_test.search_svs(["test query"], skip_topics=True)

        # Assert: Verify skip_topics parameter is included in API call
        call_args = mock_post.call_args
        assert "skip_topics=true" in call_args[0][0]

    @pytest.mark.asyncio
    @patch("datacommons_mcp.clients.requests.post")
    async def test_search_svs_max_results_limit(
        self, mock_post, mocked_datacommons_client
    ):
        """
        Test that search_svs respects the max_results parameter.
        """
        # Arrange: Create client and mock response with more results than limit
        client_under_test = DCClient(dc=mocked_datacommons_client)

        mock_response = Mock()
        mock_response.json.return_value = {
            "queryResults": {
                "test query": {
                    "SV": ["var1", "var2", "var3", "var4", "var5"],
                    "CosineScore": [0.9, 0.8, 0.7, 0.6, 0.5],
                }
            }
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        # Act: Call search_svs with max_results=3
        result = await client_under_test.search_svs(["test query"], max_results=3)

        # Assert: Verify only 3 results are returned (limited by max_results)
        assert len(result["test query"]) == 3
        assert result["test query"] == [
            {"SV": "var1", "CosineScore": 0.9},
            {"SV": "var2", "CosineScore": 0.8},
            {"SV": "var3", "CosineScore": 0.7},
        ]


@pytest.mark.asyncio
class TestDCClientFetchObs:
    """Tests for the fetch_obs method of DCClient."""

    async def test_fetch_obs_calls_fetch_for_single_place(
        self, mocked_datacommons_client
    ):
        """
        Verifies that fetch_obs calls the correct underlying API for a single place.
        """
        # Arrange
        client_under_test = DCClient(dc=mocked_datacommons_client)
        request = ObservationRequest(
            variable_dcid="var1",
            place_dcid="place1",
            date_type=ObservationDateType.LATEST,
            child_place_type=None,  # Explicitly None for single place query
        )

        # Act
        await client_under_test.fetch_obs(request)

        # Assert
        # Verify that the correct underlying method was called with the right parameters
        mocked_datacommons_client.observation.fetch.assert_called_once_with(
            variable_dcids="var1",
            entity_dcids="place1",
            date=ObservationDateType.LATEST,
            filter_facet_ids=None,
        )
        # Verify that the other method was not called
        mocked_datacommons_client.observation.fetch_observations_by_entity_type.assert_not_called()

    async def test_fetch_obs_calls_fetch_by_entity_type_for_child_places(
        self, mocked_datacommons_client
    ):
        """
        Verifies that fetch_obs calls the correct underlying API for child places.
        """
        # Arrange
        client_under_test = DCClient(dc=mocked_datacommons_client)
        request = ObservationRequest(
            variable_dcid="var1",
            place_dcid="parent_place",
            child_place_type="County",
            date_type=ObservationDateType.LATEST,
        )

        # Act
        await client_under_test.fetch_obs(request)

        # Assert
        # Verify that the correct underlying method was called with the right parameters
        mocked_datacommons_client.observation.fetch_observations_by_entity_type.assert_called_once_with(
            variable_dcids="var1",
            parent_entity="parent_place",
            entity_type="County",
            date=ObservationDateType.LATEST,
            filter_facet_ids=None,
        )
        # Verify that the other method was not called
        mocked_datacommons_client.observation.fetch.assert_not_called()


class TestDCClientFetchIndicators:
    """Tests for the fetch_indicators method of DCClient."""

    @pytest.mark.asyncio
    async def test_fetch_indicators_include_topics_true(
        self, mocked_datacommons_client: Mock
    ):
        """Test basic functionality without place filtering."""
        # Arrange: Create client for the old path and mock search results
        client_under_test = DCClient(
            dc=mocked_datacommons_client, use_search_indicators_endpoint=False
        )

        # Mock search_svs to return topics and variables
        mock_search_results = {
            "test query": [
                {"SV": "dc/topic/Health", "CosineScore": 0.9},
                {"SV": "dc/topic/Economy", "CosineScore": 0.8},
                {"SV": "dc/variable/Count_Person", "CosineScore": 0.7},
                {"SV": "dc/variable/Count_Household", "CosineScore": 0.6},
            ]
        }

        # Mock the search_svs method
        client_under_test.search_svs = AsyncMock(return_value=mock_search_results)

        # Mock topic store
        client_under_test.topic_store = Mock()
        client_under_test.topic_store.get_name.side_effect = lambda dcid: {
            "dc/topic/Health": "Health",
            "dc/topic/Economy": "Economy",
            "dc/variable/Count_Person": "Count of Persons",
            "dc/variable/Count_Household": "Count of Households",
        }.get(dcid, dcid)

        # Mock topic data
        client_under_test.topic_store.topics_by_dcid = {
            "dc/topic/Health": Mock(
                member_topics=[], variables=["dc/variable/Count_Person"]
            ),
            "dc/topic/Economy": Mock(
                member_topics=[], variables=["dc/variable/Count_Household"]
            ),
        }

        # Act: Call the method
        result = await client_under_test.fetch_indicators(
            "test query", include_topics=True
        )

        # Assert: Verify the response structure
        assert "topics" in result
        assert "variables" in result
        assert "lookups" in result

        # Verify topics
        assert len(result["topics"]) == 2
        topic_dcids = [topic["dcid"] for topic in result["topics"]]
        assert "dc/topic/Health" in topic_dcids
        assert "dc/topic/Economy" in topic_dcids

        # Verify variables
        assert len(result["variables"]) == 2
        variable_dcids = [var["dcid"] for var in result["variables"]]
        assert "dc/variable/Count_Person" in variable_dcids
        assert "dc/variable/Count_Household" in variable_dcids

        # Verify lookups
        assert len(result["lookups"]) == 4
        assert result["lookups"]["dc/topic/Health"] == "Health"
        assert result["lookups"]["dc/variable/Count_Person"] == "Count of Persons"

    @pytest.mark.asyncio
    async def test_fetch_indicators_include_topics_false(
        self, mocked_datacommons_client: Mock
    ):
        """Test basic functionality without place filtering."""
        # Arrange: Create client for the old path and mock search results
        client_under_test = DCClient(
            dc=mocked_datacommons_client, use_search_indicators_endpoint=False
        )

        # Mock search_svs to return topics and variables
        mock_search_results = {
            "test query": [
                {"SV": "dc/variable/Count_Person", "CosineScore": 0.7},
                {"SV": "dc/variable/Count_Household", "CosineScore": 0.6},
            ]
        }

        # Mock the search_svs method
        client_under_test.search_svs = AsyncMock(return_value=mock_search_results)

        # Mock topic store
        client_under_test.topic_store = Mock()
        client_under_test.topic_store.get_name.side_effect = lambda dcid: {
            "dc/variable/Count_Health": "Count of Health",
            "dc/variable/Count_Economy": "Count of Economy",
            "dc/variable/Count_Person": "Count of Persons",
            "dc/variable/Count_Household": "Count of Households",
        }.get(dcid, dcid)

        # Mock topic data
        client_under_test.topic_store.topics_by_dcid = {}

        client_under_test.topic_store.get_topic_variables.side_effect = (
            lambda dcid: {}.get(dcid, [])
        )

        # Act: Call the method
        result = await client_under_test.fetch_indicators(
            "test query", include_topics=False
        )

        # Assert: Verify the response structure
        assert "topics" in result
        assert "variables" in result
        assert "lookups" in result

        # Verify topics
        assert len(result["topics"]) == 0

        # Verify variables
        assert len(result["variables"]) == 2
        variable_dcids = [var["dcid"] for var in result["variables"]]
        assert variable_dcids == [
            "dc/variable/Count_Person",
            "dc/variable/Count_Household",
        ]

        # Verify lookups
        assert len(result["lookups"]) == 2
        assert result["lookups"]["dc/variable/Count_Household"] == "Count of Households"
        assert result["lookups"]["dc/variable/Count_Person"] == "Count of Persons"

    @pytest.mark.asyncio
    async def test_fetch_indicators_include_topics_with_places(
        self, mocked_datacommons_client: Mock
    ):
        """Test functionality with place filtering."""
        # Arrange: Create client for the old path and mock search results
        client_under_test = DCClient(
            dc=mocked_datacommons_client, use_search_indicators_endpoint=False
        )

        # Mock search_svs to return topics and variables
        mock_search_results = {
            "test query": [
                {"SV": "dc/topic/Health", "CosineScore": 0.9},
                {"SV": "dc/variable/Count_Person", "CosineScore": 0.7},
            ]
        }

        # Mock the search_svs method
        client_under_test.search_svs = AsyncMock(return_value=mock_search_results)

        # Mock topic store
        client_under_test.topic_store = Mock()
        client_under_test.topic_store.get_name.side_effect = lambda dcid: {
            "dc/topic/Health": "Health",
            "dc/variable/Count_Person": "Count of Persons",
        }.get(dcid, dcid)

        # Mock topic data
        client_under_test.topic_store.topics_by_dcid = {
            "dc/topic/Health": Mock(
                member_topics=[],
                variables=["dc/variable/Count_Person", "dc/variable/Count_Household"],
            )
        }

        # Mock variable cache to simulate data existence
        client_under_test.variable_cache = Mock()
        client_under_test.variable_cache.get.side_effect = lambda place_dcid: {
            "geoId/06": {"dc/variable/Count_Person"},  # California has Count_Person
            "geoId/36": set(),  # New York has no data
        }.get(place_dcid, set())

        # Act: Call the method with place filtering
        result = await client_under_test.fetch_indicators(
            "test query", place_dcids=["geoId/06", "geoId/36"], include_topics=True
        )

        # Assert: Verify that only variables with data are returned
        assert len(result["variables"]) == 1
        assert result["variables"][0]["dcid"] == "dc/variable/Count_Person"
        assert "places_with_data" in result["variables"][0]
        assert result["variables"][0]["places_with_data"] == ["geoId/06"]

    def test_filter_variables_by_existence(self, mocked_datacommons_client):
        """Test variable filtering by existence."""
        # Arrange: Create client for the old path and mock variable cache
        client_under_test = DCClient(
            dc=mocked_datacommons_client, use_search_indicators_endpoint=False
        )
        client_under_test.variable_cache = Mock()
        client_under_test.variable_cache.get.side_effect = lambda place_dcid: {
            "geoId/06": {"dc/variable/Count_Person", "dc/variable/Count_Household"},
            "geoId/36": {"dc/variable/Count_Person"},
        }.get(place_dcid, set())

        # Act: Filter variables
        variables = [
            "dc/variable/Count_Person",
            "dc/variable/Count_Household",
            "dc/variable/Count_Business",
        ]
        result = client_under_test._filter_variables_by_existence(
            variables, ["geoId/06", "geoId/36"]
        )

        # Assert: Verify filtering results
        assert len(result) == 2
        var_dcids = [var["dcid"] for var in result]
        assert "dc/variable/Count_Person" in var_dcids
        assert "dc/variable/Count_Household" in var_dcids
        assert "dc/variable/Count_Business" not in var_dcids

        # Verify places_with_data
        count_person = next(
            var for var in result if var["dcid"] == "dc/variable/Count_Person"
        )
        assert count_person["places_with_data"] == ["geoId/06", "geoId/36"]

    def test_filter_topics_by_existence(self, mocked_datacommons_client: Mock):
        """Test topic filtering by existence."""
        # Arrange: Create client for the old path and mock topic store
        client_under_test = DCClient(
            dc=mocked_datacommons_client, use_search_indicators_endpoint=False
        )
        client_under_test.topic_store = Mock()
        client_under_test.topic_store.topics_by_dcid = {
            "dc/topic/Health": Mock(
                member_topics=[], variables=["dc/variable/Count_Person"]
            )
        }

        # Mock variable cache
        client_under_test.variable_cache = Mock()
        client_under_test.variable_cache.get.side_effect = lambda place_dcid: {
            "geoId/06": {"dc/variable/Count_Person"},
            "geoId/36": set(),
        }.get(place_dcid, set())

        # Act: Filter topics
        topics = ["dc/topic/Health", "dc/topic/Economy"]
        result = client_under_test._filter_topics_by_existence(
            topics, ["geoId/06", "geoId/36"]
        )

        # Assert: Verify filtering results
        assert len(result) == 1
        assert result[0]["dcid"] == "dc/topic/Health"
        assert result[0]["places_with_data"] == ["geoId/06"]

    def test_filter_topics_by_existence_new(self, mocked_datacommons_client: Mock):
        """Test the new topic filtering logic which operates on SearchTopic objects."""
        # Arrange
        client = DCClient(dc=mocked_datacommons_client)
        # Mock the helper method that gets places with data for a topic
        client._get_topic_places_with_data = Mock(
            side_effect=lambda topic_dcid, _: {
                "dc/topic/Health": ["geoId/06"],  # Health exists in CA
                "dc/topic/Economy": [],  # Economy exists nowhere
            }.get(topic_dcid, [])
        )

        # Input topics
        topics_to_filter = {
            "dc/topic/Health": SearchTopic(dcid="dc/topic/Health"),
            "dc/topic/Economy": SearchTopic(dcid="dc/topic/Economy"),
        }

        # Act
        filtered_topics = client._filter_topics_by_existence_new(
            topics_to_filter, ["geoId/06", "geoId/36"]
        )

        # Assert
        # Only the 'Health' topic should remain
        assert len(filtered_topics) == 1
        assert "dc/topic/Health" in filtered_topics
        assert "dc/topic/Economy" not in filtered_topics

        # The remaining topic should have its 'places_with_data' attribute populated
        health_topic = filtered_topics["dc/topic/Health"]
        assert health_topic.places_with_data == ["geoId/06"]

    def test_get_topics_members_with_existence(self, mocked_datacommons_client: Mock):
        """Test topic filtering by existence."""
        # Arrange: Create client for the old path and mock topic store
        client_under_test = DCClient(
            dc=mocked_datacommons_client, use_search_indicators_endpoint=False
        )
        client_under_test.topic_store = Mock()
        client_under_test.topic_store.topics_by_dcid = {
            "dc/topic/Health": Mock(
                member_topics=[], variables=["dc/variable/Count_Person"]
            )
        }

        # Mock variable cache
        client_under_test.variable_cache = Mock()
        client_under_test.variable_cache.get.side_effect = lambda place_dcid: {
            "geoId/06": {"dc/variable/Count_Person"},
            "geoId/36": set(),
        }.get(place_dcid, set())

        client_under_test.topic_store = Mock()
        client_under_test.topic_store.topics_by_dcid = {
            "dc/topic/Health": Mock(
                member_topics=["dc/topic/HealthCare"],
                variables=["dc/variable/Count_Person", "dc/variable/Count_Household"],
            )
        }

        # Mock variable cache
        client_under_test.variable_cache = Mock()
        client_under_test.variable_cache.get.side_effect = lambda place_dcid: {
            "geoId/06": {"dc/variable/Count_Person"},
            "geoId/36": set(),
        }.get(place_dcid, set())

        # Act: Get members with existence filtering
        topics = [{"dcid": "dc/topic/Health"}]
        result = client_under_test._get_topics_members_with_existence(
            topics, ["geoId/06", "geoId/36"]
        )

        # Assert: Verify member filtering
        assert "dc/topic/Health" in result
        health_topic = result["dc/topic/Health"]
        assert health_topic["member_variables"] == ["dc/variable/Count_Person"]
        assert health_topic["member_topics"] == []

    @pytest.mark.asyncio
    async def test_search_entities_filters_invalid_topics(
        self, mocked_datacommons_client: Mock
    ):
        """Test that _search_entities filters out topics that don't exist in the topic store."""
        # Arrange: Create client for the old path and mock search results
        client_under_test = DCClient(
            dc=mocked_datacommons_client, use_search_indicators_endpoint=False
        )

        # Mock search_svs to return topics (some valid, some invalid) and variables
        mock_search_results = {
            "test query": [
                {"SV": "dc/topic/Health", "CosineScore": 0.9},  # Valid topic
                {
                    "SV": "dc/topic/InvalidTopic",
                    "CosineScore": 0.8,
                },  # Invalid topic (not in store)
                {"SV": "dc/topic/Economy", "CosineScore": 0.7},  # Valid topic
                {"SV": "dc/variable/Count_Person", "CosineScore": 0.6},  # Variable
            ]
        }

        # Mock the search_svs method
        client_under_test.search_svs = AsyncMock(return_value=mock_search_results)

        # Mock topic store to only contain some topics
        client_under_test.topic_store = Mock()
        client_under_test.topic_store.topics_by_dcid = {
            "dc/topic/Health": Mock(),
            "dc/topic/Economy": Mock(),
            # Note: "dc/topic/InvalidTopic" is NOT in the topic store
        }

        # Act: Call the method
        result = await client_under_test._search_vector(
            "test query", include_topics=True
        )

        # Assert: Verify that only valid topics are returned
        assert "topics" in result
        assert "variables" in result

        # Verify topics - should only include topics that exist in the topic store
        assert len(result["topics"]) == 2
        assert "dc/topic/Health" in result["topics"]
        assert "dc/topic/Economy" in result["topics"]
        assert (
            "dc/topic/InvalidTopic" not in result["topics"]
        )  # Invalid topic should be filtered out

        # Verify variables - should include all variables
        assert len(result["variables"]) == 1
        assert "dc/variable/Count_Person" in result["variables"]

    @pytest.mark.asyncio
    async def test_search_entities_with_no_topic_store(self, mocked_datacommons_client):
        """
        Test that _search_vector handles the case when topic store is None.
        """
        # Arrange: Create client and mock search results
        client_under_test = DCClient(dc=mocked_datacommons_client)

        # Mock search_svs to return topics and variables
        mock_search_results = {
            "test query": [
                {"SV": "dc/topic/Health", "CosineScore": 0.9},
                {"SV": "dc/variable/Count_Person", "CosineScore": 0.6},
            ]
        }

        # Mock the search_svs method
        client_under_test.search_svs = AsyncMock(return_value=mock_search_results)

        # Set topic store to None
        client_under_test.topic_store = None

        # Act: Call the method
        result = await client_under_test._search_vector(  # Corrected method name
            "test query", include_topics=True
        )

        # Assert: Verify that no topics are returned when topic store is None
        assert "topics" in result
        assert "variables" in result

        # Verify topics - should be empty when topic store is None
        assert len(result["topics"]) == 0

        # Verify variables - should include all variables
        assert len(result["variables"]) == 1
        assert "dc/variable/Count_Person" in result["variables"]

    @pytest.mark.asyncio
    async def test_search_entities_with_per_search_limit(
        self, mocked_datacommons_client: Mock
    ):
        """
        Test _search_vector with per_search_limit parameter.
        """
        client_under_test = DCClient(
            dc=mocked_datacommons_client, use_search_indicators_endpoint=False
        )

        # Mock search_svs to return results
        mock_search_results = {
            "test query": [
                {"SV": "Count_Person", "CosineScore": 0.8},
                {"SV": "Count_Household", "CosineScore": 0.7},
            ]
        }
        client_under_test.search_svs = AsyncMock(return_value=mock_search_results)

        result = await client_under_test._search_vector(  # Corrected method name
            "test query", include_topics=True, max_results=2
        )

        # Verify that search_svs was called with max_results=2
        client_under_test.search_svs.assert_called_once_with(
            ["test query"], skip_topics=False, max_results=2
        )

        # Should return variables (no topics since topic_store is None by default)
        assert "topics" in result
        assert "variables" in result
        assert len(result["variables"]) == 2  # Both variables should be included
        assert "Count_Person" in result["variables"]
        assert "Count_Household" in result["variables"]


class TestCreateDCClient:
    """Tests for the create_dc_client factory function."""

    @patch("datacommons_mcp.clients.DataCommonsClient")
    @patch("datacommons_mcp.clients.read_topic_cache")
    def test_create_dc_client_base_dc(
        self, mock_read_cache: Mock, mock_dc_client: Mock
    ):
        """Test base DC creation with defaults."""
        # Arrange
        with patch.dict(os.environ, {"DC_API_KEY": "test_api_key", "DC_TYPE": "base"}):
            settings = BaseDCSettings()
            mock_dc_instance = Mock()
            mock_dc_client.return_value = mock_dc_instance
            mock_read_cache.return_value = Mock()

            # Act
            result = create_dc_client(settings)

            # Assert
            assert isinstance(result, DCClient)
            assert result.dc == mock_dc_instance
            assert result.search_scope == SearchScope.BASE_ONLY
            assert result.base_index == "base_uae_mem"
            assert result.custom_index is None
            assert result.use_search_indicators_endpoint is True  # Default value
            mock_dc_client.assert_called_once_with(api_key="test_api_key")

    @patch("datacommons_mcp.clients.DataCommonsClient")
    @patch("datacommons_mcp.clients.create_topic_store")
    def test_create_dc_client_custom_dc(
        self, mock_create_store: Mock, mock_dc_client: Mock
    ):
        """Test custom DC creation with defaults."""
        # Arrange
        with patch.dict(
            os.environ,
            {
                "DC_API_KEY": "test_api_key",
                "DC_TYPE": "custom",
                "CUSTOM_DC_URL": "https://staging-datacommons-web-service-650536812276.northamerica-northeast1.run.app",
            },
        ):
            settings = CustomDCSettings()
            mock_dc_instance = Mock()
            mock_dc_client.return_value = mock_dc_instance
            mock_topic_store = Mock()
            mock_create_store.return_value = mock_topic_store

            # Act
            result = create_dc_client(settings)

            # Assert
            assert isinstance(result, DCClient)
            assert result.dc == mock_dc_instance
            assert result.search_scope == SearchScope.BASE_AND_CUSTOM
            assert result.base_index == "medium_ft"
            assert result.custom_index == "user_all_minilm_mem"
            assert (
                result.sv_search_base_url
                == "https://staging-datacommons-web-service-650536812276.northamerica-northeast1.run.app"
            )
            assert result.use_search_indicators_endpoint is True  # Default value
            # Should have called DataCommonsClient with computed api_base_url
            expected_api_url = "https://staging-datacommons-web-service-650536812276.northamerica-northeast1.run.app/core/api/v2/"
            mock_dc_client.assert_called_with(url=expected_api_url)

    @patch("datacommons_mcp.clients.DataCommonsClient")
    @patch("datacommons_mcp.clients.create_topic_store")
    def test_create_dc_client_custom_dc_uses_search_vector(
        self, mock_create_store: Mock, mock_dc_client: Mock
    ):
        """Test custom DC creation with use_search_indicators_endpoint set to false (uses search_vector)."""
        # Arrange
        with patch.dict(
            os.environ,
            {
                "DC_API_KEY": "test_api_key",
                "DC_TYPE": "custom",
                "CUSTOM_DC_URL": "https://example.com",
                "DC_USE_SEARCH_INDICATORS_ENDPOINT": "false",
            },
        ):
            settings = CustomDCSettings()
            mock_dc_instance = Mock()
            mock_dc_client.return_value = mock_dc_instance
            mock_create_store.return_value = Mock()

            # Act
            result = create_dc_client(settings)

            # Assert
            assert result.use_search_indicators_endpoint is False

    @patch("datacommons_mcp.clients.DataCommonsClient")
    def test_create_dc_client_url_computation(self, mock_dc_client):
        """Test URL computation for custom DC."""
        # Arrange
        with patch.dict(
            os.environ,
            {
                "DC_API_KEY": "test_api_key",
                "DC_TYPE": "custom",
                "CUSTOM_DC_URL": "https://example.com",  # No trailing slash
            },
        ):
            settings = CustomDCSettings()
            mock_dc_instance = Mock()
            mock_dc_client.return_value = mock_dc_instance

            # Act
            _ = create_dc_client(settings)

            # Assert
            # Should compute api_base_url by adding /core/api/v2/
            expected_api_url = "https://example.com/core/api/v2/"
            mock_dc_client.assert_called_with(url=expected_api_url)


class TestSearchIndicatorsEndpoint:
    """Tests related to the /api/nl/search-indicators endpoint logic."""

    @pytest.fixture
    def client(self, mocked_datacommons_client):
        """Provides a DCClient instance for testing."""
        return DCClient(dc=mocked_datacommons_client)

    def test_transform_response_with_mixed_results(self, client):
        """Tests transformation with a mix of topics and variables."""
        mock_api_response = {
            "queryResults": [
                {
                    "query": "test query",
                    "indexResults": [
                        {
                            "results": [
                                {
                                    "dcid": "dc/topic/Health",
                                    "name": "Health",
                                    "typeOf": "Topic",
                                    "description": "Health related indicators",
                                    "search_descriptions": ["health data"],
                                },
                                {
                                    "dcid": "Count_Person",
                                    "name": "Person Count",
                                    "typeOf": "StatisticalVariable",
                                },
                            ]
                        }
                    ],
                }
            ]
        }

        result, dcid_name_mappings = client._transform_search_indicators_response(
            mock_api_response
        )

        assert "dc/topic/Health" in result.topics
        assert "Count_Person" in result.variables
        assert (
            result.topics["dc/topic/Health"].description == "Health related indicators"
        )
        assert result.topics["dc/topic/Health"].alternate_descriptions == [
            "health data"
        ]
        assert result.variables["Count_Person"].description is None

        assert dcid_name_mappings == {
            "dc/topic/Health": "Health",
            "Count_Person": "Person Count",
        }

    def test_transform_response_with_only_variables(self, client):
        """Tests transformation with only statistical variables."""
        mock_api_response = {
            "queryResults": [
                {
                    "query": "test query",
                    "indexResults": [
                        {
                            "results": [
                                {
                                    "dcid": "Count_Person",
                                    "name": "Person Count",
                                    "typeOf": "StatisticalVariable",
                                }
                            ]
                        }
                    ],
                }
            ]
        }

        result, dcid_name_mappings = client._transform_search_indicators_response(
            mock_api_response
        )

        assert not result.topics
        assert "Count_Person" in result.variables
        assert dcid_name_mappings == {"Count_Person": "Person Count"}

    def test_transform_response_with_only_topics(self, client):
        """Tests transformation with only topics."""
        mock_api_response = {
            "queryResults": [
                {
                    "query": "test query",
                    "indexResults": [
                        {
                            "results": [
                                {
                                    "dcid": "dc/topic/Health",
                                    "name": "Health",
                                    "typeOf": "Topic",
                                }
                            ]
                        }
                    ],
                }
            ]
        }

        result, dcid_name_mappings = client._transform_search_indicators_response(
            mock_api_response
        )

        assert "dc/topic/Health" in result.topics
        assert not result.variables
        assert dcid_name_mappings == {"dc/topic/Health": "Health"}

    def test_transform_response_with_empty_results(self, client):
        """Tests transformation with an empty API response."""
        mock_api_response = {"queryResults": []}
        result, dcid_name_mappings = client._transform_search_indicators_response(
            mock_api_response
        )
        assert not result.topics
        assert not result.variables
        assert not dcid_name_mappings

    @pytest.mark.asyncio
    @patch("datacommons_mcp.clients.requests.get")
    async def test_fetch_indicators_new_constructs_request_with_topics(
        self, mock_get, client
    ):
        """Tests that _fetch_indicators_new constructs the correct request when including topics."""
        # Arrange
        mock_api_response: dict[str, Any] = {"queryResults": []}
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = mock_api_response
        mock_get.return_value = mock_response

        search_tasks = [
            SearchTask(query="health"),
            SearchTask(query="economy", place_dcids=[]),
        ]

        # Act
        await client._fetch_indicators_new(
            search_tasks=search_tasks, include_topics=True, max_results=15
        )

        # Assert
        mock_get.assert_called_once()
        call_args, call_kwargs = mock_get.call_args
        # Verify URL and headers
        assert "api/nl/search-indicators" in call_args[0]
        assert call_kwargs["headers"] == {"Content-Type": "application/json"}

        # Verify params
        params = call_kwargs["params"]
        assert params["queries"] == ["economy", "health"]  # Sorted unique queries
        assert params["limit_per_index"] == 30  # max_results * 2
        assert "include_types" not in params  # Topics are included by default

    @pytest.mark.asyncio
    @patch("datacommons_mcp.clients.requests.get")
    async def test_fetch_indicators_new_exclude_topics(self, mock_get, client):
        """Tests that include_types is set when include_topics is False."""
        # Arrange
        mock_api_response: dict[str, Any] = {"queryResults": []}
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = mock_api_response
        mock_get.return_value = mock_response

        search_tasks = [SearchTask(query="population")]

        # Act
        await client._fetch_indicators_new(
            search_tasks=search_tasks, include_topics=False, max_results=10
        )

        # Assert
        mock_get.assert_called_once()
        _, call_kwargs = mock_get.call_args
        params = call_kwargs["params"]
        assert params["include_types"] == ["StatisticalVariable"]

    @pytest.mark.asyncio
    @patch("datacommons_mcp.clients.requests.get")
    async def test_fetch_indicators_new_handles_api_error(self, mock_get, client):
        """Tests that an empty result is returned on API failure."""
        # Arrange
        mock_get.side_effect = requests.exceptions.RequestException("API Error")

        search_tasks = [SearchTask(query="test")]

        # Act
        search_result, dcid_name_mappings = await client._fetch_indicators_new(
            search_tasks=search_tasks, include_topics=True, max_results=10
        )

        # Assert
        assert not search_result.topics
        assert not search_result.variables
        assert not dcid_name_mappings

    @pytest.mark.asyncio
    @patch("datacommons_mcp.clients.requests.get")
    async def test_fetch_indicators_new_passes_response_to_transform(
        self, mock_get, client
    ):
        """Tests that the API response is correctly passed to the transform helper."""
        # Arrange
        mock_api_response = {
            "queryResults": [
                {"indexResults": [{"results": [{"dcid": "Count_Person"}]}]}
            ]
        }
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = mock_api_response
        mock_get.return_value = mock_response

        # Patch the transform method to spy on it
        with patch.object(
            client,
            "_transform_search_indicators_response",
            wraps=client._transform_search_indicators_response,
        ) as mock_transform:
            search_tasks = [SearchTask(query="population")]

            # Act
            await client._fetch_indicators_new(
                search_tasks=search_tasks, include_topics=False, max_results=10
            )

            # Assert
            mock_transform.assert_called_once_with(mock_api_response)

        mock_api_response_no_results = {"queryResults": [{"indexResults": []}]}
        result, dcid_name_mappings = client._transform_search_indicators_response(
            mock_api_response_no_results
        )
        assert not result.topics
        assert not result.variables
        assert not dcid_name_mappings

    @pytest.mark.asyncio
    @patch("datacommons_mcp.clients.requests.get")
    async def test_fetch_indicators_new_with_place_filtering(self, mock_get, client):
        """Tests that existence filtering is applied in _fetch_indicators_new."""
        # Arrange
        # Mock API response to return some initial results
        mock_api_response = {
            "queryResults": [
                {
                    "indexResults": [
                        {
                            "results": [
                                {
                                    "dcid": "Count_Person",
                                    "name": "Person Count",
                                    "typeOf": "StatisticalVariable",
                                },
                                {
                                    "dcid": "Count_Household",
                                    "name": "Household Count",
                                    "typeOf": "StatisticalVariable",
                                },
                                {
                                    "dcid": "dc/topic/Health",
                                    "name": "Health",
                                    "typeOf": "Topic",
                                },
                            ]
                        }
                    ]
                }
            ]
        }
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = mock_api_response
        mock_get.return_value = mock_response

        # Mock the underlying DC client for caching place variables
        mock_dc_response = {
            "geoId/06": ["Count_Person"],  # CA has Person
            "geoId/36": ["Count_Household"],  # NY has Household
        }
        client.dc.observation.fetch_available_statistical_variables.return_value = (
            mock_dc_response
        )

        # Mock topic store to provide member variables for the topic
        mock_topic_data = Mock()
        mock_topic_data.variables = [
            "Count_Person",
            "Count_Household",
        ]  # Health topic has two members
        mock_topic_data.member_topics = []
        client.topic_store = Mock()
        client.topic_store.topics_by_dcid = {"dc/topic/Health": mock_topic_data}
        # This mock is for the recursive topic existence check
        client.topic_store.has_variable.return_value = True

        search_tasks = [SearchTask(query="test", place_dcids=["geoId/06", "geoId/36"])]

        # Act
        # Spy on the new helper functions to ensure they are called correctly
        with (
            patch.object(
                client,
                "_filter_variables_by_existence_new",
                wraps=client._filter_variables_by_existence_new,
            ) as mock_filter_vars,
            patch.object(
                client,
                "_filter_topics_by_existence_new",
                wraps=client._filter_topics_by_existence_new,
            ) as mock_filter_topics,
        ):
            search_result, _ = await client._fetch_indicators_new(
                search_tasks=search_tasks, include_topics=True, max_results=10
            )

        # Assert
        # 1. Assert that the correct high-level filtering functions were called
        mock_filter_vars.assert_called()
        mock_filter_topics.assert_called()

        # 2. Assert the final state of the search_result object
        assert "Count_Person" in search_result.variables
        assert "Count_Household" in search_result.variables
        assert search_result.variables["Count_Person"].places_with_data == ["geoId/06"]
        assert search_result.variables["Count_Household"].places_with_data == [
            "geoId/36"
        ]
        assert "dc/topic/Health" in search_result.topics
        # 3. Assert that the topic members were also filtered correctly
        # The topic members should be filtered to only those that exist in the provided places.
        health_topic = search_result.topics["dc/topic/Health"]
        # Both Count_Person (in geoId/06) and Count_Household (in geoId/36) should be present.
        assert sorted(health_topic.member_variables) == [
            "Count_Household",
            "Count_Person",
        ]

    @pytest.mark.asyncio
    @patch("datacommons_mcp.clients.requests.get")
    async def test_fetch_indicators_new_topic_member_fetching(self, mock_get, client):
        """Tests that topic members are fetched and filtered correctly."""
        # Arrange
        mock_api_response = {
            "queryResults": [
                {
                    "indexResults": [
                        {
                            "results": [
                                {
                                    "dcid": "dc/topic/Health",
                                    "name": "Health",
                                    "typeOf": "Topic",
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = mock_api_response
        mock_get.return_value = mock_response

        # Mock topic store with member data
        mock_topic_data = Mock()
        mock_topic_data.variables = ["Count_Person", "Count_Household"]
        mock_topic_data.member_topics = ["dc/topic/HeartDisease"]
        client.topic_store = Mock()
        client.topic_store.topics_by_dcid = {"dc/topic/Health": mock_topic_data}

        search_tasks = [SearchTask(query="health")]  # No place filtering

        # Act
        search_result, _ = await client._fetch_indicators_new(
            search_tasks=search_tasks, include_topics=True, max_results=10
        )

        # Assert
        assert "dc/topic/Health" in search_result.topics
        health_topic = search_result.topics["dc/topic/Health"]
        # Without place filtering, all members should be present
        assert health_topic.member_variables == ["Count_Person", "Count_Household"]
        assert health_topic.member_topics == ["dc/topic/HeartDisease"]


@pytest.mark.asyncio
class TestSearchIndicatorsNewPath:
    """Tests for the client.search_indicators method (new path)."""

    @pytest.fixture
    def client(self, mocked_datacommons_client):
        """Provides a DCClient instance for testing."""
        return DCClient(
            dc=mocked_datacommons_client, use_search_indicators_endpoint=True
        )

    async def test_search_indicators_calls_dependencies(self, client):
        """Tests that search_indicators calls _fetch_indicators_new."""
        # Arrange
        # Mock the dependencies that will be called
        client._fetch_indicators_new = AsyncMock(
            return_value=(SearchResult(), {"Count_Person": "Person Count"})
        )
        client.fetch_entity_names = AsyncMock(return_value={})

        # Act
        await client.search_indicators(
            [SearchTask(query="population", place_dcids=["geoId/06"])],
            include_topics=False,
            max_results=10,
        )

        # Assert
        # 1. Verify _fetch_indicators_new was called correctly
        client._fetch_indicators_new.assert_awaited_once()
        call_args = client._fetch_indicators_new.call_args
        assert call_args.kwargs["include_topics"] is False
        assert call_args.kwargs["max_results"] == 10
        # Check the SearchTask object passed
        search_task = call_args.kwargs["search_tasks"][0]
        assert search_task.query == "population"
        assert search_task.place_dcids == ["geoId/06"]

        # 2. Verify fetch_entity_names was not called, as the mock SearchResult
        #    is empty and has no member DCIDs that would require a name lookup.
        client.fetch_entity_names.assert_not_awaited()

    async def test_search_indicators_formats_response(self, client):
        """Tests that search_indicators correctly formats the final SearchResponse."""
        # Arrange
        # Prepare a mock SearchResult to be returned by the underlying fetch method
        mock_search_result = SearchResult(
            topics={
                "dc/topic/Health": SearchTopic(
                    dcid="dc/topic/Health",
                    member_topics=["dc/topic/SubHealth"],
                    member_variables=["Count_Person"],
                )
            },
            variables={"Count_Person": SearchVariable(dcid="Count_Person")},
        )
        mock_dcid_names = {
            "dc/topic/Health": "Health",
            "Count_Person": "Person Count",
        }
        client._fetch_indicators_new = AsyncMock(
            return_value=(mock_search_result, mock_dcid_names)
        )
        # Mock the lookup for member entities
        client.fetch_entity_names = AsyncMock(
            return_value={"dc/topic/SubHealth": "Sub-Health Topic"}
        )

        # Act
        result = await client.search_indicators(
            [SearchTask(query="health", place_dcids=[])],
            include_topics=True,
            max_results=10,
        )

        # Assert
        assert result.status == "SUCCESS"
        assert len(result.topics) == 1
        assert result.topics[0].dcid == "dc/topic/Health"
        assert len(result.variables) == 1
        assert result.variables[0].dcid == "Count_Person"
        # Check that lookups from both sources were merged
        assert result.dcid_name_mappings == {
            "dc/topic/Health": "Health",
            "Count_Person": "Person Count",
            "dc/topic/SubHealth": "Sub-Health Topic",
        }

    async def test_search_indicators_avoids_redundant_lookups(self, client):
        """Tests that we only look up names for DCIDs we don't already have."""
        # Arrange
        # The initial API call returns names for the topic and one of its members.
        mock_search_result = SearchResult(
            topics={
                "dc/topic/Health": SearchTopic(
                    dcid="dc/topic/Health",
                    member_topics=[
                        "dc/topic/SubHealth"
                    ],  # Name not in initial response
                    member_variables=["Count_Person"],  # Name is in initial response
                )
            },
            variables={},
        )
        mock_dcid_names = {
            "dc/topic/Health": "Health",
            "Count_Person": "Person Count",
        }
        client._fetch_indicators_new = AsyncMock(
            return_value=(mock_search_result, mock_dcid_names)
        )
        # Mock the lookup for only the missing member entity
        client.fetch_entity_names = AsyncMock(
            return_value={"dc/topic/SubHealth": "Sub-Health Topic"}
        )

        # Act
        await client.search_indicators(
            [SearchTask(query="health")], include_topics=True, max_results=10
        )

        # Assert that we only called fetch_entity_names for the single missing DCID
        client.fetch_entity_names.assert_awaited_once_with(["dc/topic/SubHealth"])

    @patch("datacommons_mcp.clients.requests.get")
    async def test_fetch_indicators_new_filters_dcid_name_mappings(
        self, mock_get, client
    ):
        """
        Tests that _fetch_indicators_new correctly filters dcid_name_mappings
        to only include indicators that survive the existence filter.
        """
        # Arrange
        # 1. Mock the API response to return two variables.
        mock_api_response = {
            "queryResults": [
                {
                    "indexResults": [
                        {
                            "results": [
                                {
                                    "dcid": "Count_Person",
                                    "name": "Person Count",
                                    "typeOf": "StatisticalVariable",
                                },
                                {
                                    "dcid": "Count_Household",
                                    "name": "Household Count",
                                    "typeOf": "StatisticalVariable",
                                },
                            ]
                        }
                    ]
                }
            ]
        }
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = mock_api_response
        mock_get.return_value = mock_response

        # 2. Mock the existence check to only find data for "Count_Person".
        #    This will cause "Count_Household" to be filtered out.
        mock_dc_response = {"geoId/06": ["Count_Person"]}
        client.dc.observation.fetch_available_statistical_variables.return_value = (
            mock_dc_response
        )

        # Act
        # Directly call the method we are testing.
        search_result, dcid_name_mappings = await client._fetch_indicators_new(
            [SearchTask(query="population", place_dcids=["geoId/06"])],
            include_topics=False,
            max_results=10,
        )

        # Assert
        # The search_result should only contain the variable that was not filtered.
        assert "Count_Person" in search_result.variables
        assert "Count_Household" not in search_result.variables

        # The returned dcid_name_mappings should ONLY contain the mapping for the remaining variable.
        assert dcid_name_mappings == {"Count_Person": "Person Count"}
        assert "Count_Household" not in dcid_name_mappings
