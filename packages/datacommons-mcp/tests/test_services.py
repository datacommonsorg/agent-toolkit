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
from datacommons_mcp.data_models.observations import ObservationPeriod
from datacommons_mcp.exceptions import NoDataFoundError
from datacommons_mcp.services import _build_observation_request, get_observations, search_topics_and_variables, search_indicators


@pytest.mark.asyncio
class TestBuildObservationRequest:
    @pytest.fixture
    def mock_client(self):
        client = Mock()
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
        with pytest.raises(NoDataFoundError, match="NoDataFoundError: No place found"):
            await _build_observation_request(
                mock_client, variable_dcid="var1", place_name="invalid"
            )


@pytest.mark.asyncio
class TestGetObservations:
    @pytest.fixture
    def mock_client(self):
        client = Mock()
        client.search_places = AsyncMock()
        client.fetch_obs = AsyncMock()
        return client

    async def test_get_observations_success(self, mock_client):
        """Test successful observation retrieval."""
        # Setup mocks
        mock_client.search_places.return_value = {"USA": "country/USA"}
        mock_response = Mock()
        mock_client.fetch_obs.return_value = mock_response

        # Call the function
        result = await get_observations(
            client=mock_client,
            variable_dcid="Count_Person",
            place_name="USA",
            period="latest"
        )

        # Verify the result
        assert result == mock_response
        
        # Verify search_places was called
        mock_client.search_places.assert_awaited_once_with(["USA"])
        
        # Verify fetch_obs was called with the correct request
        mock_client.fetch_obs.assert_awaited_once()
        call_args = mock_client.fetch_obs.call_args[0][0]
        assert call_args.variable_dcid == "Count_Person"
        assert call_args.place_dcid == "country/USA"
        assert call_args.observation_period == ObservationPeriod.LATEST

    async def test_get_observations_with_dcid(self, mock_client):
        """Test observation retrieval with direct DCID."""
        # Setup mocks
        mock_response = Mock()
        mock_client.fetch_obs.return_value = mock_response

        # Call the function
        result = await get_observations(
            client=mock_client,
            variable_dcid="Count_Person",
            place_dcid="country/USA",
            period="latest"
        )

        # Verify the result
        assert result == mock_response
        
        # Verify search_places was NOT called (since we provided DCID)
        mock_client.search_places.assert_not_called()
        
        # Verify fetch_obs was called with the correct request
        mock_client.fetch_obs.assert_awaited_once()
        call_args = mock_client.fetch_obs.call_args[0][0]
        assert call_args.variable_dcid == "Count_Person"
        assert call_args.place_dcid == "country/USA"
        assert call_args.observation_period == ObservationPeriod.LATEST


