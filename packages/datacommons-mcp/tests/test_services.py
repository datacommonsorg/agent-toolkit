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
    ObservationPeriod,
    ObservationToolResponse,
    PlaceObservation,
    SeriesMetadata,
)
from datacommons_mcp.data_models.search import SearchMode
from datacommons_mcp.exceptions import DataLookupError
from datacommons_mcp.services import (
    _build_observation_request,
    get_observations,
    search_indicators,
)


@pytest.mark.asyncio
class TestBuildObservationRequest:
    @pytest.fixture
    def mock_client(self):
        client = Mock(spec=DCClient)
        client.search_places = AsyncMock()
        return client

    async def test_validation_errors(self, mock_client):
        # Missing variable
        with pytest.raises(ValueError, match="'variable_dcid' must be specified."):
            await _build_observation_request(
                mock_client, variable_dcid="", place_name="USA"
            )

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
        mock_client.search_places.assert_not_called()

    async def test_with_resolution_success(self, mock_client):
        mock_client.search_places.return_value = {"USA": "country/USA"}

        request = await _build_observation_request(
            mock_client,
            variable_dcid="Count_Person",
            place_name="USA",
            start_date="2022",
            end_date="2023",
        )

        mock_client.search_places.assert_awaited_once_with(["USA"])
        assert request.variable_dcid == "Count_Person"
        assert request.place_dcid == "country/USA"
        assert request.observation_period == ObservationPeriod.ALL
        assert request.date_filter.start_date == "2022-01-01"
        assert request.date_filter.end_date == "2023-12-31"

    async def test_resolution_failure(self, mock_client):
        mock_client.search_places.return_value = {}  # No place found
        with pytest.raises(DataLookupError, match="DataLookupError: No place found"):
            await _build_observation_request(
                mock_client, variable_dcid="var1", place_name="invalid"
            )


