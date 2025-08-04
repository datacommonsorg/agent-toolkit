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


class TestDCClientObservations:
    """Tests for the observation-fetching methods of DCClient."""

    @pytest.mark.asyncio
    async def test_fetch_obs_single_place(self, mocked_datacommons_client):
        """
        Verifies that fetch_obs calls the correct underlying method for a single place query.
        """
        # Arrange: Create an instance of our wrapper client.
        # Its self.dc attribute will be the mocked_datacommons_client.
        client_under_test = DCClient(api_key="fake_key")
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
        client_under_test = DCClient(api_key="fake_key")
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
