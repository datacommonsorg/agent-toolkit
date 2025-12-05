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
"""
Tests for settings module.
"""

import os
from unittest.mock import patch

import pytest
from datacommons_mcp.data_models.enums import SearchScope
from datacommons_mcp.data_models.settings import BaseDCSettings, CustomDCSettings
from datacommons_mcp.settings import get_dc_settings


class TestBaseSettings:
    """Test suite for loading BaseDCSettings."""

    def test_loads_with_minimal_config(self):
        """Tests that BaseDCSettings loads with minimal config and correct defaults."""
        env_vars = {"DC_API_KEY": "test_key", "DC_TYPE": "base"}
        with patch.dict(os.environ, env_vars):
            settings = get_dc_settings()

            assert isinstance(settings, BaseDCSettings)
            assert settings.api_key == "test_key"
            assert settings.search_root == "https://datacommons.org"
            assert settings.base_index == "base_uae_mem"
            assert settings.topic_cache_paths is None

    def test_loads_with_env_var_overrides(self):
        """Tests that environment variables override defaults for BaseDCSettings."""
        env_vars = {
            "DC_API_KEY": "test_key",
            "DC_TYPE": "base",
            "DC_SEARCH_ROOT": "https://custom.com",
            "DC_BASE_INDEX": "custom_index",
            "DC_TOPIC_CACHE_PATHS": "/path/to/cache1.json, /path/to/cache2.json",
        }
        with patch.dict(os.environ, env_vars):
            settings = get_dc_settings()

            assert isinstance(settings, BaseDCSettings)
            assert settings.search_root == "https://custom.com"
            assert settings.base_index == "custom_index"
            assert settings.topic_cache_paths == [
                "/path/to/cache1.json",
                "/path/to/cache2.json",
            ]

    @pytest.mark.parametrize(
        ("env_value", "expected"),
        [("true", True), ("false", False), ("1", True), ("0", False)],
    )
    def test_use_search_indicators_endpoint_parsing(self, env_value, expected):
        """Tests that DC_USE_SEARCH_INDICATORS_ENDPOINT is parsed correctly."""
        env_vars = {
            "DC_API_KEY": "test_key",
            "DC_TYPE": "base",
            "DC_USE_SEARCH_INDICATORS_ENDPOINT": env_value,
        }
        with patch.dict(os.environ, env_vars):
            settings = get_dc_settings()
            assert settings.use_search_indicators_endpoint is expected

    def test_default_dc_type_is_base(self):
        """Tests that DC_TYPE defaults to 'base' when not provided."""
        env_vars = {"DC_API_KEY": "test_key"}
        with patch.dict(os.environ, env_vars):
            settings = get_dc_settings()
            assert isinstance(settings, BaseDCSettings)
            assert settings.dc_type == "base"


class TestCustomSettings:
    """Test suite for loading CustomDCSettings."""

    def test_loads_with_minimal_config(self):
        """Tests that CustomDCSettings loads with minimal config and correct defaults."""
        env_vars = {
            "DC_API_KEY": "test_key",
            "DC_TYPE": "custom",
            "CUSTOM_DC_URL": "https://test.com",
        }
        with patch.dict(os.environ, env_vars):
            settings = get_dc_settings()

            assert isinstance(settings, CustomDCSettings)
            assert settings.api_key == "test_key"
            assert settings.custom_dc_url == "https://test.com"
            assert settings.api_base_url == "https://test.com/core/api/v2/"
            assert settings.search_scope == SearchScope.BASE_AND_CUSTOM
            assert settings.base_index == "medium_ft"
            assert settings.custom_index == "user_all_minilm_mem"
            assert settings.root_topic_dcids is None
            assert settings.use_search_indicators_endpoint is True  # Default value

    def test_loads_with_env_var_overrides(self):
        """Tests that environment variables override defaults for CustomDCSettings."""
        env_vars = {
            "DC_API_KEY": "test_key",
            "DC_TYPE": "custom",
            "CUSTOM_DC_URL": "https://test.com",
            "DC_SEARCH_SCOPE": "custom_only",
            "DC_BASE_INDEX": "custom_base",
            "DC_CUSTOM_INDEX": "custom_custom",
            "DC_ROOT_TOPIC_DCIDS": "topic1, topic2",
            "DC_USE_SEARCH_INDICATORS_ENDPOINT": "false",
        }
        with patch.dict(os.environ, env_vars):
            settings = get_dc_settings()

            assert isinstance(settings, CustomDCSettings)
            assert settings.search_scope == SearchScope.CUSTOM_ONLY
            assert settings.base_index == "custom_base"
            assert settings.custom_index == "custom_custom"
            assert settings.root_topic_dcids == ["topic1", "topic2"]
            assert settings.use_search_indicators_endpoint is False

    def test_missing_custom_url_raises_error(self):
        """Tests that a ValueError is raised for custom type without CUSTOM_DC_URL."""
        env_vars = {"DC_API_KEY": "test_key", "DC_TYPE": "custom"}
        with (
            patch.dict(os.environ, env_vars),
            pytest.raises(ValueError, match="CUSTOM_DC_URL"),
        ):
            get_dc_settings()


class TestSettingsValidation:
    """Test suite for generic settings validation."""

    def test_invalid_dc_type_raises_error(self):
        """Tests that a ValueError is raised for an invalid DC_TYPE."""
        env_vars = {"DC_API_KEY": "test_key", "DC_TYPE": "invalid"}
        with (
            patch.dict(os.environ, env_vars),
            pytest.raises(ValueError, match="Input should be 'base' or 'custom'"),
        ):
            get_dc_settings()
