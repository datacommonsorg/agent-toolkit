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
    ObservationRequest,
    ObservationToolResponse,
)
from datacommons_mcp.data_models.search import SearchMode
from datacommons_mcp.exceptions import DataLookupError
from datacommons_mcp.services import (
    _validate_and_build_request,
    get_observations,
    search_indicators,
)


@pytest.mark.asyncio
class TestValidateAndBuildRequest:
    @pytest.fixture
    def mock_client(self):
        client = Mock(spec=DCClient)
        client.search_places = AsyncMock()
        return client

    async def test_validation_errors(self, mock_client):
        # Missing variable
        with pytest.raises(ValueError, match="'variable_dcid' must be specified."):
            await _validate_and_build_request(
                mock_client, variable_dcid="", place_name="USA"
            )

        # Missing place
        with pytest.raises(
            ValueError, match="Specify either 'place_name' or 'place_dcid'"
        ):
            await _validate_and_build_request(mock_client, variable_dcid="var1")

        # Incomplete date range
        with pytest.raises(
            ValueError, match="Both 'start_date' and 'end_date' are required"
        ):
            await _validate_and_build_request(
                mock_client, variable_dcid="var1", place_name="USA", start_date="2022"
            )

    async def test_with_dcids(self, mock_client):
        request = await _validate_and_build_request(
            mock_client, variable_dcid="var1", place_dcid="country/USA"
        )
        assert request.variable_dcid == "var1"
        assert request.place_dcid == "country/USA"
        assert request.observation_period == ObservationPeriod.LATEST
        mock_client.search_places.assert_not_called()

    async def test_with_resolution_success(self, mock_client):
        mock_client.search_places.return_value = {"USA": "country/USA"}

        request = await _validate_and_build_request(
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
            await _validate_and_build_request(
                mock_client, variable_dcid="var1", place_name="invalid"
            )


class TestGetObservations:
    @pytest.fixture
    def mock_client(self):
        client = Mock(spec=DCClient)
        client.search_places = AsyncMock()
        client.fetch_obs = AsyncMock()
        client.fetch_entity_names = AsyncMock()
        client.fetch_entity_types = AsyncMock()
        return client

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

    @pytest.mark.asyncio
    async def test_fetch_all_metadata(self, mock_client, mock_api_response):
        """Test _fetch_all_metadata fetches names and types for all entities."""
        # Arrange
        variable_dcid = "var1"
        parent_place_dcid = "northamerica"
        expected_dcids = {"country/USA", "country/CAN", "northamerica"}

        mock_client.fetch_entity_names.return_value = {
            "country/USA": "United States",
            "country/CAN": "Canada",
            "northamerica": "North America",
        }
        mock_client.fetch_entity_types.return_value = {
            "country/USA": ["Country"],
            "country/CAN": ["Country"],
            "northamerica": ["Continent"],
        }

        # Act
        from datacommons_mcp.services import _fetch_all_metadata

        metadata_map = await _fetch_all_metadata(
            mock_client, variable_dcid, mock_api_response, parent_place_dcid
        )

        # Assert
        assert set(metadata_map.keys()) == expected_dcids
        assert metadata_map["country/USA"].name == "United States"
        assert metadata_map["country/USA"].type_of == ["Country"]
        assert metadata_map["northamerica"].name == "North America"
        assert metadata_map["northamerica"].type_of == ["Continent"]

        # Assert that the mock was called with the correct set of DCIDs, ignoring order.
        mock_client.fetch_entity_names.assert_awaited_once()
        assert set(mock_client.fetch_entity_names.call_args[0][0]) == expected_dcids
        mock_client.fetch_entity_types.assert_awaited_once()
        assert set(mock_client.fetch_entity_types.call_args[0][0]) == expected_dcids

    @pytest.mark.asyncio
    async def test_fetch_all_metadata_no_parent_place(
        self, mock_client, mock_api_response
    ):
        """Test _fetch_all_metadata when parent_place_dcid is None."""
        # Arrange
        variable_dcid = "var1"
        parent_place_dcid = None  # Test case where this is not provided
        expected_dcids = {"country/USA", "country/CAN"}

        mock_client.fetch_entity_names.return_value = {
            "country/USA": "United States",
            "country/CAN": "Canada",
        }
        mock_client.fetch_entity_types.return_value = {
            "country/USA": ["Country"],
            "country/CAN": ["Country"],
        }

        # Act
        from datacommons_mcp.services import _fetch_all_metadata

        metadata_map = await _fetch_all_metadata(
            mock_client, variable_dcid, mock_api_response, parent_place_dcid
        )

        # Assert
        assert set(metadata_map.keys()) == expected_dcids

        # Assert that the mock was called with the correct set of DCIDs, ignoring order.
        mock_client.fetch_entity_names.assert_awaited_once()
        assert set(mock_client.fetch_entity_names.call_args[0][0]) == expected_dcids
        mock_client.fetch_entity_types.assert_awaited_once()
        assert set(mock_client.fetch_entity_types.call_args[0][0]) == expected_dcids

    def test_select_primary_source(self, mock_api_response):
        """Test the logic for selecting the primary source."""
        # Arrange
        variable_data = mock_api_response.byVariable["var1"]
        request = ObservationRequest(
            variable_dcid="var1",
            place_dcid="any",
            date_filter=None,
            observation_period=ObservationPeriod.ALL,
        )

        # Act
        from datacommons_mcp.services import _select_primary_source

        primary_id, alt_counts, processed_data = _select_primary_source(
            variable_data, request
        )

        # Assert
        # source1 has more observations (3 vs 2), so it should be primary
        assert primary_id == "source1"
        assert alt_counts == {"source2": 1}
        assert "country/USA" in processed_data
        assert "country/CAN" in processed_data
        assert len(processed_data["country/USA"]["observations"]) == 3
        assert len(processed_data["country/CAN"]["observations"]) == 2

    def test_select_primary_source_with_date_filter(self, mock_api_response):
        """Test primary source selection when a date filter is active."""
        # Arrange
        variable_data = mock_api_response.byVariable["var1"]
        request = ObservationRequest(
            variable_dcid="var1",
            place_dcid="any",
            observation_period=ObservationPeriod.ALL,
            date_filter={"start_date": "2022-01-01", "end_date": "2022-12-31"},
        )

        # Act
        from datacommons_mcp.services import _select_primary_source

        primary_id, alt_counts, processed_data = _select_primary_source(
            variable_data, request
        )

        # Assert
        # After filtering for 2022, both sources have 1 place and 1 observation.
        # The tie-breaker is the source_id string itself, where max() chooses the
        # alphabetically later string.
        assert primary_id == "source2"
        assert alt_counts == {"source1": 1}
        assert len(processed_data["country/USA"]["observations"]) == 1
        assert processed_data["country/USA"]["observations"][0].date == "2022"
        assert len(processed_data["country/CAN"]["observations"]) == 1
        assert processed_data["country/CAN"]["observations"][0].date == "2022"

    @pytest.mark.asyncio
    async def test_get_observations_e2e_single_place(self, mock_client):
        """Test the full get_observations flow for a single place."""
        # Arrange
        # This mock response is specific to this test and only contains data for the requested place.
        single_place_api_response_data = {
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
                        }
                    }
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
            start_date="2021",
            end_date="2022",
        )

        # Assert
        assert isinstance(result, ObservationToolResponse)
        assert result.variable_dcid == "var1"
        assert result.resolved_parent_place is None
        assert result.child_place_type is None

        # Check observations
        assert len(result.observations_by_place) == 1
        obs = result.observations_by_place[0]
        assert obs.place.dcid == "country/USA"
        assert obs.place.name == "United States"
        assert obs.place.place_type == "Country"
        assert obs.source_id == "source1"
        assert len(obs.observations) == 2
        assert {"2021": 20} in obs.observations
        assert {"2022": 30} in obs.observations

        # Check source info
        assert result.observations_source.source_id == "source1"
        assert result.observations_source.importName == "Source One"
        assert len(result.alternative_sources) == 0  # No other sources for USA

    @pytest.mark.asyncio
    async def test_get_observations_e2e_child_places(self, mock_client):
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
            period="latest",
        )

        # Assert
        assert result.resolved_parent_place.name == "California"
        assert result.child_place_type == "County"
        assert len(result.observations_by_place) == 3

        # Check primary source (source1 has more places)
        assert result.observations_source.source_id == "source1"

        # Check alternative sources
        assert len(result.alternative_sources) == 1
        alt_source = result.alternative_sources[0]
        assert alt_source.source_id == "source2"
        assert alt_source.num_available_places == 1

        # Check observations
        obs_by_dcid = {obs.place.dcid: obs for obs in result.observations_by_place}
        assert obs_by_dcid["geoId/06001"].source_id == "source1"
        assert obs_by_dcid["geoId/06001"].observations[0]["2022"] == 100
        assert obs_by_dcid["geoId/06037"].source_id == "source1"
        assert obs_by_dcid["geoId/06037"].observations[0]["2022"] == 200
        assert obs_by_dcid["geoId/06085"].source_id == "source2"
        assert obs_by_dcid["geoId/06085"].observations[0]["2022"] == 300


