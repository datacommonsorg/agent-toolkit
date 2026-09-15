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
Tests for settings data model.
"""

import os
from unittest.mock import patch

from datacommons_mcp.data_models.enums import SearchScope
from datacommons_mcp.data_models.settings import DCSettings


class TestDCSettings:
    """Test suite for loading DCSettings."""

    def test_loads_with_minimal_config(self):
        """Tests that DCSettings loads with minimal config and correct defaults."""
        env_vars = {"DC_API_KEY": "test_key"}
        with patch.dict(os.environ, env_vars):
            settings = DCSettings()

            assert isinstance(settings, DCSettings)
            assert settings.api_key == "test_key"
            assert settings.agent_api_root == "https://api.datacommons.org/v2"
            assert settings.search_scope is None
            assert settings.instructions_dir is None

    def test_loads_with_env_var_overrides(self):
        """Tests that environment variables override defaults for DCSettings."""
        env_vars = {
            "DC_API_KEY": "custom_key",
            "DC_AGENT_API_ROOT": "https://custom-agent-api.datacommons.org/v2",
            "DC_SEARCH_SCOPE": "custom_only",
            "DC_INSTRUCTIONS_DIR": "/path/to/instructions",
        }
        with patch.dict(os.environ, env_vars):
            settings = DCSettings()

            assert isinstance(settings, DCSettings)
            assert settings.api_key == "custom_key"
            assert (
                settings.agent_api_root == "https://custom-agent-api.datacommons.org/v2"
            )
            assert settings.search_scope == SearchScope.CUSTOM_ONLY
            assert settings.instructions_dir == "/path/to/instructions"
