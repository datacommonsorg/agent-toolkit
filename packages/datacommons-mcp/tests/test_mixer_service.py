# Copyright 2026 Google LLC.
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
"""
Tests for MixerClient, mixer_service, and feature flag routing.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from datacommons_mcp.app import app
from datacommons_mcp.mixer_client import MixerClient
from datacommons_mcp.mixer_service import get_observations, search_indicators
from datacommons_mcp.tools import (
    get_observations as tools_get_obs,
)
from datacommons_mcp.tools import (
    search_indicators as tools_search_ind,
)


@pytest.mark.asyncio
async def test_mixer_client_post():
    """Verify MixerClient correctly sends payload and headers to the endpoint."""
    client = MixerClient(api_root="https://api.datacommons.org/v2", api_key="test-api-key")
    assert client.headers["X-API-Key"] == "test-api-key"

    mock_response = MagicMock()
    mock_response.json.return_value = {"status": "SUCCESS", "data": "test"}
    mock_response.raise_for_status = lambda: None

    with patch.object(client.client, "post", return_value=mock_response) as mock_post:
        result = await client.post("agent/test_endpoint", {"param": "value"})

        assert result == {"status": "SUCCESS", "data": "test"}
        mock_post.assert_called_once_with(
            "https://api.datacommons.org/v2/agent/test_endpoint",
            json={"param": "value"}
        )

    await client.close()


@pytest.mark.asyncio
async def test_mixer_service_get_observations():
    """Verify get_observations builds correct payload and invokes mixer_client."""
    mock_client = AsyncMock()
    mock_client.post.return_value = {"placeObservations": []}

    with patch.object(app, "mixer_client", mock_client):
        result = await get_observations(
            variable_dcid="Count_Person",
            place_dcid="geoId/06",
            child_place_type="County",
            source_override="USCensus",
            date="latest",
            date_range_start="2020",
            date_range_end="2022"
        )
        assert result == {"placeObservations": []}
        mock_client.post.assert_called_once_with(
            "agent/get_observations",
            {
                "variable_dcid": "Count_Person",
                "place_dcid": "geoId/06",
                "child_place_type": "County",
                "source_override": "USCensus",
                "date": "latest",
                "date_range_start": "2020",
                "date_range_end": "2022",
            }
        )


@pytest.mark.asyncio
async def test_mixer_service_search_indicators():
    """Verify search_indicators builds correct payload and invokes mixer_client."""
    mock_client = AsyncMock()
    mock_client.post.return_value = {"variables": []}

    with patch.object(app, "mixer_client", mock_client):
        result = await search_indicators(
            query="unemployment",
            places=["California"],
            parent_place="USA",
            per_search_limit=5,
            include_topics=False
        )
        assert result == {"variables": []}
        mock_client.post.assert_called_once_with(
            "agent/search_indicators",
            {
                "query": "unemployment",
                "places": ["California"],
                "parent_place": "USA",
                "per_search_limit": 5,
                "include_topics": False,
            }
        )


@pytest.mark.asyncio
async def test_tools_routing_mixer_enabled():
    """Verify tool functions delegate to mixer_service when feature flag is enabled."""
    with patch.object(app.settings, "use_mixer_agent_apis", True):
        with patch("datacommons_mcp.tools.mixer_get_observations", new_callable=AsyncMock) as mock_mixer_get_obs:
            mock_mixer_get_obs.return_value = {"mixer_obs": True}
            result = await tools_get_obs(
                variable_dcid="Count_Person",
                place_dcid="geoId/06"
            )
            assert result == {"mixer_obs": True}
            mock_mixer_get_obs.assert_called_once()

        with patch("datacommons_mcp.tools.mixer_search_indicators", new_callable=AsyncMock) as mock_mixer_search_ind:
            mock_mixer_search_ind.return_value = {"mixer_search": True}
            result = await tools_search_ind(
                query="unemployment",
                places=["California"]
            )
            assert result == {"mixer_search": True}
            mock_mixer_search_ind.assert_called_once()


@pytest.mark.asyncio
async def test_tools_routing_mixer_disabled():
    """Verify tool functions delegate to old local services when feature flag is disabled."""
    with patch.object(app.settings, "use_mixer_agent_apis", False):
        with patch("datacommons_mcp.tools.get_observations_service", new_callable=AsyncMock) as mock_local_get_obs:
            mock_response = MagicMock()
            mock_response.model_dump.return_value = {"local_obs": True}
            mock_local_get_obs.return_value = mock_response

            result = await tools_get_obs(
                variable_dcid="Count_Person",
                place_dcid="geoId/06"
            )
            assert result == {"local_obs": True}
            mock_local_get_obs.assert_called_once()

        with patch("datacommons_mcp.tools.search_indicators_service", new_callable=AsyncMock) as mock_local_search_ind:
            mock_response = MagicMock()
            mock_response.model_dump.return_value = {"local_search": True}
            mock_local_search_ind.return_value = mock_response

            result = await tools_search_ind(
                query="unemployment",
                places=["California"]
            )
            assert result == {"local_search": True}
            mock_local_search_ind.assert_called_once()
