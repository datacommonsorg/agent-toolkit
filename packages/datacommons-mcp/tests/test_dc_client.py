from unittest.mock import Mock, patch

import pytest
from datacommons_client.client import DataCommonsClient
from datacommons_mcp.clients import DCClient
from datacommons_mcp.data_models.observations import (
    ObservationPeriod,
    ObservationToolRequest,
)


@pytest.fixture
def mock_dc_api_client():
    """Fixture to mock the underlying DataCommonsClient."""
    with patch("datacommons_mcp.clients.DataCommonsClient") as mock_client_constructor:
        mock_instance = Mock(spec=DataCommonsClient)
        mock_client_constructor.return_value = mock_instance
        yield mock_instance


class TestDCClient:
    def test_fetch_obs_single_place(self, mock_dc_api_client):
        client = DCClient(api_key="fake_key")
        request = ObservationToolRequest(
            variable_dcid="var1",
            place_dcid="place1",
            observation_period=ObservationPeriod.LATEST,
        )
        client.fetch_obs(request)
        mock_dc_api_client.observation.fetch.assert_called_once_with(
            variable_dcids="var1",
            entity_dcids="place1",
            date=ObservationPeriod.LATEST,
            filter_facet_ids=None,
        )

    def test_fetch_obs_child_places(self, mock_dc_api_client):
        client = DCClient(api_key="fake_key")
        request = ObservationToolRequest(
            variable_dcid="var1",
            place_dcid="parent_place",
            child_place_type="County",
            observation_period=ObservationPeriod.LATEST,
        )
        client.fetch_obs(request)
        mock_dc_api_client.observation.fetch_observations_by_entity_type.assert_called_once_with(
            variable_dcids="var1",
            parent_entity="parent_place",
            entity_type="County",
            date=ObservationPeriod.LATEST,
            filter_facet_ids=None,
        )