@pytest.mark.asyncio
class TestSearchTopicsAndVariables:
    """Tests for the search_topics_and_variables service function."""

    @pytest.mark.asyncio
    async def test_search_topics_and_variables_basic(self):
        """Test basic search without place filtering."""
        mock_client = Mock()
        mock_client.fetch_topics_and_variables = AsyncMock(return_value={
            "topics": [{"dcid": "topic/health"}],
            "variables": [{"dcid": "Count_Person"}],
            "lookups": {"topic/health": "Health", "Count_Person": "Population"}
        })

        result = await search_topics_and_variables(
            client=mock_client,
            query="health"
        )

        assert "topics" in result
        assert "variables" in result
        assert "lookups" in result
        mock_client.fetch_topics_and_variables.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_topics_and_variables_with_places(self):
        """Test search with place filtering."""
        mock_client = Mock()
        mock_client.search_places = AsyncMock(return_value={"France": "country/FRA"})
        mock_client.fetch_topics_and_variables = AsyncMock(return_value={
            "topics": [{"dcid": "topic/trade"}],
            "variables": [{"dcid": "TradeExports_FRA"}],
            "lookups": {"topic/trade": "Trade", "TradeExports_FRA": "Exports to France"}
        })

        result = await search_topics_and_variables(
            client=mock_client,
            query="trade exports",
            place1_name="France"
        )

        assert "topics" in result
        assert "variables" in result
        assert "lookups" in result
        mock_client.search_places.assert_called_once_with(["France"])
        # Should be called twice: once for the base query and once for the base + place1_name query
        assert mock_client.fetch_topics_and_variables.call_count == 2

        # Assert the actual queries fetch_topics_and_variables was called with
        calls = mock_client.fetch_topics_and_variables.call_args_list
        # The first call should be just the base query
        assert calls[0].kwargs["query"] == "trade exports"
        assert calls[0].kwargs["place_dcids"] == ["country/FRA"]
        # The second call should be with the place name appended to query
        assert calls[1].kwargs["query"] == "trade exports France"
        assert calls[1].kwargs["place_dcids"] == []  

    @pytest.mark.asyncio
    async def test_search_topics_and_variables_merge_results(self):
        """Test that results from multiple searches are properly merged."""
        mock_client = Mock()
        mock_client.search_places = AsyncMock(return_value={"France": "country/FRA"})
        mock_client.fetch_topics_and_variables = AsyncMock(side_effect=[
            {
                "topics": [{"dcid": "topic/trade"}],
                "variables": [{"dcid": "TradeExports_FRA"}],
                "lookups": {
                    "topic/trade": "Trade", 
                    "TradeExports_FRA": "Exports to France"
                }
            },
            {
                "topics": [{"dcid": "topic/trade"}],  # Duplicate topic
                "variables": [
                    {"dcid": "TradeImports_FRA"},  # New variable
                    {"dcid": "TradeExports_FRA"}   # Duplicate variable
                ],
                "lookups": {
                    "topic/trade": "Trade", 
                    "TradeImports_FRA": "Imports from France", 
                    "TradeExports_FRA": "Exports to France"
                }
            }
        ])
        mock_client.fetch_entity_names = Mock(return_value={
            "topic/trade": "Trade",
            "TradeExports_FRA": "Exports to France",
            "TradeImports_FRA": "Imports from France"
        })

        result = await search_topics_and_variables(
            client=mock_client,
            query="trade",
            place1_name="France"
        )

        # Should have deduplicated topics and variables
        assert len(result["topics"]) == 1  # Deduplicated
        assert len(result["variables"]) == 2  # Both unique variables included (duplicate removed)
        assert "TradeExports_FRA" in [v.dcid for v in result["variables"]]
        assert "TradeImports_FRA" in [v.dcid for v in result["variables"]]

    @pytest.mark.asyncio
    async def test_search_topics_and_variables_with_custom_per_search_limit(self):
        """Test search with custom per_search_limit parameter."""
        mock_client = Mock()
        mock_client.fetch_topics_and_variables = AsyncMock(return_value={
            "topics": [{"dcid": "topic/health"}],
            "variables": [{"dcid": "Count_Person"}],
            "lookups": {"topic/health": "Health", "Count_Person": "Population"}
        })

        result = await search_topics_and_variables(
            client=mock_client,
            query="health",
            per_search_limit=5
        )

        assert "topics" in result
        assert "variables" in result
        assert "lookups" in result
        # Verify per_search_limit was passed to client
        mock_client.fetch_topics_and_variables.assert_called_once_with(
            query="health", place_dcids=[], max_results=5
        )

    @pytest.mark.asyncio
    async def test_search_topics_and_variables_per_search_limit_validation(self):
        """Test per_search_limit parameter validation."""
        mock_client = Mock()

        # Test invalid per_search_limit values
        with pytest.raises(ValueError, match="per_search_limit must be between 1 and 100"):
            await search_topics_and_variables(
                client=mock_client,
                query="health",
                per_search_limit=0
            )

        with pytest.raises(ValueError, match="per_search_limit must be between 1 and 100"):
            await search_topics_and_variables(
                client=mock_client,
                query="health",
                per_search_limit=101
            )

        # Test valid per_search_limit values
        mock_client.fetch_topics_and_variables = AsyncMock(return_value={
            "topics": [], "variables": [], "lookups": {}
        })

        # Should not raise for valid values
        await search_topics_and_variables(client=mock_client, query="health", per_search_limit=1)
        await search_topics_and_variables(client=mock_client, query="health", per_search_limit=100)

    @pytest.mark.asyncio
    async def test_search_topics_and_variables_default_per_search_limit(self):
        """Test that default per_search_limit=10 is used when not specified."""
        mock_client = Mock()
        mock_client.fetch_topics_and_variables = AsyncMock(return_value={
            "topics": [], "variables": [], "lookups": {}
        })

        await search_topics_and_variables(client=mock_client, query="health")

        # Verify default per_search_limit=10 was used
        mock_client.fetch_topics_and_variables.assert_called_once_with(
            query="health", place_dcids=[], max_results=10
        )


