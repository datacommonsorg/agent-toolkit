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
from unittest.mock import AsyncMock, Mock, patch

import pytest
from datacommons_client.client import DataCommonsClient
from datacommons_mcp.clients import SURFACE_HEADER_VALUE, DCClient, create_dc_client
from datacommons_mcp.data_models.enums import SearchScope
from datacommons_mcp.data_models.observations import (
    ObservationDateType,
    ObservationRequest,
)
from datacommons_mcp.data_models.search import (
    NodeInfo,
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
        client_under_test = DCClient(dc=mocked_datacommons_client)

        # Mock search_svs to return topics and variables
        mock_search_results = {
            "test query": [
                {"SV": "dc/topic/Health", "CosineScore": 0.9},
                {"SV": "dc/topic/Economy", "CosineScore": 0.8},
                {"SV": "dc/variable/Count_Person", "CosineScore": 0.7},
                {"SV": "dc/variable/Count_Household", "CosineScore": 0.6},
            ]
        }

        # Mock the _call_search_indicators_temp method
        client_under_test._call_search_indicators_temp = AsyncMock(
            return_value=mock_search_results
        )

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
        client_under_test = DCClient(dc=mocked_datacommons_client)

        # Mock search_svs to return topics and variables
        mock_search_results = {
            "test query": [
                {"SV": "dc/variable/Count_Person", "CosineScore": 0.7},
                {"SV": "dc/variable/Count_Household", "CosineScore": 0.6},
            ]
        }

        # Mock the _call_search_indicators_temp method
        client_under_test._call_search_indicators_temp = AsyncMock(
            return_value=mock_search_results
        )

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
        client_under_test = DCClient(dc=mocked_datacommons_client)

        # Mock search_svs to return topics and variables
        mock_search_results = {
            "test query": [
                {"SV": "dc/topic/Health", "CosineScore": 0.9},
                {"SV": "dc/variable/Count_Person", "CosineScore": 0.7},
            ]
        }

        # Mock the _call_search_indicators_temp method
        client_under_test._call_search_indicators_temp = AsyncMock(
            return_value=mock_search_results
        )

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
                member_variables=[
                    "dc/variable/Count_Person",
                    "dc/variable/Count_Household",
                ],
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
        client_under_test = DCClient(dc=mocked_datacommons_client)
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
        client_under_test = DCClient(dc=mocked_datacommons_client)
        client_under_test.topic_store = Mock()
        client_under_test.topic_store.topics_by_dcid = {
            "dc/topic/Health": Mock(
                member_topics=[], member_variables=["dc/variable/Count_Person"]
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

    def test_get_topics_members_with_existence(self, mocked_datacommons_client: Mock):
        """Test topic filtering by existence."""
        # Arrange: Create client for the old path and mock topic store
        client_under_test = DCClient(dc=mocked_datacommons_client)
        client_under_test.topic_store = Mock()
        client_under_test.topic_store.topics_by_dcid = {
            "dc/topic/Health": Mock(
                member_topics=["dc/topic/HealthCare"],
                member_variables=[
                    "dc/variable/Count_Person",
                    "dc/variable/Count_Household",
                ],
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
            topics, include_topics=True, place_dcids=["geoId/06", "geoId/36"]
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
        client_under_test = DCClient(dc=mocked_datacommons_client)

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

        # Mock the _call_search_indicators_temp method
        client_under_test._call_search_indicators_temp = AsyncMock(
            return_value=mock_search_results
        )

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

        # Mock the _call_search_indicators_temp method
        client_under_test._call_search_indicators_temp = AsyncMock(
            return_value=mock_search_results
        )

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
        client_under_test = DCClient(dc=mocked_datacommons_client)

        # Mock search_svs to return results
        mock_search_results = {
            "test query": [
                {"SV": "Count_Person", "CosineScore": 0.8},
                {"SV": "Count_Household", "CosineScore": 0.7},
            ]
        }
        client_under_test._call_search_indicators_temp = AsyncMock(
            return_value=mock_search_results
        )

        result = await client_under_test._search_vector(  # Corrected method name
            "test query", include_topics=True, max_results=2
        )

        # Verify that _call_search_indicators_temp was called with max_results=2
        client_under_test._call_search_indicators_temp.assert_awaited_once_with(
            queries=["test query"], max_results=2
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
    @patch("datacommons_mcp.clients.read_topic_caches")
    def test_create_dc_client_base_dc(
        self, mock_read_caches: Mock, mock_dc_client: Mock
    ):
        """Test base DC creation with defaults."""
        # Arrange
        with patch.dict(os.environ, {"DC_API_KEY": "test_api_key", "DC_TYPE": "base"}):
            settings = BaseDCSettings()
            mock_dc_instance = Mock()
            mock_dc_client.return_value = mock_dc_instance
            mock_read_caches.return_value = Mock()

            # Act
            result = create_dc_client(settings)

            # Assert
            assert isinstance(result, DCClient)
            assert result.dc == mock_dc_instance
            assert result.search_scope == SearchScope.BASE_ONLY
            assert result.base_index == "base_uae_mem"
            assert result.custom_index is None
            mock_dc_client.assert_called_with(
                api_key="test_api_key",
                surface_header_value=SURFACE_HEADER_VALUE,
            )

    @patch("datacommons_mcp.clients.DataCommonsClient")
    @patch("datacommons_mcp.clients.create_topic_store")
    def test_create_dc_client_custom_dc(
        self, mock_create_store: Mock, mock_dc_client: Mock
    ):
        """Test custom DC creation with defaults."""
        # Arrange
        env_vars = {
            "DC_API_KEY": "test_api_key",
            "DC_TYPE": "custom",
            "CUSTOM_DC_URL": "https://staging-datacommons-web-service-650536812276.northamerica-northeast1.run.app",
        }
        with patch.dict(os.environ, env_vars):
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
            # Should have called DataCommonsClient with computed api_base_url
            expected_api_url = "https://staging-datacommons-web-service-650536812276.northamerica-northeast1.run.app/core/api/v2/"
            mock_dc_client.assert_called_with(
                url=expected_api_url,
                surface_header_value=SURFACE_HEADER_VALUE,
            )

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
            mock_dc_client.assert_called_with(
                url=expected_api_url,
                surface_header_value=SURFACE_HEADER_VALUE,
            )

    @patch("datacommons_mcp.clients.DataCommonsClient")
    @patch("datacommons_mcp.clients._create_base_topic_store")
    @patch("datacommons_mcp.clients.create_topic_store")
    @pytest.mark.parametrize(
        "test_case",
        [
            pytest.param(
                {
                    "dc_type": "base",
                    "env_vars": {"DC_API_KEY": "test_api_key", "DC_TYPE": "base"},
                    "expected_scope": SearchScope.BASE_ONLY,
                    "should_create_base": True,
                    "should_create_custom": False,
                    "should_merge": False,
                },
                id="base_only_scope_creates_only_base_topic_store",
            ),
            pytest.param(
                {
                    "dc_type": "custom",
                    "env_vars": {
                        "DC_API_KEY": "test_api_key",
                        "DC_TYPE": "custom",
                        "CUSTOM_DC_URL": "https://example.com",
                        "DC_ROOT_TOPIC_DCIDS": "topic1,topic2",
                        "DC_SEARCH_SCOPE": "custom_only",
                    },
                    "expected_scope": SearchScope.CUSTOM_ONLY,
                    "should_create_base": False,
                    "should_create_custom": True,
                    "should_merge": False,
                },
                id="custom_only_scope_creates_only_custom_topic_store",
            ),
            pytest.param(
                {
                    "dc_type": "custom",
                    "env_vars": {
                        "DC_API_KEY": "test_api_key",
                        "DC_TYPE": "custom",
                        "CUSTOM_DC_URL": "https://example.com",
                        "DC_ROOT_TOPIC_DCIDS": "topic1,topic2",
                    },
                    "expected_scope": SearchScope.BASE_AND_CUSTOM,
                    "should_create_base": True,
                    "should_create_custom": True,
                    "should_merge": True,
                },
                id="base_and_custom_scope_creates_and_merges_both_topic_stores",
            ),
        ],
    )
    def test_create_dc_client_search_scope_topic_stores(
        self,
        mock_create_store: Mock,
        mock_create_base_store: Mock,
        mock_dc_client: Mock,
        test_case: dict,
    ):
        """Test that topic store creation calls match search scope."""
        # Arrange
        env_vars = test_case["env_vars"]
        with patch.dict(os.environ, env_vars):
            settings = (
                BaseDCSettings()
                if test_case["dc_type"] == "base"
                else CustomDCSettings()
            )
            mock_dc_instance = Mock()
            mock_dc_client.return_value = mock_dc_instance
            mock_custom_store = Mock()
            mock_base_store = Mock()
            mock_create_store.return_value = mock_custom_store
            mock_create_base_store.return_value = mock_base_store

            # Act
            result = create_dc_client(settings)

            # Assert
            assert isinstance(result, DCClient)
            assert result.search_scope == test_case["expected_scope"]

            # Verify base topic store creation
            if test_case["should_create_base"]:
                mock_create_base_store.assert_called_once_with(settings)
            else:
                mock_create_base_store.assert_not_called()

            # Verify custom topic store creation
            if test_case["should_create_custom"]:
                mock_create_store.assert_called_once_with(
                    ["topic1", "topic2"], mock_dc_instance
                )
            else:
                mock_create_store.assert_not_called()

            # Verify store merging
            if test_case["should_merge"]:
                mock_custom_store.merge.assert_called_once_with(mock_base_store)
            else:
                mock_custom_store.merge.assert_not_called()


class TestFetchEntityInfos:
    """Test the fetch_entity_infos method."""

    @pytest.mark.asyncio
    async def test_fetch_entity_infos(self):
        """Test successful fetch of entity information."""

        # Mock data - simple dict from dcid to name and typeOf
        mock_data = {
            "geoId/06": {"name": "California", "typeOf": ["State"]},
            "country/USA": {"name": "United States", "typeOf": ["Country"]},
        }

        # Mock the underlying DC client
        mock_dc = Mock()
        mock_response = Mock()
        mock_dc.node.fetch_property_values.return_value = mock_response

        # Mock the extract_connected_nodes method for names
        def mock_extract_connected_nodes(dcid, property_name):
            if property_name == "name" and dcid in mock_data:
                return [Mock(value=mock_data[dcid]["name"])]
            return []

        # Mock the extract_connected_dcids method for types
        def mock_extract_connected_dcids(dcid, property_name):
            if property_name == "typeOf" and dcid in mock_data:
                return mock_data[dcid]["typeOf"]
            return []

        mock_response.extract_connected_nodes.side_effect = mock_extract_connected_nodes
        mock_response.extract_connected_dcids.side_effect = mock_extract_connected_dcids

        client = DCClient(dc=mock_dc)
        result = await client.fetch_entity_infos(["geoId/06", "country/USA"])

        # Verify the entire result
        expected_result = {
            "geoId/06": NodeInfo(name="California", typeOf=["State"]),
            "country/USA": NodeInfo(name="United States", typeOf=["Country"]),
        }
        assert result == expected_result

        # Verify the underlying methods were called
        mock_dc.node.fetch_property_values.assert_called_once_with(
            node_dcids=["geoId/06", "country/USA"], properties=["name", "typeOf"]
        )