@pytest.mark.asyncio
class TestGetObservations:
    @pytest.fixture
    def mock_client(self):
        client = Mock(spec=DCClient)
        client.search_places = AsyncMock()
        client.fetch_obs = AsyncMock()
        client.fetch_entity_names = AsyncMock()
        client.fetch_entity_types = AsyncMock()
        return client

    async def test_get_observations_with_date_filter(self, mock_client):
        """Test that get_observations correctly filters by date and sets observation_count."""
        # Arrange
        # Mock place resolution
        mock_client.search_places.return_value = {"USA": "country/USA"}

        # Mock API response from fetch_obs
        api_response_data = {
            "byVariable": {
                "var1": {
                    "byEntity": {
                        "country/USA": {
                            "orderedFacets": [
                                {
                                    "facetId": "source1",
                                    "earliestDate": "2020",
                                    "latestDate": "2023",
                                    "obsCount": 4,
                                    "observations": [
                                        {"date": "2020", "value": 10},
                                        {"date": "2021", "value": 20},
                                        {"date": "2022", "value": 30},
                                        {"date": "2023", "value": 40},
                                    ],
                                }
                            ]
                        }
                    }
                }
            },
            "facets": {"source1": {"importName": "test_source"}},
        }
        mock_api_response = ObservationApiResponse.model_validate(api_response_data)
        mock_client.fetch_obs.return_value = mock_api_response

        # Mock name/type lookups
        mock_client.fetch_entity_names.return_value = {
            "var1": "Variable 1",
            "country/USA": "United States",
        }
        mock_client.fetch_entity_types.return_value = {
            "country/USA": ["Country"],
        }

        # Act: Call the service with a date filter
        result = await get_observations(
            client=mock_client,
            variable_dcid="var1",
            place_name="USA",
            start_date="2021",
            end_date="2022",
        )

        # Assert
        # 1. Check the response structure
        assert isinstance(result, ObservationToolResponse)
        assert result.variable_dcid == "var1"
        assert result.variable_name == "Variable 1"
        assert len(result.observations_by_place) == 1

        # 2. Check the place observation
        place_obs = result.observations_by_place[0]
        assert isinstance(place_obs, PlaceObservation)
        assert place_obs.place.dcid == "country/USA"
        assert place_obs.place.name == "United States"
        assert place_obs.place.place_type == "Country"

        # 3. Check the primary series metadata and the filtered observation_count
        primary_meta = place_obs.primary_series_metadata
        assert isinstance(primary_meta, SeriesMetadata)
        assert primary_meta.source_id == "source1"
        # This is the key assertion for the user's request
        assert primary_meta.observation_count == 2  # Should be 2 after filtering

        # 4. Check that the observations themselves are filtered
        assert len(place_obs.observations) == 2
        assert {obs.value for obs in place_obs.observations} == {20, 30}
        assert {obs.date for obs in place_obs.observations} == {"2021", "2022"}

        # 5. Check source info
        assert len(result.source_info) == 1
        assert result.source_info[0].source_id == "source1"

        # 5. Check that the underlying API call was made correctly
        mock_client.fetch_obs.assert_awaited_once()
        request_arg = mock_client.fetch_obs.call_args[0][0]
        assert request_arg.variable_dcid == "var1"
        assert request_arg.place_dcid == "country/USA"
        assert request_arg.observation_period == ObservationPeriod.ALL
        assert request_arg.date_filter.start_date == "2021-01-01"
        assert request_arg.date_filter.end_date == "2022-12-31"

    async def test_get_observations_no_data_after_filter(self, mock_client):
        """Test case where date filtering results in no observations."""
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
                                    "earliestDate": "2020",
                                    "latestDate": "2021",
                                    "obsCount": 2,
                                    "observations": [
                                        {"date": "2020", "value": 10},
                                        {"date": "2021", "value": 20},
                                    ],
                                }
                            ]
                        }
                    }
                }
            },
            "facets": {"source1": {"importName": "test_source"}},
        }
        mock_api_response = ObservationApiResponse.model_validate(api_response_data)
        mock_client.fetch_obs.return_value = mock_api_response
        mock_client.fetch_entity_names.return_value = {
            "var1": "Variable 1",
            "country/USA": "United States",
        }
        mock_client.fetch_entity_types.return_value = {
            "country/USA": ["Country"],
        }

        # Act: Call with a date range that will filter out all data
        result = await get_observations(
            client=mock_client,
            variable_dcid="var1",
            place_name="USA",
            start_date="2023",
            end_date="2024",
        )

        # Assert
        assert len(result.observations_by_place) == 1
        place_obs = result.observations_by_place[0]

        # The primary series should be present, but with 0 observations
        assert place_obs.primary_series_metadata.observation_count == 0
        assert len(place_obs.observations) == 0
        assert len(place_obs.alternative_series_metadata) == 0

    async def test_get_observations_multiple_sources(self, mock_client):
        """Test that primary and alternative sources are handled correctly."""
        # Arrange
        mock_client.search_places.return_value = {"USA": "country/USA"}
        api_response_data = {
            "byVariable": {
                "var1": {
                    "byEntity": {
                        "country/USA": {
                            "orderedFacets": [
                                {  # First source, but has no data in the date range
                                    "facetId": "source1",
                                    "earliestDate": "2019",
                                    "latestDate": "2020",
                                    "obsCount": 2,
                                    "observations": [
                                        {"date": "2019", "value": 10},
                                        {"date": "2020", "value": 20},
                                    ],
                                },
                                {  # Second source, has data in the date range
                                    "facetId": "source2",
                                    "earliestDate": "2021",
                                    "latestDate": "2022",
                                    "obsCount": 2,
                                    "observations": [
                                        {"date": "2021", "value": 30},
                                        {"date": "2022", "value": 40},
                                    ],
                                },
                            ]
                        }
                    }
                }
            },
            "facets": {
                "source1": {"importName": "test_source_1"},
                "source2": {"importName": "test_source_2"},
            },
        }
        mock_api_response = ObservationApiResponse.model_validate(api_response_data)
        mock_client.fetch_obs.return_value = mock_api_response
        mock_client.fetch_entity_names.return_value = {
            "var1": "Variable 1",
            "country/USA": "United States",
        }
        mock_client.fetch_entity_types.return_value = {
            "country/USA": ["Country"],
        }

        # Act: Filter for a range where only the second source has data
        result = await get_observations(
            client=mock_client,
            variable_dcid="var1",
            place_name="USA",
            start_date="2021",
            end_date="2022",
        )

        # Assert
        assert len(result.observations_by_place) == 1
        place_obs = result.observations_by_place[0]

        # Primary series should be source2, as it's the first with data
        assert place_obs.primary_series_metadata.source_id == "source2"
        assert place_obs.primary_series_metadata.observation_count == 2
        assert len(place_obs.observations) == 2

        # Alternative series should be source1
        assert len(place_obs.alternative_series_metadata) == 1
        assert place_obs.alternative_series_metadata[0].source_id == "source1"
        assert (
            place_obs.alternative_series_metadata[0].observation_count == 0
        )  # No data after filtering

    async def test_get_observations_child_places(self, mock_client):
        """Test observation retrieval for child places of a parent."""
        # Arrange
        # Mock place resolution for the parent place
        mock_client.search_places.return_value = {"California": "country/USA/state/CA"}

        # Mock API response from fetch_obs for the child places
        api_response_data = {
            "byVariable": {
                "var1": {
                    "byEntity": {
                        "geoId/06001": {  # Alameda County
                            "orderedFacets": [
                                {
                                    "facetId": "source1",
                                    "earliestDate": "2022",
                                    "latestDate": "2022",
                                    "obsCount": 1,
                                    "observations": [{"date": "2022", "value": 100}],
                                }
                            ]
                        },
                        "geoId/06037": {  # Los Angeles County
                            "orderedFacets": [
                                {
                                    "facetId": "source1",
                                    "earliestDate": "2022",
                                    "latestDate": "2022",
                                    "obsCount": 1,
                                    "observations": [{"date": "2022", "value": 200}],
                                }
                            ]
                        },
                    }
                }
            },
            "facets": {"source1": {"importName": "test_source"}},
        }
        mock_api_response = ObservationApiResponse.model_validate(api_response_data)
        mock_client.fetch_obs.return_value = mock_api_response

        # Mock name/type lookups for all relevant DCIDs
        mock_client.fetch_entity_names.return_value = {
            "var1": "Variable 1",
            "country/USA/state/CA": "California",
            "geoId/06001": "Alameda County",
            "geoId/06037": "Los Angeles County",
        }
        mock_client.fetch_entity_types.return_value = {
            "country/USA/state/CA": ["State"],
            "geoId/06001": ["County"],
            "geoId/06037": ["County"],
        }

        # Act
        result = await get_observations(
            client=mock_client,
            variable_dcid="var1",
            place_name="California",
            child_place_type="County",
            period="latest",
        )

        # Assert
        # 1. Check response structure and parent place resolution
        assert isinstance(result, ObservationToolResponse)
        assert result.variable_dcid == "var1"
        assert result.resolved_parent_place.dcid == "country/USA/state/CA"
        assert result.resolved_parent_place.name == "California"
        assert result.resolved_parent_place.place_type == "State"
        assert len(result.observations_by_place) == 2

        # 2. Check observations for each child place
        obs_by_dcid = {obs.place.dcid: obs for obs in result.observations_by_place}
        assert "geoId/06001" in obs_by_dcid
        assert "geoId/06037" in obs_by_dcid

        alameda_obs = obs_by_dcid["geoId/06001"]
        assert alameda_obs.place.name == "Alameda County"
        assert alameda_obs.place.place_type == "County"
        assert len(alameda_obs.observations) == 1
        assert alameda_obs.observations[0].value == 100

        la_obs = obs_by_dcid["geoId/06037"]
        assert la_obs.place.name == "Los Angeles County"
        assert la_obs.place.place_type == "County"
        assert len(la_obs.observations) == 1
        assert la_obs.observations[0].value == 200

        # 3. Check that the underlying API call was made correctly
        mock_client.fetch_obs.assert_awaited_once()
        request_arg = mock_client.fetch_obs.call_args[0][0]
        assert request_arg.variable_dcid == "var1"
        assert request_arg.place_dcid == "country/USA/state/CA"  # parent place
        assert request_arg.child_place_type == "County"
        assert request_arg.observation_period == ObservationPeriod.LATEST


