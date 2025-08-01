from unittest.mock import Mock

import pytest
from datacommons_client.models.observation import Facet, Observation, OrderedFacet
from datacommons_mcp.clients import MultiDCClient
from datacommons_mcp.data_models.observations import (
    DateRange,
    ObservationApiResponse,
    ObservationToolResponse,
)


class TestMultiDCClient:
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
        facets = {"f1": Facet(), "f2": Facet()}
        return ObservationApiResponse(data, facets)

    def test_integrate_observation_initial_data(self, mock_api_response):
        response = ObservationToolResponse()
        MultiDCClient._integrate_observation_response(
            response, mock_api_response, "dc1"
        )

        assert "place1" in response.place_data
        place_data = response.place_data["place1"]
        assert "var1" in place_data.variable_series

        var_series = place_data.variable_series["var1"]
        assert var_series.source_metadata.facetId == "f1"
        assert len(var_series.observations) == 2
        assert len(var_series.alternative_sources) == 1
        assert var_series.alternative_sources[0].facetId == "f2"

    def test_integrate_observation_alternative_sources(self, mock_api_response):
        response = ObservationToolResponse()
        # Pre-populate with some data
        response.place_data["place1"] = Mock(
            variable_series={"var1": Mock(alternative_sources=[])}
        )

        MultiDCClient._integrate_observation_response(
            response, mock_api_response, "dc1"
        )

        # Check that the new sources were appended
        var_series = response.place_data["place1"].variable_series["var1"]
        assert len(var_series.alternative_sources) == 2  # 2 new sources added

    def test_integrate_observation_with_date_filter(self, mock_api_response):
        response = ObservationToolResponse()
        date_filter = DateRange(start_date="2023", end_date="2023")

        MultiDCClient._integrate_observation_response(
            response, mock_api_response, "dc1", date_filter=date_filter
        )

        var_series = response.place_data["place1"].variable_series["var1"]
        # Only the observation for "2023" should have been selected
        assert len(var_series.observations) == 1
        assert var_series.observations[0].value == 2
