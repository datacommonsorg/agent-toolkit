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

from unittest.mock import AsyncMock, Mock

import pytest
from datacommons_mcp.clients import DCClient, MultiDCClient
from datacommons_mcp.data_models.observations import (
    DateRange,
    ObservationApiResponse,
    ObservationToolRequest,
    ObservationToolResponse,
    SourceMetadata,
    VariableSeries,
)


@pytest.fixture
def mock_base_dc():
    """Fixture for a mocked base DCClient."""
    client = Mock(spec=DCClient)
    client.fetch_obs = AsyncMock()
    client.dc_name = "Data Commons"
    return client


@pytest.fixture
def mock_custom_dc():
    """Fixture for a mocked custom DCClient."""
    client = Mock(spec=DCClient)
    client.fetch_obs = AsyncMock()
    client.dc_name = "Custom DC"
    return client


class TestMultiDCClientObservations:
    @pytest.fixture
    def mock_api_response(self):
        # Data Structure: {variable: {place: facet_data}}
        # This fixture creates a raw dictionary that mimics the JSON response
        # from the Data Commons API. The ObservationApiResponse class is
        # designed to parse this dictionary.
        raw_response_data = {
            "byVariable": {
                "var1": {
                    "byEntity": {
                        "place1": {
                            "orderedFacets": [
                                {
                                    "facetId": "f1",
                                    "earliestDate": "2022",
                                    "latestDate": "2023",
                                    "obsCount": 2,
                                    "observations": [
                                        {"date": "2022", "value": 1},
                                        {"date": "2023", "value": 2},
                                    ],
                                },
                                {
                                    "facetId": "f2",
                                    "earliestDate": "2020",
                                    "latestDate": "2021",
                                    "obsCount": 3,
                                    "observations": [
                                        {"date": "2020", "value": 3},
                                        {"date": "2020", "value": 3},
                                        {"date": "2021", "value": 4},
                                    ],
                                },
                            ]
                        }
                    }
                }
            },
            "facets": {
                "f1": {"importName": "source1"},
                "f2": {"importName": "source2"},
            },
        }
        return ObservationApiResponse.model_validate(raw_response_data)

    @pytest.mark.asyncio
    async def test_fetch_obs_base_only(self, mock_base_dc, mock_api_response):
        """Tests that fetch_obs works correctly with only a base DC."""
        mock_base_dc.fetch_obs.return_value = mock_api_response

        multi_client = MultiDCClient(base_dc=mock_base_dc, custom_dc=None)
        request = Mock(spec=ObservationToolRequest, date_filter=None)

        response = await multi_client.fetch_obs(request)

        mock_base_dc.fetch_obs.assert_awaited_once_with(request)
        assert "place1" in response.place_data
        var_series = response.place_data["place1"].variable_series["var1"]
        assert response.source_info.get(var_series.source_id).importName == "source1"
        assert len(var_series.alternative_sources) == 1

    @pytest.mark.asyncio
    async def test_fetch_obs_merges_custom_and_base(self, mock_base_dc, mock_custom_dc):
        """Tests that results from custom and base DCs are merged correctly."""

        # Custom DC has a unique facet 'f_custom'
        custom_response_data = {
            "byVariable": {
                "var1": {
                    "byEntity": {
                        "place1": {
                            "orderedFacets": [
                                {
                                    "facetId": "f_custom",
                                    "earliestDate": "2025",
                                    "latestDate": "2025",
                                    "obsCount": 1,
                                    "observations": [{"date": "2025", "value": 100}],
                                }
                            ]
                        }
                    }
                }
            },
            "facets": {"f_custom": {"import_name": "custom_source"}},
        }
        mock_custom_dc.fetch_obs.return_value = ObservationApiResponse.model_validate(
            custom_response_data
        )

        # Base DC has a different facet 'f_base' that doesn't overlap with custom
        base_response_data = {
            "byVariable": {"var1": {"byEntity": {"place1": {"orderedFacets": []}}}},
            "facets": {},
        }
        mock_base_dc.fetch_obs.return_value = ObservationApiResponse.model_validate(
            base_response_data
        )

        multi_client = MultiDCClient(base_dc=mock_base_dc, custom_dc=mock_custom_dc)
        request = Mock(spec=ObservationToolRequest, date_filter=None)

        await multi_client.fetch_obs(request)

        mock_custom_dc.fetch_obs.assert_awaited_once_with(request)
        mock_base_dc.fetch_obs.assert_awaited_once_with(request)

    def test_integrate_observation_initial_data(self, mock_api_response):
        response = ObservationToolResponse()
        MultiDCClient._integrate_observation_response(
            response, mock_api_response
        )

        assert "place1" in response.place_data
        place_data = response.place_data["place1"]
        assert "var1" in place_data.variable_series

        var_series = place_data.variable_series["var1"]
        assert var_series.source_metadata.source_id == "f1"
        assert var_series.source_id == "f1"  # Test the property
        assert len(var_series.observations) == 2
        assert len(var_series.alternative_sources) == 1
        assert var_series.alternative_sources[0].source_id == "f2"

    def test_integrate_observation_alternative_sources(self, mock_api_response):
        response = ObservationToolResponse()
        # Pre-populate with some data
        initial_metadata = SourceMetadata(source_id="f_initial")
        initial_series = VariableSeries(
            variable_dcid="var1",
            source_metadata=initial_metadata,
            observations=[],
            alternative_sources=[],
        )
        response.place_data["place1"] = Mock(variable_series={"var1": initial_series})

        MultiDCClient._integrate_observation_response(
            response, mock_api_response
        )

        # Check that the new sources were appended
        final_series = response.place_data["place1"].variable_series["var1"]
        assert len(final_series.alternative_sources) == 2  # 2 new sources added
        assert {s.source_id for s in final_series.alternative_sources} == {"f1", "f2"}

    def test_integrate_observation_with_date_filter(self, mock_api_response):
        response = ObservationToolResponse()
        date_filter = DateRange(start_date="2023", end_date="2023")

        MultiDCClient._integrate_observation_response(
            response, mock_api_response, date_filter=date_filter
        )

        var_series = response.place_data["place1"].variable_series["var1"]
        # Only the observation for "2023" should have been selected
        assert len(var_series.observations) == 1
        assert var_series.observations[0].value == 2
