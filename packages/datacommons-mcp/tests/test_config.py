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
Tests for configuration module.
"""

import os
import pytest
from unittest.mock import patch

from datacommons_mcp.config import get_dc_config, _parse_csv
from datacommons_mcp.data_models.config import BaseDCConfig, CustomDCConfig
from datacommons_mcp.data_models.enums import SearchScope


class TestGetDCConfig:
    """Test get_dc_config function."""

    def test_get_dc_config_base(self):
        """Test base DC configuration returns BaseDCConfig."""
        with patch.dict(os.environ, {
            'DC_API_KEY': 'test_key',
            'DC_TYPE': 'base'
        }):
            config = get_dc_config()
            
            assert isinstance(config, BaseDCConfig)
            assert config.dc_type == 'base'
            assert config.api_key == 'test_key'
            assert config.sv_search_base_url == 'https://datacommons.org'
            assert config.base_index == 'base_uae_mem'
            assert config.topic_cache_path is None

    def test_get_dc_config_custom(self):
        """Test custom DC configuration returns CustomDCConfig."""
        with patch.dict(os.environ, {
            'DC_API_KEY': 'test_key',
            'DC_TYPE': 'custom',
            'DC_BASE_URL': 'https://test.com'
        }):
            config = get_dc_config()
            
            assert isinstance(config, CustomDCConfig)
            assert config.dc_type == 'custom'
            assert config.api_key == 'test_key'
            assert config.base_url == 'https://test.com'
            assert config.api_base_url == 'https://test.com/core/api/v2/'
            assert config.search_scope == SearchScope.BASE_AND_CUSTOM
            assert config.base_index == 'medium_ft'
            assert config.custom_index == 'user_all_minilm_mem'
            assert config.root_topic_dcids is None

    def test_get_dc_config_missing_api_key(self):
        """Test missing required API key raises error."""
        with patch('os.getenv', return_value=None):
            with pytest.raises(ValueError, match="DC_API_KEY environment variable is required"):
                get_dc_config()

    def test_get_dc_config_missing_base_url(self):
        """Test missing base URL for custom DC raises error."""
        with patch.dict(os.environ, {
            'DC_API_KEY': 'test_key',
            'DC_TYPE': 'custom'
        }):
            with pytest.raises(ValueError, match="DC_BASE_URL is required when DC_TYPE=custom"):
                get_dc_config()

    def test_get_dc_config_invalid_type(self):
        """Test invalid DC type raises error."""
        with patch.dict(os.environ, {
            'DC_API_KEY': 'test_key',
            'DC_TYPE': 'invalid'
        }):
            with pytest.raises(ValueError, match="Input should be 'base'"):
                get_dc_config()

    def test_get_dc_config_defaults(self):
        """Test that defaults are applied correctly."""
        with patch.dict(os.environ, {
            'DC_API_KEY': 'test_key',
            'DC_TYPE': 'base'
        }):
            config = get_dc_config()
            
            # Base DC defaults
            assert config.sv_search_base_url == 'https://datacommons.org'
            assert config.base_index == 'base_uae_mem'
            
        with patch.dict(os.environ, {
            'DC_API_KEY': 'test_key',
            'DC_TYPE': 'custom',
            'DC_BASE_URL': 'https://test.com'
        }):
            config = get_dc_config()
            
            # Custom DC defaults
            assert config.search_scope == SearchScope.BASE_AND_CUSTOM
            assert config.base_index == 'medium_ft'
            assert config.custom_index == 'user_all_minilm_mem'

    def test_get_dc_config_environment_overrides(self):
        """Test env vars override defaults."""
        with patch.dict(os.environ, {
            'DC_API_KEY': 'test_key',
            'DC_TYPE': 'base',
            'DC_SV_SEARCH_BASE_URL': 'https://custom.com',
            'DC_BASE_INDEX': 'custom_index'
        }):
            config = get_dc_config()
            
            assert config.sv_search_base_url == 'https://custom.com'
            assert config.base_index == 'custom_index'
            
        with patch.dict(os.environ, {
            'DC_API_KEY': 'test_key',
            'DC_TYPE': 'custom',
            'DC_BASE_URL': 'https://test.com',
            'DC_SEARCH_SCOPE': 'base_only',
            'DC_BASE_INDEX': 'custom_base_index',
            'DC_CUSTOM_INDEX': 'custom_custom_index'
        }):
            config = get_dc_config()
            
            assert config.search_scope == SearchScope.BASE_ONLY
            assert config.base_index == 'custom_base_index'
            assert config.custom_index == 'custom_custom_index'

    def test_get_dc_config_search_scope_enum(self):
        """Test SearchScope enum conversion."""
        with patch.dict(os.environ, {
            'DC_API_KEY': 'test_key',
            'DC_TYPE': 'custom',
            'DC_BASE_URL': 'https://test.com',
            'DC_SEARCH_SCOPE': 'custom_only'
        }):
            config = get_dc_config()
            assert config.search_scope == SearchScope.CUSTOM_ONLY
            
        with patch.dict(os.environ, {
            'DC_API_KEY': 'test_key',
            'DC_TYPE': 'custom',
            'DC_BASE_URL': 'https://test.com',
            'DC_SEARCH_SCOPE': 'base_only'
        }):
            config = get_dc_config()
            assert config.search_scope == SearchScope.BASE_ONLY

    def test_get_dc_config_root_topic_dcids(self):
        """Test root topic DCIDs parsing."""
        with patch.dict(os.environ, {
            'DC_API_KEY': 'test_key',
            'DC_TYPE': 'custom',
            'DC_BASE_URL': 'https://test.com',
            'DC_ROOT_TOPIC_DCIDS': 'topic1,topic2,topic3'
        }):
            config = get_dc_config()
            assert config.root_topic_dcids == ['topic1', 'topic2', 'topic3']

    def test_get_dc_config_topic_cache_path(self):
        """Test topic cache path."""
        with patch.dict(os.environ, {
            'DC_API_KEY': 'test_key',
            'DC_TYPE': 'base',
            'DC_TOPIC_CACHE_PATH': '/path/to/cache.json'
        }):
            config = get_dc_config()
            assert config.topic_cache_path == '/path/to/cache.json'

