from unittest.mock import AsyncMock, Mock

import pytest
from datacommons_mcp.data_models.observations import ObservationPeriod
from datacommons_mcp.exceptions import NoDataFoundError
from datacommons_mcp.services import _build_observation_request


@pytest.mark.asyncio
class TestBuildObservationRequest:
    @pytest.fixture
    def mock_client(self):
        client = Mock()
        client.search_svs = AsyncMock()
        client.base_dc.search_places = AsyncMock()
        return client

    async def test_validation_errors(self, mock_client):
        # Missing variable
        with pytest.raises(
            ValueError, match="Specify either 'variable_desc' or 'variable_dcid'"
        ):
            await _build_observation_request(mock_client, place_name="USA")

        # Missing place
        with pytest.raises(
            ValueError, match="Specify either 'place_name' or 'place_dcid'"
        ):
            await _build_observation_request(mock_client, variable_dcid="var1")

        # Incomplete date range
        with pytest.raises(
            ValueError, match="Both 'start_date' and 'end_date' are required"
        ):
            await _build_observation_request(
                mock_client, variable_dcid="var1", place_name="USA", start_date="2022"
            )

    async def test_with_dcids(self, mock_client):
        request = await _build_observation_request(
            mock_client, variable_dcid="var1", place_dcid="country/USA"
        )
        assert request.variable_dcid == "var1"
        assert request.place_dcid == "country/USA"
        assert request.observation_period == ObservationPeriod.LATEST
        mock_client.search_svs.assert_not_called()
        mock_client.base_dc.search_places.assert_not_called()

    async def test_with_resolution_success(self, mock_client):
        mock_client.search_svs.return_value = {"pop": {"SV": "Count_Person"}}
        mock_client.base_dc.search_places.return_value = {"USA": "country/USA"}

        request = await _build_observation_request(
            mock_client,
            variable_desc="pop",
            place_name="USA",
            start_date="2022",
            end_date="2023",
        )

        mock_client.search_svs.assert_awaited_once_with(["pop"])
        mock_client.base_dc.search_places.assert_awaited_once_with(["USA"])
        assert request.variable_dcid == "Count_Person"
        assert request.place_dcid == "country/USA"
        assert request.observation_period == ObservationPeriod.ALL
        assert request.date_filter.start_date == "2022-01-01"
        assert request.date_filter.end_date == "2023-12-31"

    async def test_resolution_failure(self, mock_client):
        mock_client.search_svs.return_value = {}  # No variable found
        with pytest.raises(
            NoDataFoundError, match="NoDataFoundError: No statistical variables found"
        ):
            await _build_observation_request(
                mock_client, variable_desc="invalid", place_name="USA"
            )

        mock_client.search_svs.return_value = {"pop": {"SV": "Count_Person"}}
        mock_client.base_dc.search_places.return_value = {}  # No place found
        with pytest.raises(NoDataFoundError, match="NoDataFoundError: No place found"):
            await _build_observation_request(
                mock_client, variable_desc="pop", place_name="invalid"
            )