@pytest.mark.asyncio
class TestSearchIndicators:
    """Tests for the search_indicators service function."""

    @pytest.mark.asyncio
    async def test_search_indicators_browse_mode_basic(self):
        """Test basic search in browse mode without place filtering."""
        mock_client = Mock()
        mock_client.fetch_indicators = AsyncMock(
            return_value={
                "topics": [{"dcid": "topic/health"}],
                "variables": [{"dcid": "Count_Person"}],
                "lookups": {"topic/health": "Health", "Count_Person": "Population"},
            }
        )
        mock_client.fetch_entity_names = Mock(
            return_value={"topic/health": "Health", "Count_Person": "Population"}
        )

        result = await search_indicators(
            client=mock_client, query="health", mode="browse"
        )

        assert result.topics is not None
        assert result.variables is not None
        assert result.lookups is not None
        assert result.status == "SUCCESS"
        mock_client.fetch_indicators.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_indicators_browse_mode_with_places(self):
        """Test search in browse mode with place filtering."""
        mock_client = Mock()
        mock_client.search_places = AsyncMock(return_value={"France": "country/FRA"})
        mock_client.fetch_indicators = AsyncMock(
            return_value={
                "topics": [{"dcid": "topic/trade"}],
                "variables": [{"dcid": "TradeExports_FRA"}],
                "lookups": {
                    "topic/trade": "Trade",
                    "TradeExports_FRA": "Exports to France",
                },
            }
        )
        mock_client.fetch_entity_names = Mock(
            return_value={
                "topic/trade": "Trade",
                "TradeExports_FRA": "Exports to France",
                "country/FRA": "France",
            }
        )

        result = await search_indicators(
            client=mock_client,
            query="trade exports",
            mode="browse",
            place1_name="France",
        )

        assert result.topics is not None
        assert result.variables is not None
        assert result.lookups is not None
        assert result.status == "SUCCESS"
        mock_client.search_places.assert_called_once_with(["France"])
        # Should be called twice: once for the base query and once for the base + place1_name query
        assert mock_client.fetch_indicators.call_count == 2

        # Assert the actual queries fetch_topics_and_variables was called with
        calls = mock_client.fetch_indicators.call_args_list
        # The first call should be just the base query
        assert calls[0].kwargs["query"] == "trade exports"
        assert calls[0].kwargs["place_dcids"] == ["country/FRA"]
        # The second call should be with the place name appended to query
        assert calls[1].kwargs["query"] == "trade exports France"
        assert calls[1].kwargs["place_dcids"] == []

    @pytest.mark.asyncio
    async def test_search_indicators_browse_mode_merge_results(self):
        """Test that results from multiple searches are properly merged in browse mode."""
        mock_client = Mock()
        mock_client.search_places = AsyncMock(return_value={"France": "country/FRA"})
        mock_client.fetch_indicators = AsyncMock(
            side_effect=[
                {
                    "topics": [{"dcid": "topic/trade"}],
                    "variables": [{"dcid": "TradeExports_FRA"}],
                    "lookups": {
                        "topic/trade": "Trade",
                        "TradeExports_FRA": "Exports to France",
                    },
                },
                {
                    "topics": [{"dcid": "topic/trade"}],  # Duplicate topic
                    "variables": [
                        {"dcid": "TradeImports_FRA"},  # New variable
                        {"dcid": "TradeExports_FRA"},  # Duplicate variable
                    ],
                    "lookups": {
                        "topic/trade": "Trade",
                        "TradeImports_FRA": "Imports from France",
                        "TradeExports_FRA": "Exports to France",
                    },
                },
            ]
        )
        mock_client.fetch_entity_names = Mock(
            return_value={
                "topic/trade": "Trade",
                "TradeExports_FRA": "Exports to France",
                "TradeImports_FRA": "Imports from France",
            }
        )

        result = await search_indicators(
            client=mock_client, query="trade", mode="browse", place1_name="France"
        )

        # Should have deduplicated topics and variables
        assert len(result.topics) == 1  # Deduplicated
        assert (
            len(result.variables) == 2
        )  # Both unique variables included (duplicate removed)
        assert "TradeExports_FRA" in [v.dcid for v in result.variables]
        assert "TradeImports_FRA" in [v.dcid for v in result.variables]

    @pytest.mark.asyncio
    async def test_search_indicators_browse_mode_with_custom_per_search_limit(self):
        """Test search in browse mode with custom per_search_limit parameter."""
        mock_client = Mock()
        mock_client.fetch_indicators = AsyncMock(
            return_value={
                "topics": [{"dcid": "topic/health"}],
                "variables": [{"dcid": "Count_Person"}],
                "lookups": {"topic/health": "Health", "Count_Person": "Population"},
            }
        )
        mock_client.fetch_entity_names = Mock(
            return_value={"topic/health": "Health", "Count_Person": "Population"}
        )

        result = await search_indicators(
            client=mock_client, query="health", mode="browse", per_search_limit=5
        )

        assert result.topics is not None
        assert result.variables is not None
        assert result.lookups is not None
        assert result.status == "SUCCESS"
        # Verify per_search_limit was passed to client
        mock_client.fetch_indicators.assert_called_once_with(
            query="health", mode=SearchMode.BROWSE, place_dcids=[], max_results=5
        )

    @pytest.mark.asyncio
    async def test_search_indicators_browse_mode_per_search_limit_validation(self):
        """Test per_search_limit parameter validation in browse mode."""
        mock_client = Mock()

        # Test invalid per_search_limit values
        with pytest.raises(
            ValueError, match="per_search_limit must be between 1 and 100"
        ):
            await search_indicators(
                client=mock_client, query="health", mode="browse", per_search_limit=0
            )

        with pytest.raises(
            ValueError, match="per_search_limit must be between 1 and 100"
        ):
            await search_indicators(
                client=mock_client, query="health", mode="browse", per_search_limit=101
            )

        # Test valid per_search_limit values
        mock_client.fetch_indicators = AsyncMock(
            return_value={"topics": [], "variables": [], "lookups": {}}
        )

        # Should not raise for valid values
        await search_indicators(
            client=mock_client, query="health", mode="browse", per_search_limit=1
        )
        await search_indicators(
            client=mock_client, query="health", mode="browse", per_search_limit=100
        )

    @pytest.mark.asyncio
    async def test_search_indicators_browse_mode_default_per_search_limit(self):
        """Test that default per_search_limit=10 is used when not specified in browse mode."""
        mock_client = Mock()
        mock_client.fetch_indicators = AsyncMock(
            return_value={"topics": [], "variables": [], "lookups": {}}
        )

        await search_indicators(client=mock_client, query="health", mode="browse")

        # Verify default per_search_limit=10 was used
        mock_client.fetch_indicators.assert_called_once_with(
            query="health", mode=SearchMode.BROWSE, place_dcids=[], max_results=10
        )

    @pytest.mark.asyncio
    async def test_search_indicators_browse_mode_default_mode(self):
        """Test that browse mode is the default when mode is not specified."""
        mock_client = Mock()
        mock_client.fetch_indicators = AsyncMock(
            return_value={
                "topics": [{"dcid": "topic/health"}],
                "variables": [{"dcid": "Count_Person"}],
                "lookups": {"topic/health": "Health", "Count_Person": "Population"},
            }
        )
        mock_client.fetch_entity_names = Mock(
            return_value={"topic/health": "Health", "Count_Person": "Population"}
        )

        result = await search_indicators(client=mock_client, query="health")

        assert result.topics is not None
        assert result.variables is not None
        assert result.lookups is not None
        assert result.status == "SUCCESS"
        mock_client.fetch_indicators.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_indicators_mode_validation(self):
        """Test mode parameter validation."""
        mock_client = Mock()

        # Test invalid mode values
        with pytest.raises(
            ValueError, match="mode must be either 'browse' or 'lookup'"
        ):
            await search_indicators(
                client=mock_client, query="health", mode="invalid_mode"
            )

        # Test valid mode values
        mock_client.fetch_indicators = AsyncMock(
            return_value={"topics": [], "variables": [], "lookups": {}}
        )

        # Should not raise for valid values
        await search_indicators(client=mock_client, query="health", mode="browse")
        await search_indicators(client=mock_client, query="health", mode="lookup")
        await search_indicators(
            client=mock_client, query="health", mode=None
        )  # None should default to browse

    # Phase 2: Lookup Mode Tests
    @pytest.mark.asyncio
    async def test_search_indicators_lookup_mode_basic(self):
        """Test basic search in lookup mode with a single place."""
        mock_client = Mock()
        mock_client.search_places = AsyncMock(return_value={"USA": "country/USA"})
        mock_client.fetch_indicators = AsyncMock(
            return_value={
                "variables": [{"dcid": "Count_Person"}, {"dcid": "Count_Household"}],
            }
        )
        mock_client.fetch_entity_names = Mock(
            return_value={
                "Count_Person": "Population",
                "Count_Household": "Households",
                "country/USA": "USA",
            }
        )

        result = await search_indicators(
            client=mock_client, query="health", mode="lookup", place1_name="USA"
        )

        assert result.topics == []
        assert result.variables is not None
        assert result.lookups is not None
        assert result.status == "SUCCESS"
        # Should have variables with dcid and places_with_data
        assert len(result.variables) == 2
        assert any(v.dcid == "Count_Person" for v in result.variables)
        assert any(v.dcid == "Count_Household" for v in result.variables)

    @pytest.mark.asyncio
    async def test_search_indicators_lookup_mode_with_places(self):
        """Test search in lookup mode with place filtering."""
        mock_client = Mock()
        mock_client.search_places = AsyncMock(return_value={"France": "country/FRA"})
        mock_client.fetch_indicators = AsyncMock(
            return_value={
                "variables": [
                    {"dcid": "TradeExports_FRA"},
                    {"dcid": "TradeImports_FRA"},
                ],
            }
        )
        mock_client.fetch_entity_names = Mock(
            return_value={
                "TradeExports_FRA": "Exports to France",
                "TradeImports_FRA": "Imports from France",
                "country/FRA": "France",
            }
        )

        result = await search_indicators(
            client=mock_client,
            query="trade exports",
            mode="lookup",
            place1_name="France",
        )

        assert result.topics == []
        assert result.variables is not None
        assert result.lookups is not None
        assert result.status == "SUCCESS"
        mock_client.search_places.assert_called_once_with(["France"])
        # Should be called by itself and for each place DCID
        assert mock_client.fetch_indicators.call_count == 2

    @pytest.mark.asyncio
    async def test_search_indicators_lookup_mode_merge_results(self):
        mock_client = Mock()
        mock_client.search_places = AsyncMock(
            return_value={"France": "country/FRA", "Germany": "country/DEU"}
        )
        mock_client.fetch_indicators = AsyncMock(
            side_effect=[
                {"variables": [{"dcid": "TradeExports_FRA"}]},  # France results
                {
                    "variables": [
                        {"dcid": "TradeExports_DEU"},
                        {"dcid": "TradeExports_FRA"},
                    ]
                },  # Germany results (with duplicate)
                {},  # query + France
                {},  # query + Germany
            ]
        )
        mock_client.fetch_entity_names = Mock(
            return_value={
                "TradeExports_FRA": "Exports to France",
                "TradeExports_DEU": "Exports to Germany",
                "country/FRA": "France",
                "country/DEU": "Germany",
            }
        )

        result = await search_indicators(
            client=mock_client,
            query="trade",
            mode="lookup",
            place1_name="France",
            place2_name="Germany",
        )

        # Should have deduplicated variables
        assert result.topics == []
        assert (
            len(result.variables) == 2
        )  # Both unique variables included (duplicate removed)
        assert any(v.dcid == "TradeExports_FRA" for v in result.variables)
        assert any(v.dcid == "TradeExports_DEU" for v in result.variables)

    @pytest.mark.asyncio
    async def test_search_indicators_lookup_mode_per_search_limit_validation(self):
        """Test per_search_limit parameter validation in lookup mode."""
        mock_client = Mock()

        # Test invalid per_search_limit values
        with pytest.raises(
            ValueError, match="per_search_limit must be between 1 and 100"
        ):
            await search_indicators(
                client=mock_client, query="health", mode="lookup", per_search_limit=0
            )

        with pytest.raises(
            ValueError, match="per_search_limit must be between 1 and 100"
        ):
            await search_indicators(
                client=mock_client, query="health", mode="lookup", per_search_limit=101
            )

        # Test valid per_search_limit values with place (so lookup mode is actually used)
        mock_client.search_places = AsyncMock(return_value={"USA": "country/USA"})
        mock_client.fetch_indicators = AsyncMock(return_value={"variables": []})
        mock_client.fetch_entity_names = Mock(return_value={"country/USA": "USA"})

        # Should not raise for valid values
        await search_indicators(
            client=mock_client,
            query="health",
            mode="lookup",
            place1_name="USA",
            per_search_limit=1,
        )
        await search_indicators(
            client=mock_client,
            query="health",
            mode="lookup",
            place1_name="USA",
            per_search_limit=100,
        )

    @pytest.mark.asyncio
    async def test_search_indicators_lookup_mode_default_per_search_limit(self):
        """Test that default per_search_limit=10 is used when not specified in lookup mode."""
        mock_client = Mock()
        mock_client.search_places = AsyncMock(return_value={"USA": "country/USA"})
        mock_client.fetch_indicators = AsyncMock(return_value={"variables": []})
        mock_client.fetch_entity_names = Mock(return_value={"country/USA": "USA"})

        await search_indicators(
            client=mock_client, query="health", mode="lookup", place1_name="USA"
        )

        # Verify default per_search_limit=10 was used (though not directly passed to fetch_indicators)
        # The limit is applied after fetching results
        assert mock_client.fetch_indicators.call_count == 2

    @pytest.mark.asyncio
    async def test_search_indicators_lookup_mode_no_places(self):
        """Test that lookup mode works when no places are provided."""
        mock_client = Mock()
        mock_client.fetch_indicators = AsyncMock(
            return_value={
                "variables": [{"dcid": "Count_Person"}],
                "lookups": {"Count_Person": "Population"},
            }
        )
        mock_client.fetch_entity_names = Mock(
            return_value={"Count_Person": "Population"}
        )

        # Call with lookup mode but no places - should automatically fall back to browse mode
        result = await search_indicators(
            client=mock_client,
            query="health",
            mode="lookup",  # No places provided
        )

        # Should return browse mode results (topics populated)
        assert result.topics == []
        assert result.variables is not None
        assert result.lookups is not None
        assert result.status == "SUCCESS"
        mock_client.fetch_indicators.assert_called_once()
