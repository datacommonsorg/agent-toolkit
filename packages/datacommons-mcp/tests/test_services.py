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
from datacommons_mcp.clients import DCClient
from datacommons_mcp.data_models.observations import (
    ObservationApiResponse,
    ObservationDateType,
    ObservationToolResponse,
)
from datacommons_mcp.data_models.search import NodeInfo, ResolvedPlace
from datacommons_mcp.exceptions import (
    DataLookupError,
    InvalidDateFormatError,
    InvalidDateRangeError,
)
from datacommons_mcp.services import (
    _validate_and_build_request,
    get_observations,
    search_indicators,
)


@pytest.mark.asyncio
class TestGetObservations:
    @pytest.fixture
    def mock_client(self):
        """
        Provides a fresh, reset mock for each test method.
        """
        mock = Mock(spec_set=DCClient)
        mock.search_places = AsyncMock()
        mock.fetch_obs = AsyncMock()
        mock.fetch_entity_infos = AsyncMock()
        mock.fetch_entity_types = AsyncMock()
        return mock

    async def test_input_validation_errors(self, mock_client):
        # Missing variable
        with pytest.raises(ValueError, match="'variable_dcid' must be specified."):
            await _validate_and_build_request(
                client=mock_client, variable_dcid="", place_name="USA"
            )

        # Missing place
        with pytest.raises(
            ValueError, match="Specify either 'place_name' or 'place_dcid'"
        ):
            await _validate_and_build_request(client=mock_client, variable_dcid="var1")

    async def test_input_validation_date_validation(self, mock_client):
        # Invalid date format
        with pytest.raises(InvalidDateFormatError):
            await _validate_and_build_request(
                client=mock_client,
                variable_dcid="var1",
                place_name="USA",
                date=ObservationDateType.RANGE,
                date_range_start="2022-a",
                date_range_end="2023",
            )

        # Invalid date range
        with pytest.raises(InvalidDateRangeError):
            await _validate_and_build_request(
                client=mock_client,
                variable_dcid="var1",
                place_name="USA",
                date=ObservationDateType.RANGE,
                date_range_start="2023",
                date_range_end="2022",
            )

    async def test_request_building_with_dcids(self, mock_client):
        request = await _validate_and_build_request(
            client=mock_client, variable_dcid="var1", place_dcid="country/USA"
        )
        assert request.variable_dcid == "var1"
        assert request.place_dcid == "country/USA"
        assert request.date_type == ObservationDateType.LATEST
        mock_client.search_places.assert_not_called()

    async def test_request_building_with_resolution_success(self, mock_client):
        mock_client.search_places.return_value = {"USA": "country/USA"}

        request = await _validate_and_build_request(
            client=mock_client,
            variable_dcid="Count_Person",
            place_name="USA",
            date=ObservationDateType.RANGE,
            date_range_start="2022",
            date_range_end="2023",
        )

        mock_client.search_places.assert_awaited_once_with(["USA"])
        assert request.variable_dcid == "Count_Person"
        assert request.place_dcid == "country/USA"
        assert request.date_type == ObservationDateType.ALL
        assert request.date_filter.start_date_str == "2022-01-01"
        assert request.date_filter.end_date_str == "2023-12-31"

    async def test_request_building_with_single_date_string(self, mock_client):
        """Tests that a single date string creates a valid DateRange object."""
        mock_client.search_places.return_value = {"USA": "country/USA"}

        request = await _validate_and_build_request(
            client=mock_client,
            variable_dcid="Count_Person",
            place_name="USA",
            date="2022-05-15",
        )

        mock_client.search_places.assert_awaited_once_with(["USA"])
        assert request.variable_dcid == "Count_Person"
        assert request.place_dcid == "country/USA"
        assert request.date_type == ObservationDateType.ALL
        assert request.date_filter.start_date_str == "2022-05-15"
        assert request.date_filter.end_date_str == "2022-05-15"

    async def test_request_building_resolution_failure(self, mock_client):
        mock_client.search_places.return_value = {}  # No place found
        with pytest.raises(DataLookupError, match="DataLookupError: No place found"):
            await _validate_and_build_request(
                client=mock_client, variable_dcid="var1", place_name="invalid"
            )

    @pytest.fixture
    def mock_api_response(self):
        """Provides a mock ObservationApiResponse."""
        api_response_data = {
            "byVariable": {
                "var1": {
                    "byEntity": {
                        "country/USA": {
                            "orderedFacets": [
                                {
                                    "facetId": "source1",
                                    "observations": [
                                        {"date": "2020", "value": 10},
                                        {"date": "2021", "value": 20},
                                        {"date": "2022", "value": 30},
                                    ],
                                }
                            ]
                        },
                        "country/CAN": {
                            "orderedFacets": [
                                {
                                    "facetId": "source2",
                                    "observations": [
                                        {"date": "2021", "value": 15},
                                        {"date": "2022", "value": 25},
                                    ],
                                }
                            ]
                        },
                    }
                }
            },
            "facets": {
                "source1": {"importName": "Source One"},
                "source2": {"importName": "Source Two"},
            },
        }
        return ObservationApiResponse.model_validate(api_response_data)

    async def test_data_fetching_and_processing_get_observations_e2e_single_place(
        self, mock_client
    ):
        """Test the full get_observations flow for a single place."""
        # Arrange
        # This mock response is specific to this test and only contains data for the requested place.
        single_place_api_response_data = {
            "byVariable": {
                "var1": {
                    "metadata": {},  # Ensure metadata is present
                    "byEntity": {
                        "country/USA": {
                            "orderedFacets": [
                                {
                                    "facetId": "source1",
                                    "observations": [
                                        {"date": "2020", "value": 10},
                                        {"date": "2021", "value": 20},
                                        {"date": "2022", "value": 30},
                                    ],
                                }
                            ]
                        }
                    },
                }
            },
            "facets": {"source1": {"importName": "Source One"}},
        }
        mock_client.search_places.return_value = {"USA": "country/USA"}
        mock_client.fetch_obs.return_value = ObservationApiResponse.model_validate(
            single_place_api_response_data
        )

        mock_client.fetch_entity_names.return_value = {
            "country/USA": "United States",
            "country/CAN": "Canada",
            "var1": "Variable 1",
        }
        mock_client.fetch_entity_types.return_value = {
            "country/USA": ["Country"],
            "country/CAN": ["Country"],
        }

        # Act
        result = await get_observations(
            client=mock_client,
            variable_dcid="var1",
            place_name="USA",
            date=ObservationDateType.RANGE,
            date_range_start="2021",
            date_range_end="2022",
        )

        # Assert
        assert isinstance(result, ObservationToolResponse)
        assert result.variable.dcid == "var1"
        assert result.variable.name == "Variable 1"
        assert result.resolved_parent_place is None
        assert result.child_place_type is None

        # Check observations
        assert len(result.place_observations) == 1
        obs = result.place_observations[0]
        assert obs.place.dcid == "country/USA"
        assert obs.place.name == "United States"
        assert obs.place.type_of == ["Country"]
        assert len(obs.time_series) == 2
        assert ("2021", 20) in obs.time_series
        assert ("2022", 30) in obs.time_series

        # Check source info
        assert result.source_metadata.source_id == "source1"
        assert result.source_metadata.import_name == "Source One"
        assert len(result.alternative_sources) == 0  # No other sources for USA

    async def test_data_fetching_and_processing_get_observations_e2e_child_places(
        self, mock_client
    ):
        """Test observation retrieval for child places of a parent."""
        # Arrange
        mock_client.search_places.return_value = {"California": "country/USA/state/CA"}

        api_response_data = {
            "byVariable": {
                "var1": {
                    "byEntity": {
                        "geoId/06001": {
                            "orderedFacets": [
                                {
                                    "facetId": "source1",
                                    "observations": [{"date": "2022", "value": 100}],
                                }
                            ]
                        },
                        "geoId/06037": {
                            "orderedFacets": [
                                {
                                    "facetId": "source1",
                                    "observations": [{"date": "2022", "value": 200}],
                                }
                            ]
                        },
                        "geoId/06085": {  # Santa Clara, different source
                            "orderedFacets": [
                                {
                                    "facetId": "source2",
                                    "observations": [{"date": "2022", "value": 300}],
                                }
                            ]
                        },
                    }
                }
            },
            "facets": {
                "source1": {"importName": "Source One"},
                "source2": {"importName": "Source Two"},
            },
        }
        mock_api_response = ObservationApiResponse.model_validate(api_response_data)
        mock_client.fetch_obs.return_value = mock_api_response

        mock_client.fetch_entity_names.return_value = {
            "country/USA/state/CA": "California",
            "geoId/06001": "Alameda County",
            "geoId/06037": "Los Angeles County",
            "geoId/06085": "Santa Clara County",
        }
        mock_client.fetch_entity_types.return_value = {
            "country/USA/state/CA": ["State"],
            "geoId/06001": ["County"],
            "geoId/06037": ["County"],
            "geoId/06085": ["County"],
        }

        # Act
        result = await get_observations(
            client=mock_client,
            variable_dcid="var1",
            place_name="California",
            child_place_type="County",
            date="latest",
        )

        # Assert
        assert result.resolved_parent_place.name == "California"
        assert result.child_place_type == "County"
        # All 3 counties should be in the response
        assert len(result.place_observations) == 3

        # Check that the observations are correct
        obs_by_dcid = {obs.place.dcid: obs for obs in result.place_observations}
        # Alameda and LA have data from the primary source (source1)
        assert len(obs_by_dcid["geoId/06001"].time_series) == 1
        assert obs_by_dcid["geoId/06001"].time_series[0] == ("2022", 100.0)
        assert len(obs_by_dcid["geoId/06037"].time_series) == 1
        assert obs_by_dcid["geoId/06037"].time_series[0] == ("2022", 200.0)
        # Santa Clara has no data from source1, so its time_series is empty
        assert len(obs_by_dcid["geoId/06085"].time_series) == 0

        # Check that source2 is listed as an alternative
        assert len(result.alternative_sources) == 1
        alt_source = result.alternative_sources[0]
        assert alt_source.source_id == "source2"
        assert alt_source.places_found_count == 1

    async def test_data_fetching_unit_field(self, mock_client):
        """Tests that date='latest' fetches only the latest observation."""
        # Arrange
        mock_client.search_places.return_value = {"USA": "country/USA"}
        mock_client.fetch_obs.return_value = ObservationApiResponse.model_validate(
            {
                "byVariable": {
                    "var1": {
                        "metadata": {"unit": "USDollar"},
                        "byEntity": {
                            "country/USA": {
                                "orderedFacets": [
                                    {
                                        "facetId": "source1",
                                        "observations": [
                                            {"date": "2022", "value": 30},
                                        ],
                                    }
                                ]
                            }
                        },
                    }
                },
                "facets": {"source1": {"importName": "Source One", "unit": "USDollar"}},
            }
        )
        mock_client.fetch_entity_names.return_value = {"country/USA": "United States"}
        mock_client.fetch_entity_types.return_value = {"country/USA": ["Country"]}

        # Act
        result = await get_observations(
            client=mock_client,
            variable_dcid="var1",
            place_name="USA",
        )

        # Assert
        assert result.source_metadata.unit == "USDollar"

    async def test_data_fetching_date_filtering_date_latest(self, mock_client):
        """Tests that date='latest' fetches only the latest observation."""
        # Arrange
        mock_client.search_places.return_value = {"USA": "country/USA"}
        mock_client.fetch_obs.return_value = ObservationApiResponse.model_validate(
            {
                "byVariable": {
                    "var1": {
                        "byEntity": {
                            "country/USA": {
                                "orderedFacets": [
                                    {
                                        "facetId": "source1",
                                        "observations": [  # Only the latest observation is returned by the mock
                                            {"date": "2022", "value": 30},
                                        ],
                                    }
                                ]
                            }
                        }
                    }
                },
                "facets": {"source1": {"importName": "Source One"}},
            }
        )
        mock_client.fetch_entity_names.return_value = {"country/USA": "United States"}
        mock_client.fetch_entity_types.return_value = {"country/USA": ["Country"]}

        # Act
        result = await get_observations(
            client=mock_client,
            variable_dcid="var1",
            place_name="USA",
            date="latest",
        )

        # Assert
        assert len(result.place_observations) == 1
        obs = result.place_observations[0]
        assert len(obs.time_series) == 1
        assert obs.time_series[0] == ("2022", 30)
        # Verify the correct API call was made
        mock_client.fetch_obs.assert_called_once()
        assert (
            mock_client.fetch_obs.call_args[0][0].date_type
            == ObservationDateType.LATEST
        )

    async def test_source_selection_primary_source_selection(self, mock_client):
        """Tests that the source with data for the most places is chosen as primary."""
        # Arrange
        mock_client.search_places.return_value = {"California": "country/USA/state/CA"}
        api_response_data = {
            "byVariable": {
                "var1": {
                    "byEntity": {
                        "geoId/06001": {
                            "orderedFacets": [
                                {
                                    "facetId": "source1",
                                    "observations": [{"date": "2022", "value": 100}],
                                }
                            ]
                        },
                        "geoId/06037": {
                            "orderedFacets": [
                                {
                                    "facetId": "source1",
                                    "observations": [{"date": "2022", "value": 200}],
                                }
                            ]
                        },
                        "geoId/06085": {  # Santa Clara, different source
                            "orderedFacets": [
                                {
                                    "facetId": "source2",
                                    "observations": [{"date": "2022", "value": 300}],
                                }
                            ]
                        },
                    }
                }
            },
            "facets": {
                "source1": {"importName": "Source One"},
                "source2": {"importName": "Source Two"},
            },
        }
        mock_api_response = ObservationApiResponse.model_validate(api_response_data)
        mock_client.fetch_obs.return_value = mock_api_response
        mock_client.fetch_entity_names.return_value = {
            "country/USA/state/CA": "California",
            "geoId/06001": "Alameda County",
            "geoId/06037": "Los Angeles County",
            "geoId/06085": "Santa Clara County",
        }
        mock_client.fetch_entity_types.return_value = {
            "country/USA/state/CA": ["State"],
            "geoId/06001": ["County"],
            "geoId/06037": ["County"],
            "geoId/06085": ["County"],
        }

        # Act
        result = await get_observations(
            client=mock_client,
            variable_dcid="var1",
            place_name="California",
            child_place_type="County",
        )

        # Assert
        assert result.source_metadata.source_id == "source1"

        # Check alternative sources
        assert len(result.alternative_sources) == 1
        alt_source = result.alternative_sources[0]
        assert alt_source.source_id == "source2"
        assert alt_source.places_found_count == 1

    async def test_source_selection_single_place_with_alternative_source(
        self, mock_client
    ):
        """
        Tests that for a single place response, alternative sources have
        places_found_count set to None.
        """
        # Arrange
        # Mock API response with two sources for a single place
        api_response_data = {
            "byVariable": {
                "var1": {
                    "byEntity": {
                        "country/USA": {
                            "orderedFacets": [
                                {
                                    "facetId": "source1",  # More observations, will be primary
                                    "observations": [
                                        {"date": "2021", "value": 20},
                                        {"date": "2022", "value": 30},
                                    ],
                                },
                                {
                                    "facetId": "source2",
                                    "observations": [{"date": "2022", "value": 25}],
                                },
                            ]
                        }
                    }
                }
            },
            "facets": {
                "source1": {"importName": "Source One"},
                "source2": {"importName": "Source Two"},
            },
        }
        mock_client.search_places.return_value = {"USA": "country/USA"}
        mock_client.fetch_obs.return_value = ObservationApiResponse.model_validate(
            api_response_data
        )
        mock_client.fetch_entity_names.return_value = {"country/USA": "United States"}
        mock_client.fetch_entity_types.return_value = {"country/USA": ["Country"]}

        # Act
        result = await get_observations(
            client=mock_client, variable_dcid="var1", place_name="USA"
        )

        # Assert
        assert len(result.alternative_sources) == 1
        alt_source = result.alternative_sources[0]
        assert alt_source.source_id == "source2"
        assert alt_source.places_found_count is None

    async def test_source_selection_source_override(self, mock_client):
        """Tests that source_override forces the use of a specific source."""
        # Arrange
        mock_client.search_places.return_value = {"USA": "country/USA"}
        api_response_data = {
            "byVariable": {
                "var1": {
                    "byEntity": {
                        "country/USA": {
                            "orderedFacets": [
                                {
                                    "facetId": "source1",
                                    "observations": [{"date": "2022", "value": 100}],
                                },
                                {
                                    "facetId": "source2",
                                    "observations": [{"date": "2022", "value": 200}],
                                },
                            ]
                        }
                    }
                }
            },
            "facets": {
                "source1": {"importName": "Source One"},
                "source2": {"importName": "Source Two"},
            },
        }
        mock_client.fetch_obs.return_value = ObservationApiResponse.model_validate(
            api_response_data
        )
        mock_client.fetch_entity_names.return_value = {"country/USA": "United States"}
        mock_client.fetch_entity_types.return_value = {"country/USA": ["Country"]}

        # Act: Override to use source2
        result = await get_observations(
            client=mock_client,
            variable_dcid="var1",
            place_name="USA",
            source_override="source2",
        )

        # Assert
        assert result.source_metadata.source_id == "source2"
        assert result.place_observations[0].time_series[0] == ("2022", 200)
        # No alternatives should be listed when a source is selected
        assert len(result.alternative_sources) == 0

    async def test_source_selection_tiebreaker_by_facet_order(self, mock_client):
        """
        Tests that the average index in orderedFacets is used as a tie-breaker.
        Source2 should be chosen because it appears earlier on average.
        """
        # Arrange
        # source1 appears at indices 1 and 1 (avg: 1)
        # source2 appears at indices 0 and 0 (avg: 0)
        api_response_data = {
            "byVariable": {
                "var1": {
                    "byEntity": {
                        "place1": {
                            "orderedFacets": [
                                {
                                    "facetId": "source2",
                                    "observations": [{"date": "2022", "value": 1}],
                                },
                                {
                                    "facetId": "source1",
                                    "observations": [{"date": "2022", "value": 2}],
                                },
                            ]
                        },
                        "place2": {
                            "orderedFacets": [
                                {
                                    "facetId": "source2",
                                    "observations": [{"date": "2022", "value": 3}],
                                },
                                {
                                    "facetId": "source1",
                                    "observations": [{"date": "2022", "value": 4}],
                                },
                            ]
                        },
                    }
                }
            },
            "facets": {
                "source1": {"importName": "Source One"},
                "source2": {"importName": "Source Two"},
            },
        }
        mock_client.fetch_obs.return_value = ObservationApiResponse.model_validate(
            api_response_data
        )
        mock_client.fetch_entity_names.return_value = {
            "place1": "Place One",
            "place2": "Place Two",
        }
        mock_client.fetch_entity_types.return_value = {
            "place1": ["City"],
            "place2": ["City"],
        }

        # Act
        result = await get_observations(
            client=mock_client, variable_dcid="var1", place_dcid="any"
        )

        # Assert
        assert result.source_metadata.source_id == "source2"

    async def test_source_selection_tiebreaker_by_source_id(self, mock_client):
        """
        Tests that the source_id is used as a final tie-breaker.
        Source2 should be chosen because it is alphabetically greater.
        """
        # Arrange
        # source1 appears at indices 0 and 1 (avg: 0.5)
        # source2 appears at indices 1 and 0 (avg: 0.5)
        api_response_data = {
            "byVariable": {
                "var1": {
                    "byEntity": {
                        "place1": {
                            "orderedFacets": [
                                {
                                    "facetId": "source1",
                                    "observations": [{"date": "2022", "value": 1}],
                                },
                                {
                                    "facetId": "source2",
                                    "observations": [{"date": "2022", "value": 2}],
                                },
                            ]
                        },
                        "place2": {
                            "orderedFacets": [
                                {
                                    "facetId": "source2",
                                    "observations": [{"date": "2022", "value": 3}],
                                },
                                {
                                    "facetId": "source1",
                                    "observations": [{"date": "2022", "value": 4}],
                                },
                            ]
                        },
                    }
                }
            },
            "facets": {
                "source1": {"importName": "Source One"},
                "source2": {"importName": "Source Two"},
            },
        }
        mock_client.fetch_obs.return_value = ObservationApiResponse.model_validate(
            api_response_data
        )
        mock_client.fetch_entity_names.return_value = {
            "place1": "Place One",
            "place2": "Place Two",
        }
        mock_client.fetch_entity_types.return_value = {
            "place1": ["City"],
            "place2": ["City"],
        }

        # Act
        result = await get_observations(
            client=mock_client, variable_dcid="var1", place_dcid="any"
        )

        # Assert
        # Both have same avg rank (0.5), but source2 is alphabetically greater, so max() chooses it.
        assert result.source_metadata.source_id == "source2"

    @pytest.mark.parametrize(
        ("date1", "date2", "expected_primary_source"),
        [
            ("2022-01", "2022-02", "source2"),  # YYYY-MM
            ("2022-02", "2022-01", "source1"),  # YYYY-MM
            ("2022-01-15", "2022-01-16", "source2"),  # YYYY-MM-DD
            ("2022", "2022-06", "source2"),  # YYYY vs YYYY-MM
            ("2022-06", "2022", "source1"),  # YYYY-MM vs YYYY
            ("2022-01-16", "2022-01-15", "source1"),  # YYYY-MM-DD
            ("2022-02", "2022-01-15", "source1"),  # Mixed Granularity
        ],
    )
    async def test_source_selection_primary_source_tiebreaker_by_latest_date(
        self, mock_client, date1, date2, expected_primary_source
    ):
        """
        Tests that the latest date is used as a tie-breaker when place and
        observation counts are equal, across various date formats.
        """
        # Arrange
        # Two sources, each with one place and one observation.
        # The only difference is the date of the observation.
        api_response_data = {
            "byVariable": {
                "var1": {
                    "byEntity": {
                        "geoId/01": {  # Place 1
                            "orderedFacets": [
                                {
                                    "facetId": "source1",
                                    "observations": [{"date": date1, "value": 100}],
                                }
                            ]
                        },
                        "geoId/02": {  # Place 2
                            "orderedFacets": [
                                {
                                    "facetId": "source2",
                                    "observations": [{"date": date2, "value": 200}],
                                }
                            ]
                        },
                    }
                }
            },
            "facets": {
                "source1": {"importName": "Source One"},
                "source2": {"importName": "Source Two"},
            },
        }
        mock_client.search_places.return_value = {"USA": "country/USA"}
        mock_client.fetch_obs.return_value = ObservationApiResponse.model_validate(
            api_response_data
        )
        mock_client.fetch_entity_names.return_value = {
            "country/USA": "USA",
            "geoId/01": "Place 1",
            "geoId/02": "Place 2",
        }
        mock_client.fetch_entity_types.return_value = {
            "country/USA": ["Country"],
            "geoId/01": ["State"],
            "geoId/02": ["State"],
        }

        # Act
        result = await get_observations(
            client=mock_client,
            variable_dcid="var1",
            place_name="USA",
            child_place_type="State",
        )

        # Assert
        assert result.source_metadata.source_id == expected_primary_source


