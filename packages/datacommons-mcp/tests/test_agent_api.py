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
Tests for AgentAPIClient, services, tools, and skills registration.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from datacommons_mcp.client import AgentAPIClient, use_api_key
from datacommons_mcp.exceptions import AgentAPIError
from datacommons_mcp.services import (
    get_multi_entity_observations as services_get_multi_entity_obs,
)
from datacommons_mcp.services import (
    get_observations as services_get_obs,
)
from datacommons_mcp.services import (
    get_variable_metadata as services_get_var_meta,
)
from datacommons_mcp.services import (
    search_indicators as services_search_ind,
)
from datacommons_mcp.tools import (
    get_child_observations as tools_get_child_obs,
)
from datacommons_mcp.tools import (
    get_multi_entity_observations as tools_get_multi_entity_obs,
)
from datacommons_mcp.tools import (
    get_observations as tools_get_obs,
)
from datacommons_mcp.tools import (
    get_variable_metadata as tools_get_var_meta,
)
from datacommons_mcp.tools import (
    search_child_indicators as tools_search_child_ind,
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
            headers=None,
        )

    await client.close()


@pytest.mark.asyncio
async def test_agent_api_client_post_with_api_key_override():
    """Verify AgentAPIClient respects use_api_key context override."""
    client = AgentAPIClient(
        api_root="https://api.datacommons.org/v2", api_key="default-key"
    )

    mock_response = MagicMock()
    mock_response.json.return_value = {"status": "SUCCESS"}
    mock_response.raise_for_status = lambda: None

    with (
        patch.object(client.client, "post", return_value=mock_response) as mock_post,
        use_api_key("override-key-123"),
    ):
        result = await client.post("agent/test_endpoint", {"param": "value"})

        assert result == {"status": "SUCCESS"}
        mock_post.assert_called_once_with(
            "https://api.datacommons.org/v2/agent/test_endpoint",
            json={"param": "value"},
            headers={"X-API-Key": "override-key-123"},
        )

    await client.close()


@pytest.mark.asyncio
async def test_agent_api_client_search_scope():
    """Verify AgentAPIClient stores search_scope attribute."""
    client = AgentAPIClient(
        api_root="https://api.datacommons.org/v2",
        api_key="test-key",
        search_scope="custom_only",
    )
    assert client.search_scope == "custom_only"
    await client.close()


@pytest.mark.asyncio
async def test_agent_api_client_post_error():
    """Verify that AgentAPIClient.post raises AgentAPIError and extracts details on failure."""
    client = AgentAPIClient(api_root="https://api.datacommons.org/v2")
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = '{"message": "Internal error"}'
    mock_response.json.return_value = {"message": "Internal error"}

    def raise_status_error():
        raise httpx.HTTPStatusError(
            "Internal Server Error", request=MagicMock(), response=mock_response
        )

    mock_response.raise_for_status = raise_status_error

    with patch.object(client.client, "post", return_value=mock_response):
        with pytest.raises(AgentAPIError) as exc_info:
            await client.post("agent/test", {})
        assert exc_info.value.status_code == 500
        err_msg = str(exc_info.value)
        assert "agent/test" in err_msg
        assert "500" in err_msg
        assert exc_info.value.body == '{"message": "Internal error"}'

    await client.close()


@pytest.mark.asyncio
async def test_services_get_observations():
    """Verify get_observations builds correct payload and invokes client."""
    from datacommons_mcp.app import app

    mock_client = AsyncMock()
    mock_client.post.return_value = {"placeObservations": []}

    with patch.object(app, "client", mock_client):
        result = await services_get_obs(
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
                "entities": {
                    "observationAbout": {
                        "parent_dcid": "geoId/06",
                        "child_type": "County",
                    }
                },
                "source_override": "USCensus",
                "date": "latest",
                "date_range_start": "2020",
                "date_range_end": "2022",
            },
        )

        # Verify default date is "latest" when omitted
        mock_client.reset_mock()
        await services_get_obs(
            variable_dcid="Count_Person",
            place_dcid="geoId/06",
        )
        mock_client.post.assert_called_once_with(
            "agent/get_observations",
            {
                "variable_dcid": "Count_Person",
                "entities": {"observationAbout": ["geoId/06"]},
                "source_override": None,
                "date": "latest",
                "date_range_start": None,
                "date_range_end": None,
            },
        )


