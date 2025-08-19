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

from unittest.mock import Mock, patch

import pytest
from datacommons_client.client import DataCommonsClient
from datacommons_mcp.clients import DCClient
from datacommons_mcp.constants import SearchScope
from datacommons_mcp.data_models.observations import (
    ObservationPeriod,
    ObservationToolRequest,
)


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
            custom_index="user_all_minilm_mem"
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
            custom_index="user_all_minilm_mem"
        )

        # Assert: Verify the client is configured correctly
        assert client_under_test.search_scope == SearchScope.BASE_AND_CUSTOM
        assert client_under_test.search_indices == ["user_all_minilm_mem", "medium_ft"]

    def test_compute_search_indices_validation_custom_only_without_index(self, mocked_datacommons_client):
        """
        Test that CUSTOM_ONLY search scope without custom_index raises ValueError.
        """
        # Arrange & Act & Assert: Creating client with invalid configuration should raise ValueError
        with pytest.raises(ValueError, match="Custom index not configured but CUSTOM_ONLY search scope requested"):
            DCClient(
                dc=mocked_datacommons_client,
                search_scope=SearchScope.CUSTOM_ONLY,
                custom_index=None
            )

    def test_compute_search_indices_validation_custom_only_with_empty_index(self, mocked_datacommons_client):
        """
        Test that CUSTOM_ONLY search scope with empty custom_index raises ValueError.
        """
        # Arrange & Act & Assert: Creating client with invalid configuration should raise ValueError
        with pytest.raises(ValueError, match="Custom index not configured but CUSTOM_ONLY search scope requested"):
            DCClient(
                dc=mocked_datacommons_client,
                search_scope=SearchScope.CUSTOM_ONLY,
                custom_index=""
            )


class TestDCClientSearch:
    """Tests for the search_svs method of DCClient."""

    @pytest.mark.asyncio
    @patch('datacommons_mcp.clients.requests.post')
    async def test_search_svs_single_api_call(self, mock_post, mocked_datacommons_client):
        """
        Test that search_svs makes a single API call with comma-separated indices.
        """
        # Arrange: Create client and mock response
        client_under_test = DCClient(
            dc=mocked_datacommons_client,
            search_scope=SearchScope.BASE_AND_CUSTOM,
            base_index="medium_ft",
            custom_index="user_all_minilm_mem"
        )
        
        mock_response = Mock()
        mock_response.json.return_value = {
            "queryResults": {
                "test query": {
                    "SV": ["var1", "var2"],
                    "CosineScore": [0.8, 0.6]
                }
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
            {"SV": "var2", "CosineScore": 0.6}
        ]

    @pytest.mark.asyncio
    @patch('datacommons_mcp.clients.requests.post')
    async def test_search_svs_skip_topics(self, mock_post, mocked_datacommons_client):
        """
        Test that search_svs respects the skip_topics parameter.
        """
        # Arrange: Create client and mock response
        client_under_test = DCClient(dc=mocked_datacommons_client)
        
        mock_response = Mock()
        mock_response.json.return_value = {
            "queryResults": {
                "test query": {
                    "SV": ["var1"],
                    "CosineScore": [0.8]
                }
            }
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        # Act: Call search_svs with skip_topics=True
        await client_under_test.search_svs(["test query"], skip_topics=True)

        # Assert: Verify skip_topics parameter is included in API call
        call_args = mock_post.call_args
        assert "skip_topics=true" in call_args[0][0]


class TestDCClientObservations:
    """Tests for the observation-fetching methods of DCClient."""

    @pytest.mark.asyncio
    async def test_fetch_obs_single_place(self, mocked_datacommons_client):
        """
        Verifies that fetch_obs calls the correct underlying method for a single place query.
        """
        # Arrange: Create an instance of our wrapper client.
        # Its self.dc attribute will be the mocked_datacommons_client.
        client_under_test = DCClient(dc=mocked_datacommons_client)
        request = ObservationToolRequest(
            variable_dcid="var1",
            place_dcid="place1",
            observation_period=ObservationPeriod.LATEST,
        )

        # Act: Call the method on our wrapper client.
        await client_under_test.fetch_obs(request)

        # Assert: Verify that our wrapper correctly called the `fetch` method
        # on the underlying (mocked) datacommons_client instance.
        mocked_datacommons_client.observation.fetch.assert_called_once_with(
            variable_dcids="var1",
            entity_dcids="place1",
            date=ObservationPeriod.LATEST,
            filter_facet_ids=None,
        )

    @pytest.mark.asyncio
    async def test_fetch_obs_child_places(self, mocked_datacommons_client):
        """
        Verifies that fetch_obs calls the correct underlying method for a child place query.
        """
        # Arrange: Create an instance of our wrapper client.
        client_under_test = DCClient(dc=mocked_datacommons_client)
        request = ObservationToolRequest(
            variable_dcid="var1",
            place_dcid="parent_place",
            child_place_type="County",
            observation_period=ObservationPeriod.LATEST,
        )

        # Act: Call the method on our wrapper client.
        await client_under_test.fetch_obs(request)

        # Assert: Verify that our wrapper correctly called the `fetch_observations_by_entity_type`
        # method on the underlying (mocked) datacommons_client instance.
        mocked_datacommons_client.observation.fetch_observations_by_entity_type.assert_called_once_with(
            variable_dcids="var1",
            parent_entity="parent_place",
            entity_type="County",
            date=ObservationPeriod.LATEST,
            filter_facet_ids=None,
        )
