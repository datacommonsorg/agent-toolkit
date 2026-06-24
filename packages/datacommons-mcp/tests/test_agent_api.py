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
Tests for AgentAPIClient, agent_api_service, and routing.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from datacommons_mcp.agent_api_client import AgentAPIClient
from datacommons_mcp.agent_api_service import (
    get_observations,
    get_variable_metadata,
    search_indicators,
)
from datacommons_mcp.agent_api_tools import (
    get_observations as agent_api_tools_get_obs,
)
from datacommons_mcp.agent_api_tools import (
    search_indicators as agent_api_tools_search_ind,
)
from datacommons_mcp.tools import (
    get_observations as tools_get_obs,
)
from datacommons_mcp.tools import (
    search_indicators as tools_search_ind,
)


@pytest.mark.asyncio
async def test_agent_api_client_post():
    """Verify AgentAPIClient correctly sends payload and headers to the endpoint."""
    client = AgentAPIClient(
        api_root="https://api.datacommons.org/v2", api_key="test-api-key"
    )
    assert client.headers["X-API-Key"] == "test-api-key"

    mock_response = MagicMock()
    mock_response.json.return_value = {"status": "SUCCESS", "data": "test"}
    mock_response.raise_for_status = lambda: None

    with patch.object(client.client, "post", return_value=mock_response) as mock_post:
        result = await client.post("agent/test_endpoint", {"param": "value"})

        assert result == {"status": "SUCCESS", "data": "test"}
        mock_post.assert_called_once_with(
            "https://api.datacommons.org/v2/agent/test_endpoint",
            json={"param": "value"},
        )

    await client.close()


@pytest.mark.asyncio
async def test_agent_api_service_get_observations():
    """Verify get_observations builds correct payload and invokes agent_api_client."""
    from datacommons_mcp.app import app

    mock_client = AsyncMock()
    mock_client.post.return_value = {"placeObservations": []}

    with patch.object(app, "agent_api_client", mock_client):
        result = await get_observations(
            variable_dcid="Count_Person",
            place_dcid="geoId/06",
            child_place_type="County",
            source_override="USCensus",
            date="latest",
            date_range_start="2020",
            date_range_end="2022",
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
            },
        )


@pytest.mark.asyncio
async def test_agent_api_service_search_indicators():
    """Verify search_indicators builds correct payload and invokes agent_api_client."""
    from datacommons_mcp.app import app

    mock_client = AsyncMock()
    mock_client.post.return_value = {"variables": []}

    with patch.object(app, "agent_api_client", mock_client):
        result = await search_indicators(
            query="unemployment",
            places=["California"],
            parent_place="USA",
            per_search_limit=5,
            include_topics=False,
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
            },
        )


@pytest.mark.asyncio
async def test_agent_api_tools_execution():
    """Verify agent_api_tools functions delegate to agent_api_service."""
    with patch(
        "datacommons_mcp.agent_api_tools.agent_api_get_observations",
        new_callable=AsyncMock,
    ) as mock_agent_api_get_obs:
        mock_agent_api_get_obs.return_value = {"agent_api_obs": True}
        result = await agent_api_tools_get_obs(
            variable_dcid="Count_Person", place_dcid="geoId/06"
        )
        assert result == {"agent_api_obs": True}
        mock_agent_api_get_obs.assert_called_once()

    with patch(
        "datacommons_mcp.agent_api_tools.agent_api_search_indicators",
        new_callable=AsyncMock,
    ) as mock_agent_api_search_ind:
        mock_agent_api_search_ind.return_value = {"agent_api_search": True}
        result = await agent_api_tools_search_ind(
            query="unemployment", places=["California"]
        )
        assert result == {"agent_api_search": True}
        mock_agent_api_search_ind.assert_called_once()


@pytest.mark.asyncio
async def test_local_tools_execution():
    """Verify tool functions delegate to old local services."""
    with patch(
        "datacommons_mcp.tools.get_observations_service", new_callable=AsyncMock
    ) as mock_local_get_obs:
        mock_response = MagicMock()
        mock_response.model_dump.return_value = {"local_obs": True}
        mock_local_get_obs.return_value = mock_response

        result = await tools_get_obs(
            variable_dcid="Count_Person", place_dcid="geoId/06"
        )
        assert result == {"local_obs": True}
        mock_local_get_obs.assert_called_once()

    with patch(
        "datacommons_mcp.tools.search_indicators_service", new_callable=AsyncMock
    ) as mock_local_search_ind:
        mock_response = MagicMock()
        mock_response.model_dump.return_value = {"local_search": True}
        mock_local_search_ind.return_value = mock_response

        result = await tools_search_ind(query="unemployment", places=["California"])
        assert result == {"local_search": True}
        mock_local_search_ind.assert_called_once()


@pytest.mark.asyncio
async def test_agent_api_client_post_error():
    """Verify that AgentAPIClient.post raises AgentAPIError and extracts details on failure."""
    client = AgentAPIClient(api_root="https://api.datacommons.org/v2")
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = '{"message": "Internal error"}'
    mock_response.json.return_value = {"message": "Internal error"}

    # Helper function to raise the error
    def raise_status_error():
        raise httpx.HTTPStatusError(
            "Internal Server Error", request=MagicMock(), response=mock_response
        )

    mock_response.raise_for_status = raise_status_error

    with patch.object(client.client, "post", return_value=mock_response):
        from datacommons_mcp.exceptions import AgentAPIError

        with pytest.raises(AgentAPIError) as exc_info:
            await client.post("agent/test", {})
        assert exc_info.value.status_code == 500
        err_msg = str(exc_info.value)
        assert "agent/test" in err_msg
        assert "500" in err_msg
        assert exc_info.value.body == '{"message": "Internal error"}'

    await client.close()


@pytest.mark.asyncio
async def test_agent_api_service_get_variable_metadata():
    """Verify get_variable_metadata builds correct payload and invokes client."""
    from datacommons_mcp.app import app

    mock_client = AsyncMock()
    mock_client.post.return_value = {"metadata": {}, "provenance": {}}

    with patch.object(app, "agent_api_client", mock_client):
        result = await get_variable_metadata(
            variable_dcids=["Count_Person"],
            entity_dcids=["geoId/06"],
        )
        assert result == {"metadata": {}, "provenance": {}}
        mock_client.post.assert_called_once_with(
            "agent/get_variable_metadata",
            {
                "variable_dcids": ["Count_Person"],
                "entity_dcids": ["geoId/06"],
            },
        )


def test_skills_provider_registration():
    """Verify that SkillsDirectoryProvider is correctly registered when skills exist."""
    from datacommons_mcp.server import _register_skills
    from fastmcp.server.providers.skills import SkillsDirectoryProvider

    mock_mcp = MagicMock()
    mock_app = MagicMock()
    mock_app.mode_dir = "agent_api"
    mock_app.settings.instructions_dir = None  # Force package default fallback

    _register_skills(mock_mcp, mock_app)

    # Verify that add_provider was called
    mock_mcp.add_provider.assert_called_once()
    provider = mock_mcp.add_provider.call_args[0][0]
    assert isinstance(provider, SkillsDirectoryProvider)

    # Verify that the provider root points to agent_api/skills
    assert len(provider._roots) == 1
    assert "agent_api" in str(provider._roots[0])
    assert "skills" in str(provider._roots[0])