@pytest.mark.asyncio
async def test_services_get_multi_entity_observations():
    """Verify get_multi_entity_observations builds correct payload for direct and child expansion."""
    from datacommons_mcp.app import app

    mock_client = AsyncMock()
    mock_client.post.return_value = {"placeObservations": []}

    with patch.object(app, "client", mock_client):
        # Direct DCID map
        await services_get_multi_entity_obs(
            variable_dcid="Amount_EconomicActivity_GrossODA",
            entities={"donor": ["country/ARE"], "recipient": ["country/AFG"]},
        )
        mock_client.post.assert_called_with(
            "agent/get_observations",
            {
                "variable_dcid": "Amount_EconomicActivity_GrossODA",
                "entities": {"donor": ["country/ARE"], "recipient": ["country/AFG"]},
                "source_override": None,
                "date": "latest",
                "date_range_start": None,
                "date_range_end": None,
            },
        )

        # Child entity expansion
        await services_get_multi_entity_obs(
            variable_dcid="Amount_EconomicActivity_GrossODA",
            entities={"donor": ["country/ARE"]},
            parent_entity_property="recipient",
            parent_entity_dcid="Earth",
            child_entity_type="Country",
        )
        mock_client.post.assert_called_with(
            "agent/get_observations",
            {
                "variable_dcid": "Amount_EconomicActivity_GrossODA",
                "entities": {
                    "donor": ["country/ARE"],
                    "recipient": {"parent_dcid": "Earth", "child_type": "Country"},
                },
                "source_override": None,
                "date": "latest",
                "date_range_start": None,
                "date_range_end": None,
            },
        )

        # Partial child expansion parameters should raise ValueError
        with pytest.raises(ValueError, match="To use child entity expansion"):
            await services_get_multi_entity_obs(
                variable_dcid="Amount_EconomicActivity_GrossODA",
                entities={"donor": ["country/ARE"]},
                parent_entity_property="recipient",
            )

        # Conflicting parent_entity_property in entities should raise ValueError
        with pytest.raises(
            ValueError,
            match="cannot be specified in both 'entities' and child expansion",
        ):
            await services_get_multi_entity_obs(
                variable_dcid="Amount_EconomicActivity_GrossODA",
                entities={"donor": ["country/ARE"], "recipient": ["country/AFG"]},
                parent_entity_property="recipient",
                parent_entity_dcid="Earth",
                child_entity_type="Country",
            )


@pytest.mark.asyncio
async def test_services_search_indicators():
    """Verify search_indicators builds correct payload and invokes client."""
    from datacommons_mcp.app import app

    mock_client = AsyncMock()
    mock_client.search_scope = "custom_only"
    mock_client.post.return_value = {"variables": []}

    with patch.object(app, "client", mock_client):
        result = await services_search_ind(
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
                "target": "custom_only",
            },
        )


