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


class TestGetDCSettings:
    """Test get_dc_settings function."""

    def test_get_dc_settings_base(self):
        """Test base DC settings returns BaseDCSettings."""
        with patch.dict(os.environ, {"DC_API_KEY": "test_key", "DC_TYPE": "base"}):
            settings = get_dc_settings()

            assert isinstance(settings, BaseDCSettings)
            assert settings.dc_type == "base"
            assert settings.api_key == "test_key"
            assert settings.sv_search_base_url == "https://datacommons.org"
            assert settings.base_index == "base_uae_mem"
            assert settings.topic_cache_path is None

    def test_get_dc_settings_custom(self):
        """Test custom DC settings returns CustomDCSettings."""
        with patch.dict(
            os.environ,
            {
                "DC_API_KEY": "test_key",
                "DC_TYPE": "custom",
                "CUSTOM_DC_URL": "https://test.com",
            },
        ):
            settings = get_dc_settings()

            assert isinstance(settings, CustomDCSettings)
            assert settings.dc_type == "custom"
            assert settings.api_key == "test_key"
            assert settings.custom_dc_url == "https://test.com"
            assert settings.api_base_url == "https://test.com/core/api/v2/"
            assert settings.search_scope == SearchScope.BASE_AND_CUSTOM
            assert settings.base_index == "medium_ft"
            assert settings.custom_index == "user_all_minilm_mem"
            assert settings.root_topic_dcids is None

    def test_get_dc_settings_missing_api_key(self):
        """Test missing required API key raises error."""
        with patch.dict(os.environ, {}, clear=True), pytest.raises(ValueError, match="DC_API_KEY"):
                get_dc_settings()

    def test_get_dc_settings_missing_custom_dc_url(self):
        """Test missing custom DC URL for custom DC raises error."""
        with patch.dict(os.environ, {"DC_API_KEY": "test_key", "DC_TYPE": "custom"}), pytest.raises(ValueError, match="CUSTOM_DC_URL"):
                get_dc_settings()

    def test_get_dc_settings_invalid_type(self):
        """Test invalid DC type raises error."""
        with patch.dict(os.environ, {"DC_API_KEY": "test_key", "DC_TYPE": "invalid"}), pytest.raises(ValueError, match="Input should be 'base'"):
                get_dc_settings()

    def test_get_dc_settings_defaults(self):
        """Test that defaults are applied correctly."""
        with patch.dict(os.environ, {"DC_API_KEY": "test_key", "DC_TYPE": "base"}):
            settings = get_dc_settings()

            # Base DC defaults
            assert settings.sv_search_base_url == "https://datacommons.org"
            assert settings.base_index == "base_uae_mem"

        with patch.dict(
            os.environ,
            {
                "DC_API_KEY": "test_key",
                "DC_TYPE": "custom",
                "CUSTOM_DC_URL": "https://test.com",
            },
        ):
            settings = get_dc_settings()

            # Custom DC defaults
            assert settings.search_scope == SearchScope.BASE_AND_CUSTOM
            assert settings.base_index == "medium_ft"
            assert settings.custom_index == "user_all_minilm_mem"

    def test_get_dc_settings_environment_overrides(self):
        """Test env vars override defaults."""
        with patch.dict(
            os.environ,
            {
                "DC_API_KEY": "test_key",
                "DC_TYPE": "base",
                "DC_SV_SEARCH_BASE_URL": "https://custom.com",
                "DC_BASE_INDEX": "custom_index",
            },
        ):
            settings = get_dc_settings()

            assert settings.sv_search_base_url == "https://custom.com"
            assert settings.base_index == "custom_index"

        with patch.dict(
            os.environ,
            {
                "DC_API_KEY": "test_key",
                "DC_TYPE": "custom",
                "CUSTOM_DC_URL": "https://test.com",
                "DC_SEARCH_SCOPE": "base_only",
                "DC_BASE_INDEX": "custom_base_index",
                "DC_CUSTOM_INDEX": "custom_custom_index",
            },
        ):
            settings = get_dc_settings()

            assert settings.search_scope == SearchScope.BASE_ONLY
            assert settings.base_index == "custom_base_index"
            assert settings.custom_index == "custom_custom_index"

    def test_get_dc_settings_search_scope_enum(self):
        """Test SearchScope enum conversion."""
        with patch.dict(
            os.environ,
            {
                "DC_API_KEY": "test_key",
                "DC_TYPE": "custom",
                "CUSTOM_DC_URL": "https://test.com",
                "DC_SEARCH_SCOPE": "custom_only",
            },
        ):
            settings = get_dc_settings()
            assert settings.search_scope == SearchScope.CUSTOM_ONLY

        with patch.dict(
            os.environ,
            {
                "DC_API_KEY": "test_key",
                "DC_TYPE": "custom",
                "CUSTOM_DC_URL": "https://test.com",
                "DC_SEARCH_SCOPE": "base_only",
            },
        ):
            settings = get_dc_settings()
            assert settings.search_scope == SearchScope.BASE_ONLY

    def test_get_dc_settings_root_topic_dcids(self):
        """Test root topic DCIDs parsing."""
        with patch.dict(
            os.environ,
            {
                "DC_API_KEY": "test_key",
                "DC_TYPE": "custom",
                "CUSTOM_DC_URL": "https://test.com",
                "DC_ROOT_TOPIC_DCIDS": "topic1,topic2,topic3",
            },
        ):
            settings = get_dc_settings()
            assert settings.root_topic_dcids == ["topic1", "topic2", "topic3"]

    def test_get_dc_settings_topic_cache_path(self):
        """Test topic cache path."""
        with patch.dict(
            os.environ,
            {
                "DC_API_KEY": "test_key",
                "DC_TYPE": "base",
                "DC_TOPIC_CACHE_PATH": "/path/to/cache.json",
            },
        ):
            settings = get_dc_settings()
            assert settings.topic_cache_path == "/path/to/cache.json"

    def test_get_dc_settings_default_dc_type(self):
        """Test that DC_TYPE defaults to 'base' when not provided."""
        with patch.dict(os.environ, {"DC_API_KEY": "test_key"}):
            settings = get_dc_settings()
            assert settings.dc_type == "base"
            assert isinstance(settings, BaseDCSettings)


class TestSettingsClasses:
    """Test settings classes directly."""

    def test_base_dc_settings_direct(self):
        """Test BaseDCSettings class directly."""
        with patch.dict(os.environ, {"DC_API_KEY": "test_key", "DC_TYPE": "base"}):
            settings = BaseDCSettings()

            assert settings.dc_type == "base"
            assert settings.api_key == "test_key"
            assert settings.sv_search_base_url == "https://datacommons.org"
            assert settings.base_index == "base_uae_mem"

    def test_custom_dc_settings_direct(self):
        """Test CustomDCSettings class directly."""
        with patch.dict(
            os.environ,
            {
                "DC_API_KEY": "test_key",
                "DC_TYPE": "custom",
                "CUSTOM_DC_URL": "https://test.com",
            },
        ):
            settings = CustomDCSettings()

            assert settings.dc_type == "custom"
            assert settings.api_key == "test_key"
            assert settings.custom_dc_url == "https://test.com"
            assert settings.api_base_url == "https://test.com/core/api/v2/"

    def test_settings_field_aliases(self):
        """Test that field aliases work correctly."""
        with patch.dict(
            os.environ,
            {
                "DC_API_KEY": "test_key",
                "DC_TYPE": "base",
                "DC_SV_SEARCH_BASE_URL": "https://custom.com",
            },
        ):
            settings = BaseDCSettings()
            assert settings.sv_search_base_url == "https://custom.com"
