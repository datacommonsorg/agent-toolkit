from unittest.mock import AsyncMock, Mock

import pytest
from datacommons_client.models.observation import Facet, Observation, OrderedFacet
from datacommons_mcp.clients import DCClient, MultiDCClient
from datacommons_mcp.data_models.observations import (
    DateRange,
    ObservationApiResponse,
    ObservationToolRequest,
    ObservationToolResponse,
)


@pytest.mark.asyncio
class TestMultiDCClient:
    @pytest.fixture
    def mock_base_dc(self):
        """Fixture for a mocked base DCClient."""
        client = Mock(spec=DCClient)
        client.fetch_obs = AsyncMock()
        client.dc_name = "Data Commons"
        return client

    @pytest.fixture
    def mock_custom_dc(self):
        """Fixture for a mocked custom DCClient."""
        client = Mock(spec=DCClient)
        client.fetch_obs = AsyncMock()
        client.dc_name = "Custom DC"
        return client

    @pytest.fixture
    def mock_api_response(self):
        # Data Structure: {variable: {place: facet_data}}
        data = {
            "var1": {
                "place1": Mock(
                    orderedFacets=[
                        OrderedFacet(
                            facetId="f1",
                            earliestDate="2022",
                            latestDate="2023",
                            obsCount=2,
                            observations=[
                                Observation(date="2022", value=1),
                                Observation(date="2023", value=2),
                            ],
                        ),
                        OrderedFacet(
                            facetId="f2",
                            earliestDate="2020",
                            latestDate="2021",
                            obsCount=3,
                            observations=[
                                Observation(date="2020", value=3),
                                Observation(date="2020", value=3),
                                Observation(date="2021", value=4),
                            ],
                        ),
                    ]
                )
            }
        }
        facets = {
            "f1": Facet(import_name="source1"),
            "f2": Facet(import_name="source2"),
        }
        return ObservationApiResponse(data, facets)

    async def test_fetch_obs_base_only(self, mock_base_dc, mock_api_response):
        """Tests that fetch_obs works correctly with only a base DC."""
        mock_base_dc.fetch_obs.return_value = mock_api_response

        multi_client = MultiDCClient(base_dc=mock_base_dc, custom_dc=None)
        request = Mock(spec=ObservationToolRequest, date_filter=None)

        response = await multi_client.fetch_obs(request)

        mock_base_dc.fetch_obs.assert_awaited_once_with(request)
        assert "place1" in response.place_data
        var_series = response.place_data["place1"].variable_series["var1"]
        assert var_series.source_metadata.importName == "source1"
        assert len(var_series.alternative_sources) == 1

    async def test_fetch_obs_merges_custom_and_base(self, mock_base_dc, mock_custom_dc):
        """Tests that results from custom and base DCs are merged correctly."""

        custom_data = {
            "place1": Mock(
                orderedFacets=[
                    OrderedFacet(
                        "f_custom",
                        "2025",
                        "2025",
                        1,
                        [Observation(date="2025", value=100)],
                    )
                ]
            )
        }

        custom_facets = {"f_custom": Facet(importName="custom_source")}
        mock_custom_dc.fetch_obs.return_value = ObservationApiResponse(
            custom_data, custom_facets
        )

        # Base DC has a different facet 'f_base' that doesn't overlap with custom
        base_data = {"var1": {"place1": Mock(orderedFacets=[])}}
        base_facets = {}
        mock_base_dc.fetch_obs.return_value = ObservationApiResponse(
            base_data, base_facets
        )

        multi_client = MultiDCClient(base_dc=mock_base_dc, custom_dc=mock_custom_dc)
        request = Mock(spec=ObservationToolRequest, date_filter=None)

        await multi_client.fetch_obs(request)

        mock_custom_dc.fetch_obs.assert_awaited_once_with(request)
        mock_base_dc.fetch_obs.assert_awaited_once_with(request)

    def test_integrate_observation_initial_data(self, mock_api_response):
        response = ObservationToolResponse()
        MultiDCClient._integrate_observation_response(
            response, mock_api_response, "dc1"
        )

        assert "place1" in response.place_data
        place_data = response.place_data["place1"]
        assert "var1" in place_data.variable_series

        var_series = place_data.variable_series["var1"]
        assert var_series.source_metadata.facet_id == "f1"
        assert len(var_series.observations) == 2
        assert len(var_series.alternative_sources) == 1
        assert var_series.alternative_sources[0].facet_id == "f2"

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