@pytest.mark.asyncio
async def test_services_get_variable_metadata():
    """Verify get_variable_metadata builds correct payload and invokes client."""
    from datacommons_mcp.app import app

    mock_client = AsyncMock()
    mock_client.post.return_value = {"metadata": {}, "provenance": {}}

    with patch.object(app, "client", mock_client):
        result = await services_get_var_meta(
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


@pytest.mark.asyncio
async def test_tools_delegation():
    """Verify tool functions delegate to services correctly."""
    with patch(
        "datacommons_mcp.tools.services_search_indicators",
        new_callable=AsyncMock,
    ) as mock_search:
        mock_search.return_value = {"search": True}
        assert await tools_search_ind(query="pop", places=["geoId/06"]) == {
            "search": True
        }
        mock_search.assert_called_once_with(
            query="pop",
            places=["geoId/06"],
            parent_place=None,
            per_search_limit=10,
            include_topics=True,
        )

    with patch(
        "datacommons_mcp.tools.services_search_indicators",
        new_callable=AsyncMock,
    ) as mock_child_search:
        mock_child_search.return_value = {"child_search": True}
        assert await tools_search_child_ind(
            query="pop", parent_place="geoId/06", sample_child_places=["geoId/06001"]
        ) == {"child_search": True}
        mock_child_search.assert_called_once_with(
            query="pop",
            places=["geoId/06001"],
            parent_place="geoId/06",
            per_search_limit=10,
            include_topics=True,
        )

    with patch(
        "datacommons_mcp.tools.services_get_variable_metadata",
        new_callable=AsyncMock,
    ) as mock_meta:
        mock_meta.return_value = {"meta": True}
        assert await tools_get_var_meta(
            variable_dcids=["Count_Person"], entity_dcids=["geoId/06"]
        ) == {"meta": True}
        mock_meta.assert_called_once_with(
            variable_dcids=["Count_Person"], entity_dcids=["geoId/06"]
        )

    with patch(
        "datacommons_mcp.tools.services_get_observations",
        new_callable=AsyncMock,
    ) as mock_obs:
        mock_obs.return_value = {"obs": True}
        assert await tools_get_obs(
            variable_dcid="Count_Person", place_dcid="geoId/06"
        ) == {"obs": True}
        mock_obs.assert_called_once_with(
            variable_dcid="Count_Person",
            place_dcid="geoId/06",
            child_place_type=None,
            source_override=None,
            date="latest",
            date_range_start=None,
            date_range_end=None,
        )

    with patch(
        "datacommons_mcp.tools.services_get_observations",
        new_callable=AsyncMock,
    ) as mock_child_obs:
        mock_child_obs.return_value = {"child_obs": True}
        assert await tools_get_child_obs(
            variable_dcid="Count_Person",
            parent_place_dcid="geoId/06",
            child_place_type="County",
        ) == {"child_obs": True}
        mock_child_obs.assert_called_once_with(
            variable_dcid="Count_Person",
            place_dcid="geoId/06",
            child_place_type="County",
            source_override=None,
            date="latest",
            date_range_start=None,
            date_range_end=None,
        )

    with patch(
        "datacommons_mcp.tools.services_get_multi_entity_observations",
        new_callable=AsyncMock,
    ) as mock_multi_obs:
        mock_multi_obs.return_value = {"multi_obs": True}
        assert await tools_get_multi_entity_obs(
            variable_dcid="Var1", entities={"prop": ["val"]}
        ) == {"multi_obs": True}
        mock_multi_obs.assert_called_once_with(
            variable_dcid="Var1",
            entities={"prop": ["val"]},
            parent_entity_property=None,
            parent_entity_dcid=None,
            child_entity_type=None,
            source_override=None,
            date="latest",
            date_range_start=None,
            date_range_end=None,
        )


def test_skills_provider_registration():
    """Verify that SkillsDirectoryProvider is correctly registered when skills exist."""
    from datacommons_mcp.server import _register_skills
    from fastmcp.server.providers.skills import SkillsDirectoryProvider

    mock_mcp = MagicMock()
    mock_app = MagicMock()
    mock_app.settings.instructions_dir = None

    _register_skills(mock_mcp, mock_app)

    mock_mcp.add_provider.assert_called_once()
    provider = mock_mcp.add_provider.call_args[0][0]
    assert isinstance(provider, SkillsDirectoryProvider)
    assert len(provider._roots) == 1
    assert "instructions" in str(provider._roots[0])
    assert "skills" in str(provider._roots[0])