@pytest.mark.asyncio
class TestSearchIndicators:
    """Tests for the search_indicators service function."""

    @pytest.mark.asyncio
    async def test_search_indicators_browse_mode_basic(self):
        """Test basic search in browse mode without place filtering."""
        mock_client = Mock()
        mock_client.use_search_indicators_endpoint = False
        mock_client.fetch_indicators = AsyncMock(
            return_value={"topics": [], "variables": [], "lookups": {}}
        )
        mock_client.fetch_entity_infos = AsyncMock(return_value={})
        result = await search_indicators(
            client=mock_client,
            query="health",
        )

        assert result.topics is not None
        assert result.variables is not None
        assert result.dcid_name_mappings is not None
        assert result.status == "SUCCESS"
        mock_client.fetch_indicators.assert_called_once_with(
            query="health", place_dcids=[], include_topics=True, max_results=10
        )

    @pytest.mark.asyncio
    async def test_search_indicators_browse_mode_with_places(self):
        """Test search in browse mode with place filtering."""
        mock_client = Mock()
        mock_client.use_search_indicators_endpoint = False
        mock_client.search_places = AsyncMock(return_value={"France": "country/FRA"})
        mock_client.fetch_indicators = AsyncMock(
            return_value={
                "topics": [{"dcid": "topic/trade"}],
                "variables": [
                    {"dcid": "TradeExports_FRA"},
                    {"dcid": "TradeImports_FRA"},
                ],
                "lookups": {
                    "topic/trade": "Trade",
                    "TradeExports_FRA": "Exports to France",
                    "TradeImports_FRA": "Imports from France",
                },
            }
        )
        mock_client.fetch_entity_infos = AsyncMock(
            return_value={
                "topic/trade": NodeInfo(name="Trade", typeOf=["Topic"]),
                "TradeExports_FRA": NodeInfo(
                    name="Exports to France", typeOf=["StatisticalVariable"]
                ),
                "TradeImports_FRA": NodeInfo(
                    name="Imports from France", typeOf=["StatisticalVariable"]
                ),
            }
        )

        result = await search_indicators(
            client=mock_client, query="trade", places=["France"]
        )

        # Should have both topics and variables in expected order
        expected_topic_dcids = ["topic/trade"]
        expected_variable_dcids = ["TradeExports_FRA", "TradeImports_FRA"]
        actual_topic_dcids = [t.dcid for t in result.topics]
        actual_variable_dcids = [v.dcid for v in result.variables]
        assert actual_topic_dcids == expected_topic_dcids
        assert actual_variable_dcids == expected_variable_dcids

        # Verify that fetch_entity_infos is called with the correct DCIDs
        expected_dcids = {
            "topic/trade",
            "TradeExports_FRA",
            "TradeImports_FRA",
            "country/FRA",
        }
        mock_client.fetch_entity_infos.assert_called_once()
        actual_dcids = set(mock_client.fetch_entity_infos.call_args[0][0])
        assert actual_dcids == expected_dcids

    @pytest.mark.asyncio
    async def test_search_indicators_browse_mode_with_custom_per_search_limit(self):
        """Test search in browse mode with custom per_search_limit parameter."""
        mock_client = Mock()
        mock_client.use_search_indicators_endpoint = False
        mock_client.fetch_indicators = AsyncMock(
            return_value={
                "topics": [{"dcid": "topic/health"}],
                "variables": [{"dcid": "Count_Person"}],
                "lookups": {"topic/health": "Health", "Count_Person": "Population"},
            }
        )
        mock_client.fetch_entity_infos = AsyncMock(
            return_value={
                "topic/health": NodeInfo(name="Health", typeOf=["Topic"]),
                "Count_Person": NodeInfo(
                    name="Population", typeOf=["StatisticalVariable"]
                ),
            }
        )

        await search_indicators(client=mock_client, query="health", per_search_limit=5)

        # Verify per_search_limit was passed to client
        mock_client.fetch_indicators.assert_called_once_with(
            query="health", place_dcids=[], include_topics=True, max_results=5
        )

    @pytest.mark.asyncio
    async def test_search_indicators_browse_mode_per_search_limit_validation(self):
        """Test per_search_limit parameter validation in browse mode."""
        mock_client = Mock()
        mock_client.use_search_indicators_endpoint = False

        # Test invalid per_search_limit values
        with pytest.raises(
            ValueError, match="per_search_limit must be between 1 and 100"
        ):
            await search_indicators(
                client=mock_client, query="health", per_search_limit=0
            )

        with pytest.raises(
            ValueError, match="per_search_limit must be between 1 and 100"
        ):
            await search_indicators(
                client=mock_client, query="health", per_search_limit=101
            )

        # Test valid per_search_limit values
        mock_client.fetch_indicators = AsyncMock(return_value={})

        # Should not raise for valid values
        await search_indicators(client=mock_client, query="health", per_search_limit=1)
        await search_indicators(
            client=mock_client, query="health", per_search_limit=100
        )

    @pytest.mark.asyncio
    async def test_search_indicators_exclude_topics(self):
        """Test basic search in lookup mode with a single place."""
        mock_client = Mock()
        mock_client.use_search_indicators_endpoint = False
        mock_client.search_places = AsyncMock(return_value={"USA": "country/USA"})
        mock_client.fetch_indicators = AsyncMock(
            return_value={
                "variables": [{"dcid": "Count_Person"}, {"dcid": "Count_Household"}],
            }
        )
        mock_client.fetch_entity_infos = AsyncMock(
            return_value={
                "Count_Person": NodeInfo(
                    name="Population", typeOf=["StatisticalVariable"]
                ),
                "Count_Household": NodeInfo(
                    name="Households", typeOf=["StatisticalVariable"]
                ),
                "country/USA": NodeInfo(name="USA", typeOf=["Country"]),
            }
        )

        result = await search_indicators(
            client=mock_client, query="health", places=["USA"], include_topics=False
        )

        # Should have variables with dcid and places_with_data in expected order
        expected_variable_dcids = ["Count_Person", "Count_Household"]
        actual_variable_dcids = [v.dcid for v in result.variables]
        assert actual_variable_dcids == expected_variable_dcids

    @pytest.mark.asyncio
    async def test_search_indicators_exclude_topics_merge_results(self):
        """Test that results from multiple bilateral searches are properly merged and deduplicated."""
        mock_client = Mock()
        mock_client.use_search_indicators_endpoint = False
        mock_client.search_places = AsyncMock(
            return_value={"France": "country/FRA", "Germany": "country/DEU"}
        )
        mock_client.fetch_indicators = AsyncMock(
            side_effect=[
                {
                    "variables": [{"dcid": "TradeExports_FRA"}]
                },  # Base query with both places
                {
                    "variables": [
                        {"dcid": "TradeExports_DEU"},
                        {"dcid": "TradeExports_FRA"},
                    ]
                },  # query + France (filtered by Germany)
                {
                    "variables": [{"dcid": "TradeExports_FRA"}]
                },  # query + Germany (filtered by France)
            ]
        )
        mock_client.fetch_entity_infos = AsyncMock(
            return_value={
                "TradeExports_FRA": NodeInfo(
                    name="Exports to France", typeOf=["StatisticalVariable"]
                ),
                "TradeExports_DEU": NodeInfo(
                    name="Exports to Germany", typeOf=["StatisticalVariable"]
                ),
                "country/FRA": NodeInfo(name="France", typeOf=["Country"]),
                "country/DEU": NodeInfo(name="Germany", typeOf=["Country"]),
            }
        )

        result = await search_indicators(
            client=mock_client,
            query="trade",
            places=["France", "Germany"],
            include_topics=False,
            maybe_bilateral=True,
        )

        # Should have deduplicated variables in expected order
        assert result.topics == []
        expected_variable_dcids = ["TradeExports_FRA", "TradeExports_DEU"]
        actual_variable_dcids = [v.dcid for v in result.variables]
        assert actual_variable_dcids == expected_variable_dcids

    @pytest.mark.asyncio
    async def test_search_indicators_exclude_topics_per_search_limit_validation(self):
        """Test per_search_limit parameter when topics are excluded."""
        mock_client = Mock()
        mock_client.use_search_indicators_endpoint = False

        # Test invalid per_search_limit values
        with pytest.raises(
            ValueError, match="per_search_limit must be between 1 and 100"
        ):
            await search_indicators(
                client=mock_client,
                query="health",
                include_topics=False,
                per_search_limit=0,
            )

        with pytest.raises(
            ValueError, match="per_search_limit must be between 1 and 100"
        ):
            await search_indicators(
                client=mock_client,
                query="health",
                include_topics=False,
                per_search_limit=101,
            )

        # Test valid per_search_limit values with place (so lookup mode is actually used)
        mock_client.search_places = AsyncMock(return_value={"USA": "country/USA"})
        mock_client.fetch_indicators = AsyncMock(return_value={"variables": []})
        mock_client.fetch_entity_infos = AsyncMock(return_value={})

        # Should not raise for valid values
        await search_indicators(
            client=mock_client,
            query="health",
            places=["USA"],
            include_topics=False,
            per_search_limit=1,
        )
        await search_indicators(
            client=mock_client,
            query="health",
            places=["USA"],
            include_topics=False,
            per_search_limit=100,
        )

    @pytest.mark.asyncio
    async def test_search_indicators_exclude_topics_no_places(self):
        """Test that lookup mode works when no places are provided."""
        mock_client = Mock()
        mock_client.use_search_indicators_endpoint = False
        mock_client.fetch_indicators = AsyncMock(
            return_value={
                "variables": [{"dcid": "Count_Person"}],
                "lookups": {"Count_Person": "Population"},
            }
        )
        mock_client.fetch_entity_infos = AsyncMock(
            return_value={
                "Count_Person": NodeInfo(
                    name="Population", typeOf=["StatisticalVariable"]
                )
            }
        )

        # Call with lookup mode but no places - should automatically fall back to browse mode
        result = await search_indicators(
            client=mock_client,
            query="health",
            include_topics=False,  # No places provided
        )

        # Should return lookup mode results (variables only)
        assert result.topics == []
        assert result.variables is not None
        assert result.dcid_name_mappings is not None
        assert result.status == "SUCCESS"
        mock_client.fetch_indicators.assert_called_once_with(
            query="health", place_dcids=[], include_topics=False, max_results=10
        )

    @pytest.mark.asyncio
    async def test_search_indicators_places_parameter_behavior(self):
        """Test places parameter behavior across browse and lookup modes."""
        mock_client = Mock()
        mock_client.use_search_indicators_endpoint = False
        mock_client.search_places = AsyncMock(
            return_value={
                "France": "country/FRA",
                "USA": "country/USA",
                "Canada": "country/CAN",
            }
        )
        mock_client.fetch_indicators = AsyncMock(
            return_value={"topics": [], "variables": [], "lookups": {}}
        )
        mock_client.fetch_entity_infos = AsyncMock(return_value={})

        # Test 1: Single place including topics
        result = await search_indicators(
            client=mock_client,
            query="trade exports",
            places=["France"],
        )
        assert result.status == "SUCCESS"
        mock_client.search_places.assert_called_with(["France"])
        mock_client.fetch_indicators.assert_called_once_with(
            query="trade exports",
            place_dcids=["country/FRA"],
            include_topics=True,
            max_results=10,
        )

        # Reset mocks for next test
        mock_client.reset_mock()
        mock_client.use_search_indicators_endpoint = False
        mock_client.search_places = AsyncMock(return_value={"France": "country/FRA"})
        mock_client.fetch_indicators = AsyncMock(
            return_value={"topics": [], "variables": [], "lookups": {}}
        )
        mock_client.fetch_entity_infos = AsyncMock(return_value={})

        # Test 2: Single place variables-only
        result = await search_indicators(
            client=mock_client,
            query="trade exports",
            places=["France"],
            include_topics=False,
        )
        assert result.status == "SUCCESS"
        mock_client.search_places.assert_called_with(["France"])
        mock_client.fetch_indicators.assert_called_once_with(
            query="trade exports",
            place_dcids=["country/FRA"],
            include_topics=False,
            max_results=10,
        )

        # Reset mocks for next test
        mock_client.reset_mock()
        mock_client.use_search_indicators_endpoint = False
        mock_client.search_places = AsyncMock(
            return_value={
                "USA": "country/USA",
                "Canada": "country/CAN",
                "Mexico": "country/MEX",
            }
        )
        mock_client.fetch_indicators = AsyncMock(
            return_value={"topics": [], "variables": [], "lookups": {}}
        )
        mock_client.fetch_entity_infos = AsyncMock(return_value={})

        # Test 3: Multiple places including topics
        result = await search_indicators(
            client=mock_client,
            query="trade exports",
            places=["USA", "Canada", "Mexico"],
        )
        assert result.status == "SUCCESS"
        mock_client.search_places.assert_called_with(["USA", "Canada", "Mexico"])
        mock_client.fetch_indicators.assert_called_once_with(
            query="trade exports",
            place_dcids=["country/USA", "country/CAN", "country/MEX"],
            include_topics=True,
            max_results=10,
        )

    @pytest.mark.asyncio
    async def test_search_indicators_maybe_bilateral_behavior(self):
        """Test maybe_bilateral parameter behavior across browse and lookup modes."""
        mock_client = Mock()
        mock_client.use_search_indicators_endpoint = False
        mock_client.search_places = AsyncMock(
            return_value={"USA": "country/USA", "France": "country/FRA"}
        )
        mock_client.fetch_indicators = AsyncMock(
            return_value={"topics": [], "variables": [], "lookups": {}}
        )
        mock_client.fetch_entity_infos = AsyncMock(return_value={})

        # Test 1: Maybe bilateral including topics
        result = await search_indicators(
            client=mock_client,
            query="trade exports",
            places=["USA", "France"],
            maybe_bilateral=True,
        )
        assert result.status == "SUCCESS"
        mock_client.search_places.assert_called_with(["USA", "France"])
        assert mock_client.fetch_indicators.call_count == 3

        # Assert the actual queries fetch_indicators was called with
        calls = mock_client.fetch_indicators.call_args_list
        # The first call should be with USA appended to query
        assert calls[0].kwargs == {
            "query": "trade exports USA",
            "place_dcids": ["country/USA", "country/FRA"],
            "include_topics": True,
            "max_results": 10,
        }
        # The second call should be with France appended to query
        assert calls[1].kwargs == {
            "query": "trade exports France",
            "place_dcids": ["country/USA", "country/FRA"],
            "include_topics": True,
            "max_results": 10,
        }
        # The third call should be the original query with both place DCIDs
        assert calls[2].kwargs == {
            "query": "trade exports",
            "place_dcids": ["country/USA", "country/FRA"],
            "include_topics": True,
            "max_results": 10,
        }

        # Reset mocks for next test
        mock_client.reset_mock()
        mock_client.use_search_indicators_endpoint = False
        mock_client.search_places = AsyncMock(
            return_value={"USA": "country/USA", "France": "country/FRA"}
        )
        mock_client.fetch_indicators = AsyncMock(
            return_value={"topics": [], "variables": [], "lookups": {}}
        )
        mock_client.fetch_entity_infos = AsyncMock(return_value={})

        # Test 2: Maybe bilateral variables-only
        result = await search_indicators(
            client=mock_client,
            query="trade exports",
            places=["USA", "France"],
            include_topics=False,
            maybe_bilateral=True,
        )
        assert result.status == "SUCCESS"
        mock_client.search_places.assert_called_with(["USA", "France"])
        assert mock_client.fetch_indicators.call_count == 3

        # Assert the same query rewriting behavior
        calls = mock_client.fetch_indicators.call_args_list
        # The first call should be with USA appended to query
        assert calls[0].kwargs == {
            "query": "trade exports USA",
            "place_dcids": ["country/USA", "country/FRA"],
            "include_topics": False,
            "max_results": 10,
        }
        # The second call should be with France appended to query
        assert calls[1].kwargs == {
            "query": "trade exports France",
            "place_dcids": ["country/USA", "country/FRA"],
            "include_topics": False,
            "max_results": 10,
        }
        # The third call should be the original query with both place DCIDs
        assert calls[2].kwargs == {
            "query": "trade exports",
            "place_dcids": ["country/USA", "country/FRA"],
            "include_topics": False,
            "max_results": 10,
        }

    @pytest.mark.asyncio
    async def test_search_indicators_parameter_validation(self):
        """Test parameter validation for new place parameters."""
        mock_client = Mock()
        mock_client.use_search_indicators_endpoint = False
        mock_client.search_places = AsyncMock(
            return_value={"USA": "country/USA", "France": "country/FRA"}
        )
        mock_client.fetch_indicators = AsyncMock(return_value={"variables": []})
        mock_client.fetch_entity_infos = AsyncMock(return_value={})

        # Test maybe_bilateral=True with places (should work)
        result = await search_indicators(
            client=mock_client,
            query="test",
            places=["USA", "France"],
            maybe_bilateral=True,
        )
        assert result.status == "SUCCESS"
        assert mock_client.fetch_indicators.call_count == 3  # len(places) + 1

        # Test maybe_bilateral=False with places (should work)
        mock_client.reset_mock()
        mock_client.use_search_indicators_endpoint = False
        mock_client.search_places = AsyncMock(
            return_value={"USA": "country/USA", "France": "country/FRA"}
        )
        mock_client.fetch_indicators = AsyncMock(return_value={"variables": []})
        mock_client.fetch_entity_infos = AsyncMock(return_value={})

        result = await search_indicators(
            client=mock_client,
            query="test",
            places=["USA", "France"],
            maybe_bilateral=False,
        )
        assert result.status == "SUCCESS"
        assert mock_client.fetch_indicators.call_count == 1  # single search

    @pytest.mark.asyncio
    async def test_search_indicators_with_parent_place(self):
        """Test search with parent_place resolves parent and filters by children."""
        mock_client = Mock()
        mock_client.search_places = AsyncMock(
            return_value={
                "USA": "country/USA",
                "California": "geoId/06",
                "Texas": "geoId/48",
            }
        )
        mock_client.fetch_indicators = AsyncMock(
            return_value={
                "variables": [
                    {
                        "dcid": "Count_Person",
                        "places_with_data": ["geoId/06", "geoId/48"],
                    }
                ]
            }
        )
        mock_client.fetch_entity_infos = AsyncMock(
            return_value={
                "country/USA": NodeInfo(name="United States", typeOf=["Country"]),
                "geoId/06": NodeInfo(name="California", typeOf=["State"]),
                "geoId/48": NodeInfo(name="Texas", typeOf=["State"]),
                "Count_Person": NodeInfo(
                    name="Population", typeOf=["StatisticalVariable"]
                ),
            }
        )

        result = await search_indicators(
            client=mock_client,
            query="population",
            places=["California", "Texas"],
            parent_place="USA",
        )

        assert result.resolved_parent_place == ResolvedPlace(
            dcid="country/USA", name="United States", type_of=["Country"]
        )

        # Verify that existence check was done on children only
        mock_client.fetch_indicators.assert_called_once_with(
            query="population",
            place_dcids=["geoId/06", "geoId/48"],
            include_topics=True,
            max_results=10,
        )

    @pytest.mark.asyncio
    async def test_search_indicators_parent_place_no_places(self):
        """Test that a ValueError is raised if parent_place is provided without places."""
        mock_client = Mock()
        with pytest.raises(
            ValueError,
            match="`places` must be specified when `parent_place` is provided.",
        ):
            await search_indicators(
                client=mock_client, query="population", parent_place="USA"
            )