@pytest.mark.asyncio
class TestSearchIndicators:
    """Tests for the search_indicators service function."""

    @pytest.mark.asyncio
    async def test_search_indicators_browse_mode_basic(self):
        """Test basic search in browse mode without place filtering."""
        mock_client = Mock()
        mock_client.fetch_topics_and_variables = AsyncMock(return_value={
            "topics": [{"dcid": "topic/health"}],
            "variables": [{"dcid": "Count_Person"}],
            "lookups": {"topic/health": "Health", "Count_Person": "Population"}
        })
        mock_client.fetch_entity_names = Mock(return_value={
            "topic/health": "Health", "Count_Person": "Population"
        })

        result = await search_indicators(
            client=mock_client,
            query="health",
            mode="browse"
        )

        assert result.topics is not None
        assert result.variables is not None
        assert result.lookups is not None
        assert result.status == "SUCCESS"
        mock_client.fetch_topics_and_variables.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_indicators_browse_mode_with_places(self):
        """Test search in browse mode with place filtering."""
        mock_client = Mock()
        mock_client.search_places = AsyncMock(return_value={"France": "country/FRA"})
        mock_client.fetch_topics_and_variables = AsyncMock(return_value={
            "topics": [{"dcid": "topic/trade"}],
            "variables": [{"dcid": "TradeExports_FRA"}],
            "lookups": {"topic/trade": "Trade", "TradeExports_FRA": "Exports to France"}
        })
        mock_client.fetch_entity_names = Mock(return_value={
            "topic/trade": "Trade", "TradeExports_FRA": "Exports to France", "country/FRA": "France"
        })

        result = await search_indicators(
            client=mock_client,
            query="trade exports",
            mode="browse",
            place1_name="France"
        )

        assert result.topics is not None
        assert result.variables is not None
        assert result.lookups is not None
        assert result.status == "SUCCESS"
        mock_client.search_places.assert_called_once_with(["France"])
        # Should be called twice: once for the base query and once for the base + place1_name query
        assert mock_client.fetch_topics_and_variables.call_count == 2

        # Assert the actual queries fetch_topics_and_variables was called with
        calls = mock_client.fetch_topics_and_variables.call_args_list
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
        mock_client.fetch_topics_and_variables = AsyncMock(side_effect=[
            {
                "topics": [{"dcid": "topic/trade"}],
                "variables": [{"dcid": "TradeExports_FRA"}],
                "lookups": {
                    "topic/trade": "Trade", 
                    "TradeExports_FRA": "Exports to France"
                }
            },
            {
                "topics": [{"dcid": "topic/trade"}],  # Duplicate topic
                "variables": [
                    {"dcid": "TradeImports_FRA"},  # New variable
                    {"dcid": "TradeExports_FRA"}   # Duplicate variable
                ],
                "lookups": {
                    "topic/trade": "Trade", 
                    "TradeImports_FRA": "Imports from France", 
                    "TradeExports_FRA": "Exports to France"
                }
            }
        ])
        mock_client.fetch_entity_names = Mock(return_value={
            "topic/trade": "Trade",
            "TradeExports_FRA": "Exports to France",
            "TradeImports_FRA": "Imports from France"
        })

        result = await search_indicators(
            client=mock_client,
            query="trade",
            mode="browse",
            place1_name="France"
        )

        # Should have deduplicated topics and variables
        assert len(result.topics) == 1  # Deduplicated
        assert len(result.variables) == 2  # Both unique variables included (duplicate removed)
        assert "TradeExports_FRA" in [v.dcid for v in result.variables]
        assert "TradeImports_FRA" in [v.dcid for v in result.variables]

    @pytest.mark.asyncio
    async def test_search_indicators_browse_mode_with_custom_per_search_limit(self):
        """Test search in browse mode with custom per_search_limit parameter."""
        mock_client = Mock()
        mock_client.fetch_topics_and_variables = AsyncMock(return_value={
            "topics": [{"dcid": "topic/health"}],
            "variables": [{"dcid": "Count_Person"}],
            "lookups": {"topic/health": "Health", "Count_Person": "Population"}
        })
        mock_client.fetch_entity_names = Mock(return_value={
            "topic/health": "Health", "Count_Person": "Population"
        })

        result = await search_indicators(
            client=mock_client,
            query="health",
            mode="browse",
            per_search_limit=5
        )

        assert result.topics is not None
        assert result.variables is not None
        assert result.lookups is not None
        assert result.status == "SUCCESS"
        # Verify per_search_limit was passed to client
        mock_client.fetch_topics_and_variables.assert_called_once_with(
            query="health", place_dcids=[], max_results=5
        )

    @pytest.mark.asyncio
    async def test_search_indicators_browse_mode_per_search_limit_validation(self):
        """Test per_search_limit parameter validation in browse mode."""
        mock_client = Mock()

        # Test invalid per_search_limit values
        with pytest.raises(ValueError, match="per_search_limit must be between 1 and 100"):
            await search_indicators(
                client=mock_client,
                query="health",
                mode="browse",
                per_search_limit=0
            )

        with pytest.raises(ValueError, match="per_search_limit must be between 1 and 100"):
            await search_indicators(
                client=mock_client,
                query="health",
                mode="browse",
                per_search_limit=101
            )

        # Test valid per_search_limit values
        mock_client.fetch_topics_and_variables = AsyncMock(return_value={
            "topics": [], "variables": [], "lookups": {}
        })

        # Should not raise for valid values
        await search_indicators(client=mock_client, query="health", mode="browse", per_search_limit=1)
        await search_indicators(client=mock_client, query="health", mode="browse", per_search_limit=100)

    @pytest.mark.asyncio
    async def test_search_indicators_browse_mode_default_per_search_limit(self):
        """Test that default per_search_limit=10 is used when not specified in browse mode."""
        mock_client = Mock()
        mock_client.fetch_topics_and_variables = AsyncMock(return_value={
            "topics": [], "variables": [], "lookups": {}
        })

        await search_indicators(client=mock_client, query="health", mode="browse")

        # Verify default per_search_limit=10 was used
        mock_client.fetch_topics_and_variables.assert_called_once_with(
            query="health", place_dcids=[], max_results=10
        )

    @pytest.mark.asyncio
    async def test_search_indicators_browse_mode_default_mode(self):
        """Test that browse mode is the default when mode is not specified."""
        mock_client = Mock()
        mock_client.fetch_topics_and_variables = AsyncMock(return_value={
            "topics": [{"dcid": "topic/health"}],
            "variables": [{"dcid": "Count_Person"}],
            "lookups": {"topic/health": "Health", "Count_Person": "Population"}
        })
        mock_client.fetch_entity_names = Mock(return_value={
            "topic/health": "Health", "Count_Person": "Population"
        })

        result = await search_indicators(
            client=mock_client,
            query="health"
        )

        assert result.topics is not None
        assert result.variables is not None
        assert result.lookups is not None
        assert result.status == "SUCCESS"
        mock_client.fetch_topics_and_variables.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_indicators_mode_validation(self):
        """Test mode parameter validation."""
        mock_client = Mock()

        # Test invalid mode values
        with pytest.raises(ValueError, match="mode must be either 'browse' or 'lookup'"):
            await search_indicators(
                client=mock_client,
                query="health",
                mode="invalid_mode"
            )

        # Test valid mode values
        mock_client.fetch_topics_and_variables = AsyncMock(return_value={
            "topics": [], "variables": [], "lookups": {}
        })

        # Should not raise for valid values
        await search_indicators(client=mock_client, query="health", mode="browse")
        await search_indicators(client=mock_client, query="health", mode="lookup")
        await search_indicators(client=mock_client, query="health", mode=None)  # None should default to browse

    # Phase 2: Lookup Mode Tests
    @pytest.mark.asyncio
    async def test_search_indicators_lookup_mode_basic(self):
        """Test basic search in lookup mode with a single place."""
        mock_client = Mock()
        mock_client.search_places = AsyncMock(return_value={"USA": "country/USA"})
        mock_client.fetch_topic_variables = AsyncMock(return_value={
            "topic_variable_ids": ["Count_Person", "Count_Household"]
        })
        mock_client.fetch_entity_names = Mock(return_value={
            "Count_Person": "Population", "Count_Household": "Households", "country/USA": "USA"
        })

        result = await search_indicators(
            client=mock_client,
            query="health",
            mode="lookup",
            place1_name="USA"
        )

        assert result.topics is None  # No topics in lookup mode
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
        mock_client.fetch_topic_variables = AsyncMock(return_value={
            "topic_variable_ids": ["TradeExports_FRA", "TradeImports_FRA"]
        })
        mock_client.fetch_entity_names = Mock(return_value={
            "TradeExports_FRA": "Exports to France", 
            "TradeImports_FRA": "Imports from France",
            "country/FRA": "France"
        })

        result = await search_indicators(
            client=mock_client,
            query="trade exports",
            mode="lookup",
            place1_name="France"
        )

        assert result.topics is None  # No topics in lookup mode
        assert result.variables is not None
        assert result.lookups is not None
        assert result.status == "SUCCESS"
        mock_client.search_places.assert_called_once_with(["France"])
        # Should be called for each place DCID
        assert mock_client.fetch_topic_variables.call_count == 1

        # Verify the call was made with the correct parameters
        call_args = mock_client.fetch_topic_variables.call_args
        assert call_args[0][0] == "country/FRA"  # place_dcid
        assert call_args[1]["topic_query"] == "trade exports"

    @pytest.mark.asyncio
    async def test_search_indicators_lookup_mode_merge_results(self):
        """Test that results from multiple searches are properly merged in lookup mode."""
        mock_client = Mock()
        mock_client.search_places = AsyncMock(return_value={"France": "country/FRA", "Germany": "country/DEU"})
        mock_client.fetch_topic_variables = AsyncMock(side_effect=[
            {"topic_variable_ids": ["TradeExports_FRA"]},  # France results
            {"topic_variable_ids": ["TradeExports_DEU", "TradeExports_FRA"]}  # Germany results (with duplicate)
        ])
        mock_client.fetch_entity_names = Mock(return_value={
            "TradeExports_FRA": "Exports to France",
            "TradeExports_DEU": "Exports to Germany",
            "country/FRA": "France",
            "country/DEU": "Germany"
        })

        result = await search_indicators(
            client=mock_client,
            query="trade",
            mode="lookup",
            place1_name="France",
            place2_name="Germany"
        )

        # Should have deduplicated variables
        assert result.topics is None  # No topics in lookup mode
        assert len(result.variables) == 2  # Both unique variables included (duplicate removed)
        assert any(v.dcid == "TradeExports_FRA" for v in result.variables)
        assert any(v.dcid == "TradeExports_DEU" for v in result.variables)

    @pytest.mark.asyncio
    async def test_search_indicators_lookup_mode_with_custom_per_search_limit(self):
        """Test search in lookup mode with custom per_search_limit parameter."""
        mock_client = Mock()
        mock_client.search_places = AsyncMock(return_value={"USA": "country/USA"})
        mock_client.fetch_topic_variables = AsyncMock(return_value={
            "topic_variable_ids": ["Count_Person", "Count_Household", "Count_Business"]
        })
        mock_client.fetch_entity_names = Mock(return_value={
            "Count_Person": "Population", 
            "Count_Household": "Households",
            "Count_Business": "Businesses",
            "country/USA": "USA"
        })

        result = await search_indicators(
            client=mock_client,
            query="health",
            mode="lookup",
            place1_name="USA",
            per_search_limit=2
        )

        assert result.topics is None  # No topics in lookup mode
        assert result.variables is not None
        assert result.lookups is not None
        assert result.status == "SUCCESS"
        # Should be limited to 2 results
        assert len(result.variables) == 2

    @pytest.mark.asyncio
    async def test_search_indicators_lookup_mode_per_search_limit_validation(self):
        """Test per_search_limit parameter validation in lookup mode."""
        mock_client = Mock()

        # Test invalid per_search_limit values
        with pytest.raises(ValueError, match="per_search_limit must be between 1 and 100"):
            await search_indicators(
                client=mock_client,
                query="health",
                mode="lookup",
                per_search_limit=0
            )

        with pytest.raises(ValueError, match="per_search_limit must be between 1 and 100"):
            await search_indicators(
                client=mock_client,
                query="health",
                mode="lookup",
                per_search_limit=101
            )

        # Test valid per_search_limit values with place (so lookup mode is actually used)
        mock_client.search_places = AsyncMock(return_value={"USA": "country/USA"})
        mock_client.fetch_topic_variables = AsyncMock(return_value={
            "topic_variable_ids": []
        })
        mock_client.fetch_entity_names = Mock(return_value={
            "country/USA": "USA"
        })

        # Should not raise for valid values
        await search_indicators(client=mock_client, query="health", mode="lookup", place1_name="USA", per_search_limit=1)
        await search_indicators(client=mock_client, query="health", mode="lookup", place1_name="USA", per_search_limit=100)

    @pytest.mark.asyncio
    async def test_search_indicators_lookup_mode_default_per_search_limit(self):
        """Test that default per_search_limit=10 is used when not specified in lookup mode."""
        mock_client = Mock()
        mock_client.search_places = AsyncMock(return_value={"USA": "country/USA"})
        mock_client.fetch_topic_variables = AsyncMock(return_value={
            "topic_variable_ids": []
        })
        mock_client.fetch_entity_names = Mock(return_value={
            "country/USA": "USA"
        })

        await search_indicators(client=mock_client, query="health", mode="lookup", place1_name="USA")

        # Verify default per_search_limit=10 was used (though not directly passed to fetch_topic_variables)
        # The limit is applied after fetching results
        mock_client.fetch_topic_variables.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_indicators_automatic_fallback_to_browse_mode(self):
        """Test that lookup mode automatically falls back to browse mode when no places are provided."""
        mock_client = Mock()
        mock_client.fetch_topics_and_variables = AsyncMock(return_value={
            "topics": [{"dcid": "topic/health"}],
            "variables": [{"dcid": "Count_Person"}],
            "lookups": {"topic/health": "Health", "Count_Person": "Population"}
        })
        mock_client.fetch_entity_names = Mock(return_value={
            "topic/health": "Health", "Count_Person": "Population"
        })

        # Call with lookup mode but no places - should automatically fall back to browse mode
        result = await search_indicators(
            client=mock_client,
            query="health",
            mode="lookup"  # No places provided
        )

        # Should return browse mode results (topics populated)
        assert result.topics is not None
        assert result.variables is not None
        assert result.lookups is not None
        assert result.status == "SUCCESS"
        # Should have called fetch_topics_and_variables (browse mode) instead of fetch_topic_variables (lookup mode)
        mock_client.fetch_topics_and_variables.assert_called_once()
        mock_client.fetch_topic_variables.assert_not_called()