@pytest.mark.asyncio
class TestSearchIndicators:
    """Tests for the search_indicators service function."""

    @pytest.mark.asyncio
    async def test_search_indicators_browse_mode_basic(self):
        """Test basic search in browse mode without place filtering."""
        mock_client = Mock()
        mock_client.fetch_indicators = AsyncMock(
            return_value={"topics": [], "variables": [], "lookups": {}}
        )
        mock_client.fetch_entity_names = Mock(return_value={})

        result = await search_indicators(
            client=mock_client, query="health", mode="browse"
        )

        assert result.topics is not None
        assert result.variables is not None
        assert result.dcid_name_mappings is not None
        assert result.status == "SUCCESS"
        mock_client.fetch_indicators.assert_called_once_with(
            query="health", mode=SearchMode.BROWSE, place_dcids=[], max_results=10
        )

    @pytest.mark.asyncio
    async def test_search_indicators_browse_mode_with_places(self):
        """Test search in browse mode with place filtering."""
        mock_client = Mock()
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
        mock_client.fetch_entity_names = AsyncMock(
            return_value={
                "topic/trade": "Trade",
                "TradeExports_FRA": "Exports to France",
                "TradeImports_FRA": "Imports from France",
            }
        )

        result = await search_indicators(
            client=mock_client, query="trade", mode="browse", places=["France"]
        )

        # Should have both topics and variables in expected order
        expected_topic_dcids = ["topic/trade"]
        expected_variable_dcids = ["TradeExports_FRA", "TradeImports_FRA"]
        actual_topic_dcids = [t.dcid for t in result.topics]
        actual_variable_dcids = [v.dcid for v in result.variables]
        assert actual_topic_dcids == expected_topic_dcids
        assert actual_variable_dcids == expected_variable_dcids

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
        mock_client.fetch_entity_names = AsyncMock(
            return_value={"topic/health": "Health", "Count_Person": "Population"}
        )

        await search_indicators(
            client=mock_client, query="health", mode="browse", per_search_limit=5
        )

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
        mock_client.fetch_indicators = AsyncMock(return_value={})

        # Should not raise for valid values
        await search_indicators(
            client=mock_client, query="health", mode="browse", per_search_limit=1
        )
        await search_indicators(
            client=mock_client, query="health", mode="browse", per_search_limit=100
        )

    @pytest.mark.asyncio
    async def test_search_indicators_browse_mode_default_mode(self):
        """Test that browse mode is the default when mode is not specified."""
        mock_client = Mock()
        mock_client.fetch_indicators = AsyncMock(
            return_value={"topics": [], "variables": [], "lookups": {}}
        )
        mock_client.fetch_entity_names = Mock(return_value={})

        await search_indicators(client=mock_client, query="health")

        mock_client.fetch_indicators.assert_called_once_with(
            query="health", mode=SearchMode.BROWSE, place_dcids=[], max_results=10
        )

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
            return_value={"topics": [], "variables": [], "dcid_name_mappings": {}}
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
        mock_client.fetch_entity_names = AsyncMock(
            return_value={
                "Count_Person": "Population",
                "Count_Household": "Households",
                "country/USA": "USA",
            }
        )

        result = await search_indicators(
            client=mock_client, query="health", mode="lookup", places=["USA"]
        )

        # Should have variables with dcid and places_with_data in expected order
        expected_variable_dcids = ["Count_Person", "Count_Household"]
        actual_variable_dcids = [v.dcid for v in result.variables]
        assert actual_variable_dcids == expected_variable_dcids

    @pytest.mark.asyncio
    async def test_search_indicators_lookup_mode_merge_results(self):
        """Test that results from multiple bilateral searches are properly merged and deduplicated in lookup mode."""
        mock_client = Mock()
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
        mock_client.fetch_entity_names = AsyncMock(
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
            bilateral_places=["France", "Germany"],
        )

        # Should have deduplicated variables in expected order
        assert result.topics == []
        expected_variable_dcids = ["TradeExports_FRA", "TradeExports_DEU"]
        actual_variable_dcids = [v.dcid for v in result.variables]
        assert actual_variable_dcids == expected_variable_dcids

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
        mock_client.fetch_entity_names = AsyncMock(return_value={"country/USA": "USA"})

        # Should not raise for valid values
        await search_indicators(
            client=mock_client,
            query="health",
            mode="lookup",
            places=["USA"],
            per_search_limit=1,
        )
        await search_indicators(
            client=mock_client,
            query="health",
            mode="lookup",
            places=["USA"],
            per_search_limit=100,
        )

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
        mock_client.fetch_entity_names = AsyncMock(
            return_value={"Count_Person": "Population"}
        )

        # Call with lookup mode but no places - should automatically fall back to browse mode
        result = await search_indicators(
            client=mock_client,
            query="health",
            mode="lookup",  # No places provided
        )

        # Should return lookup mode results (variables only)
        assert result.topics == []
        assert result.variables is not None
        assert result.dcid_name_mappings is not None
        assert result.status == "SUCCESS"
        mock_client.fetch_indicators.assert_called_once_with(
            query="health", mode=SearchMode.LOOKUP, place_dcids=[], max_results=10
        )

    @pytest.mark.asyncio
    async def test_search_indicators_places_parameter_behavior(self):
        """Test places parameter behavior across browse and lookup modes."""
        mock_client = Mock()
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
        mock_client.fetch_entity_names = Mock(return_value={})

        # Test 1: Single place in browse mode
        result = await search_indicators(
            client=mock_client,
            query="trade exports",
            mode="browse",
            places=["France"],
        )
        assert result.status == "SUCCESS"
        mock_client.search_places.assert_called_with(["France"])
        mock_client.fetch_indicators.assert_called_once_with(
            query="trade exports",
            mode=SearchMode.BROWSE,
            place_dcids=["country/FRA"],
            max_results=10,
        )

        # Reset mocks for next test
        mock_client.reset_mock()
        mock_client.search_places = AsyncMock(return_value={"France": "country/FRA"})
        mock_client.fetch_indicators = AsyncMock(
            return_value={"topics": [], "variables": [], "lookups": {}}
        )
        mock_client.fetch_entity_names = Mock(return_value={})

        # Test 2: Single place in lookup mode
        result = await search_indicators(
            client=mock_client,
            query="trade exports",
            mode="lookup",
            places=["France"],
        )
        assert result.status == "SUCCESS"
        mock_client.search_places.assert_called_with(["France"])
        mock_client.fetch_indicators.assert_called_once_with(
            query="trade exports",
            mode=SearchMode.LOOKUP,
            place_dcids=["country/FRA"],
            max_results=10,
        )

        # Reset mocks for next test
        mock_client.reset_mock()
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
        mock_client.fetch_entity_names = Mock(return_value={})

        # Test 3: Multiple places
        result = await search_indicators(
            client=mock_client,
            query="trade exports",
            mode="browse",
            places=["USA", "Canada", "Mexico"],
        )
        assert result.status == "SUCCESS"
        mock_client.search_places.assert_called_with(["USA", "Canada", "Mexico"])
        mock_client.fetch_indicators.assert_called_once_with(
            query="trade exports",
            mode=SearchMode.BROWSE,
            place_dcids=["country/USA", "country/CAN", "country/MEX"],
            max_results=10,
        )

    @pytest.mark.asyncio
    async def test_search_indicators_bilateral_places_behavior(self):
        """Test bilateral_places parameter behavior across browse and lookup modes."""
        mock_client = Mock()
        mock_client.search_places = AsyncMock(
            return_value={"USA": "country/USA", "France": "country/FRA"}
        )
        mock_client.fetch_indicators = AsyncMock(
            return_value={"topics": [], "variables": [], "lookups": {}}
        )
        mock_client.fetch_entity_names = Mock(return_value={})

        # Test 1: Bilateral places in browse mode
        result = await search_indicators(
            client=mock_client,
            query="trade exports",
            mode="browse",
            bilateral_places=["USA", "France"],
        )
        assert result.status == "SUCCESS"
        mock_client.search_places.assert_called_with(["USA", "France"])
        assert mock_client.fetch_indicators.call_count == 3

        # Assert the actual queries fetch_indicators was called with
        calls = mock_client.fetch_indicators.call_args_list
        # The first call should be just the base query with both place DCIDs
        assert calls[0].kwargs == {
            "query": "trade exports",
            "mode": SearchMode.BROWSE,
            "place_dcids": ["country/USA", "country/FRA"],
            "max_results": 10,
        }
        # The second call should be with USA appended to query, filtered by France
        assert calls[1].kwargs == {
            "query": "trade exports USA",
            "mode": SearchMode.BROWSE,
            "place_dcids": ["country/FRA"],
            "max_results": 10,
        }
        # The third call should be with France appended to query, filtered by USA
        assert calls[2].kwargs == {
            "query": "trade exports France",
            "mode": SearchMode.BROWSE,
            "place_dcids": ["country/USA"],
            "max_results": 10,
        }

        # Reset mocks for next test
        mock_client.reset_mock()
        mock_client.search_places = AsyncMock(
            return_value={"USA": "country/USA", "France": "country/FRA"}
        )
        mock_client.fetch_indicators = AsyncMock(
            return_value={"topics": [], "variables": [], "lookups": {}}
        )
        mock_client.fetch_entity_names = Mock(return_value={})

        # Test 2: Bilateral places in lookup mode
        result = await search_indicators(
            client=mock_client,
            query="trade exports",
            mode="lookup",
            bilateral_places=["USA", "France"],
        )
        assert result.status == "SUCCESS"
        mock_client.search_places.assert_called_with(["USA", "France"])
        assert mock_client.fetch_indicators.call_count == 3

        # Assert the same query rewriting behavior
        calls = mock_client.fetch_indicators.call_args_list
        # The first call should be just the base query with both place DCIDs
        assert calls[0].kwargs == {
            "query": "trade exports",
            "mode": SearchMode.LOOKUP,
            "place_dcids": ["country/USA", "country/FRA"],
            "max_results": 10,
        }
        # The second call should be with USA appended to query, filtered by France
        assert calls[1].kwargs == {
            "query": "trade exports USA",
            "mode": SearchMode.LOOKUP,
            "place_dcids": ["country/FRA"],
            "max_results": 10,
        }
        # The third call should be with France appended to query, filtered by USA
        assert calls[2].kwargs == {
            "query": "trade exports France",
            "mode": SearchMode.LOOKUP,
            "place_dcids": ["country/USA"],
            "max_results": 10,
        }

    @pytest.mark.asyncio
    async def test_search_indicators_parameter_validation(self):
        """Test parameter validation for new place parameters."""
        mock_client = Mock()
        mock_client.search_places = AsyncMock(
            return_value={"USA": "country/USA", "France": "country/FRA"}
        )
        mock_client.fetch_indicators = AsyncMock(return_value={"variables": []})
        mock_client.fetch_entity_names = AsyncMock(return_value={})

        # Test both places and bilateral_places specified (should raise ValueError)
        with pytest.raises(
            ValueError, match="Cannot specify both 'places' and 'bilateral_places'"
        ):
            await search_indicators(
                client=mock_client,
                query="test",
                places=["USA"],
                bilateral_places=["USA", "France"],
            )

        # Test bilateral_places with != 2 items (should raise ValueError)
        with pytest.raises(
            ValueError, match="bilateral_places must contain exactly 2 place names"
        ):
            await search_indicators(
                client=mock_client,
                query="test",
                bilateral_places=["USA"],  # Only 1 place
            )

        with pytest.raises(
            ValueError, match="bilateral_places must contain exactly 2 place names"
        ):
            await search_indicators(
                client=mock_client,
                query="test",
                bilateral_places=["USA", "France", "Germany"],  # 3 places
            )

        # Test valid combinations (should not raise)
        # Single place
        result = await search_indicators(
            client=mock_client,
            query="test",
            places=["USA"],
        )
        assert result.status == "SUCCESS"

        # Multiple places
        result = await search_indicators(
            client=mock_client,
            query="test",
            places=["USA", "Canada"],
        )
        assert result.status == "SUCCESS"

        # Bilateral places
        result = await search_indicators(
            client=mock_client,
            query="test",
            bilateral_places=["USA", "France"],
        )
        assert result.status == "SUCCESS"

        # No places
        result = await search_indicators(client=mock_client, query="test")
        assert result.status == "SUCCESS"
