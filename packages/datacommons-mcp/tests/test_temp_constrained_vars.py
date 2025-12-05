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
# TODO(https://github.com/datacommonsorg/agent-toolkit/issues/47): Remove once the new endpoint is live.
import os
from unittest.mock import Mock, patch

import pytest
from datacommons_client.client import DataCommonsClient
from datacommons_mcp._constrained_vars import _merge_dicts
from datacommons_mcp.clients import DCClient, create_dc_client
from datacommons_mcp.data_models.settings import CustomDCSettings
from datacommons_mcp.settings import get_dc_settings


@pytest.fixture
def mocked_datacommons_client():
    """
    NOTE: This is a temporary copy of the code in `test_dc_client`. It will be removed
    once these tests are no longer necessary.

    Provides a mocked instance of the underlying `DataCommonsClient`.

    This fixture patches the `DataCommonsClient` constructor within the
    `datacommons_mcp.clients` module. Any instance of `DCClient` created
    in a test using this fixture will have its `self.dc` attribute set to
    this mock instance.
    """
    with patch("datacommons_mcp.clients.DataCommonsClient") as mock_constructor:
        mock_instance = Mock(spec=DataCommonsClient)
        # Manually add the client endpoints which aren't picked up by spec
        mock_instance.observation = Mock()

        mock_constructor.return_value = mock_instance
        yield mock_instance


def test_merge_dicts_unions_values():
    d1 = {"p1": ["v1", "v2"], "p2": ["v3"]}
    d2 = {"p1": ["v2", "v4"], "p3": ["v5"]}

    merged = _merge_dicts([d1, d2])

    # Expect sets with unioned values
    assert merged["p1"] == {"v1", "v2", "v4"}
    assert merged["p2"] == {"v3"}
    assert merged["p3"] == {"v5"}


def test_filter_variables_includes_place_like_store(mocked_datacommons_client):
    """_filter_variables_by_existence should consider _place_like_statvar_store union."""
    client_under_test = DCClient(dc=mocked_datacommons_client)
    # Variable cache has no variables for the place
    client_under_test.variable_cache = Mock()
    client_under_test.variable_cache.get.side_effect = lambda _: set()
    # Place-like store provides the variable for the place
    client_under_test._place_like_statvar_store = {
        "geoId/06": {"dc/variable/Count_Person"}
    }

    result = client_under_test._filter_variables_by_existence(
        ["dc/variable/Count_Person"], ["geoId/06"]
    )

    assert result == [
        {"dcid": "dc/variable/Count_Person", "places_with_data": ["geoId/06"]}
    ]


def test_get_topic_places_with_data_includes_place_like_store(
    mocked_datacommons_client,
):
    """_get_topic_places_with_data should consider _place_like_statvar_store union."""
    client_under_test = DCClient(dc=mocked_datacommons_client)
    # Minimal topic store containing a topic with one variable
    topic_dcid = "dc/topic/Health"
    var_dcid = "dc/variable/Count_Person"
    topic_obj = Mock(member_topics=[], member_variables=[var_dcid])
    client_under_test.topic_store = Mock(topics_by_dcid={topic_dcid: topic_obj})

    # Variable cache does not list the variable for the place
    client_under_test.variable_cache = Mock()
    client_under_test.variable_cache.get.side_effect = lambda _: set()

    # Place-like store provides the variable for the place
    client_under_test._place_like_statvar_store = {"geoId/06": {var_dcid}}

    places = client_under_test._get_topic_places_with_data(
        topic_dcid, ["geoId/06", "geoId/36"]
    )

    assert places == ["geoId/06"]


@patch("datacommons_mcp.clients.DCClient._compute_place_like_statvar_store")
@patch("datacommons_mcp.clients.DataCommonsClient")
def test_create_custom_client_passes_place_like_constraints(
    mock_dc_client,  # noqa: ARG001 -- Required for test to pass
    mock_compute_store,
):
    """Ensure PLACE_LIKE_CONSTRAINTS are forwarded to DCClient constructor logic."""
    with patch.dict(
        os.environ,
        {
            "DC_API_KEY": "k",
            "DC_TYPE": "custom",
            "CUSTOM_DC_URL": "https://example.com",
            "PLACE_LIKE_CONSTRAINTS": "prop/a,prop/b",
        },
    ):
        settings = CustomDCSettings()
        _ = create_dc_client(settings)

        mock_compute_store.assert_called_once()


def test_loads_with_minimal_config(isolated_env):
    """Tests that CustomDCSettings loads with minimal config and correct defaults."""
    env_vars = {
        "DC_API_KEY": "test_key",
        "DC_TYPE": "custom",
        "CUSTOM_DC_URL": "https://test.com",
    }
    with isolated_env(env_vars):
        settings = get_dc_settings()

        assert settings.place_like_constraints is None


def test_place_like_constraints_parsing_empty_and_whitespace(isolated_env):
    """PLACE_LIKE_CONSTRAINTS empty string becomes None; whitespace trimmed and empties dropped."""
    env_vars = {
        "DC_API_KEY": "test_key",
        "DC_TYPE": "custom",
        "CUSTOM_DC_URL": "https://test.com",
        "PLACE_LIKE_CONSTRAINTS": "  ,  ",
    }
    with isolated_env(env_vars):
        settings = get_dc_settings()
        assert not settings.place_like_constraints

    env_vars = {
        "DC_API_KEY": "test_key",
        "DC_TYPE": "custom",
        "CUSTOM_DC_URL": "https://test.com",
        "PLACE_LIKE_CONSTRAINTS": " prop/a , ,prop/b ",
    }
    with isolated_env(env_vars):
        settings = get_dc_settings()
        assert settings.place_like_constraints == ["prop/a", "prop/b"]


def test_loads_with_env_var_overrides(isolated_env):
    """Tests that environment variables override defaults for CustomDCSettings."""
    env_vars = {
        "DC_API_KEY": "test_key",
        "DC_TYPE": "custom",
        "CUSTOM_DC_URL": "https://test.com",
        "DC_SEARCH_SCOPE": "custom_only",
        "DC_BASE_INDEX": "custom_base",
        "DC_CUSTOM_INDEX": "custom_custom",
        "DC_ROOT_TOPIC_DCIDS": "topic1, topic2",
        "PLACE_LIKE_CONSTRAINTS": "prop/containedInPlace, prop/overlapsWith",
    }
    with isolated_env(env_vars):
        settings = get_dc_settings()
        assert settings.place_like_constraints == [
            "prop/containedInPlace",
            "prop/overlapsWith",
        ]
