import calendar
from unittest.mock import AsyncMock, Mock

import pytest
from datacommons_client.models.observation import Observation, OrderedFacet

# Import the classes and functions to be tested
from datacommons_mcp.data_models.observations import (
    DateRange,
    InvalidDateFormatError,
    NoDataFoundError,
    ObservationPeriod,
    ObservationToolRequest,
    ObservationToolResponse,
    SourceMetadata,
    VariableSeries,
    filter_by_date,
    parse_date_interval,
)

# --- Tests for Utility Functions ---


class TestParseDateInterval:
    def test_yyyy_format(self):
        assert parse_date_interval("2023") == ("2023-01-01", "2023-12-31")

    def test_yyyymm_format(self):
        # Non-leap year
        assert parse_date_interval("2023-02") == ("2023-02-01", "2023-02-28")
        # Leap year
        assert parse_date_interval("2024-02") == ("2024-02-01", "2024-02-29")

    def test_yyyymmdd_format(self):
        assert parse_date_interval("2023-07-15") == ("2023-07-15", "2023-07-15")

    def test_invalid_format_raises_error(self):
        with pytest.raises(InvalidDateFormatError):
            parse_date_interval("not-a-date")
        with pytest.raises(InvalidDateFormatError):
            parse_date_interval("2023-13-01")  # Invalid month


class TestFilterByDate:
    @pytest.fixture
    def observations(self) -> list[Observation]:
        return [
            Observation(date="2022", value=1),
            Observation(date="2023-05", value=2),
            Observation(date="2024-01-15", value=3),
            Observation(date="2024-07", value=4),
        ]

    def test_no_filter(self, observations):
        assert len(filter_by_date(observations, None)) == 4

    def test_filter_contains_fully(self, observations):
        date_filter = DateRange(start_date="2023", end_date="2024")
        result = filter_by_date(observations, date_filter)
        assert len(result) == 3
        assert {obs.value for obs in result} == {2, 3, 4}

    def test_filter_partial_overlap_excluded(self, observations):
        # Observation for "2022" (Jan 1 to Dec 31) is not fully contained
        date_filter = DateRange(start_date="2022-06-01", end_date="2023-06-01")
        result = filter_by_date(observations, date_filter)
        assert len(result) == 1
        assert result[0].value == 2  # Only 2023-05 is fully contained

    def test_empty_result(self, observations):
        date_filter = DateRange(start_date="2025", end_date="2026")
        assert len(filter_by_date(observations, date_filter)) == 0


# --- Tests for ObservationToolRequest ---


@pytest.mark.asyncio
class TestObservationToolRequest:
    @pytest.fixture
    def mock_client(self, mocker):
        client = Mock()
        client.search_svs = AsyncMock()
        client.base_dc.search_places = AsyncMock()
        return client

    async def test_from_tool_inputs_validation_errors(self, mock_client):
        # Missing variable
        with pytest.raises(
            ValueError, match="Specify either 'variable_desc' or 'variable_dcid'"
        ):
            await ObservationToolRequest.from_tool_inputs(mock_client, place_name="USA")

        # Missing place
        with pytest.raises(
            ValueError, match="Specify either 'place_name' or 'place_dcid'"
        ):
            await ObservationToolRequest.from_tool_inputs(
                mock_client, variable_dcid="var1"
            )

        # Incomplete date range
        with pytest.raises(
            ValueError, match="Both 'start_date' and 'end_date' are required"
        ):
            await ObservationToolRequest.from_tool_inputs(
                mock_client, variable_dcid="var1", place_name="USA", start_date="2022"
            )

    async def test_from_tool_inputs_with_dcids(self, mock_client):
        request = await ObservationToolRequest.from_tool_inputs(
            mock_client, variable_dcid="var1", place_dcid="country/USA"
        )
        assert request.variable_dcid == "var1"
        assert request.place_dcid == "country/USA"
        assert request.observation_period == ObservationPeriod.LATEST
        mock_client.search_svs.assert_not_called()
        mock_client.base_dc.search_places.assert_not_called()

    async def test_from_tool_inputs_with_resolution_success(self, mock_client):
        mock_client.search_svs.return_value = {"pop": {"SV": "Count_Person"}}
        mock_client.base_dc.search_places.return_value = {"USA": "country/USA"}

        request = await ObservationToolRequest.from_tool_inputs(
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
        assert request.date_filter.start_date == "2022"

    async def test_from_tool_inputs_resolution_failure(self, mock_client):
        mock_client.search_svs.return_value = {}  # No variable found
        with pytest.raises(NoDataFoundError, match="No statistical variables found"):
            await ObservationToolRequest.from_tool_inputs(
                mock_client, variable_desc="invalid", place_name="USA"
            )

        mock_client.search_svs.return_value = {"pop": {"SV": "Count_Person"}}
        mock_client.base_dc.search_places.return_value = {}  # No place found
        with pytest.raises(NoDataFoundError, match="No place found"):
            await ObservationToolRequest.from_tool_inputs(
                mock_client, variable_desc="pop", place_name="invalid"
            )


# --- Tests for ObservationToolResponse ---


class TestObservationToolResponse:
    @pytest.fixture
    def mock_api_response(self):
        # Data Structure: {variable: {place: facet_data}}
        data = {
            "var1": {
                "place1": Mock(
                    orderedFacets=[
                        OrderedFacet(
                            "f1",
                            "2022",
                            "2023",
                            2,
                            [Observation("2022", 1), Observation("2023", 2)],
                        ),
                        OrderedFacet(
                            "f2",
                            "2020",
                            "2021",
                            2,
                            [Observation("2020", 3), Observation("2021", 4)],
                        ),
                    ]
                )
            }
        }
        facets = {"f1": MockFacetMetadata(), "f2": MockFacetMetadata()}
        return MockApiResponse(data, facets)

    def test_merge_initial_data(self, mock_api_response):
        response = ObservationToolResponse()
        response.merge_fetch_observation_response(mock_api_response, "dc1")

        assert "place1" in response.place_data
        place_data = response.place_data["place1"]
        assert "var1" in place_data.variable_series

        var_series = place_data.variable_series["var1"]
        assert var_series.source_metadata.facetId == "f1"
        assert len(var_series.observations) == 2
        assert len(var_series.alternative_sources) == 1
        assert var_series.alternative_sources[0].facetId == "f2"

    def test_merge_alternative_sources(self, mock_api_response):
        response = ObservationToolResponse()
        # Pre-populate with some data
        response.place_data["place1"] = Mock(
            variable_series={"var1": Mock(alternative_sources=[])}
        )

        response.merge_fetch_observation_response(mock_api_response, "dc1")

        # Check that the new sources were appended
        var_series = response.place_data["place1"].variable_series["var1"]
        assert len(var_series.alternative_sources) == 2  # 2 new sources added

    def test_merge_with_date_filter(self, mock_api_response):
        response = ObservationToolResponse()
        date_filter = DateRange(start_date="2023", end_date="2023")

        response.merge_fetch_observation_response(
            mock_api_response, "dc1", date_filter=date_filter
        )

        var_series = response.place_data["place1"].variable_series["var1"]
        # Only the observation for "2023" should have been selected
        assert len(var_series.observations) == 1
        assert var_series.observations[0].value == 2
