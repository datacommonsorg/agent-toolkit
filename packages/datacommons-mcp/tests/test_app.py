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
Unit tests for the DCApp class.
"""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_settings():
    from datacommons_mcp.data_models.settings import DCSettings

    with patch("datacommons_mcp.app.DCSettings") as mock:
        mock.return_value = DCSettings(api_key="test-key")
        yield mock


@pytest.fixture
def mock_fastmcp():
    with patch("datacommons_mcp.app.FastMCP") as mock:
        mock_instance = MagicMock()
        mock.return_value = mock_instance
        yield mock


def test_app_initialization_default(mock_settings, mock_fastmcp):  # noqa: ARG001
    """Test that DCApp initializes with default instructions."""
    from datacommons_mcp.app import DCApp

    _ = DCApp()

    call_kwargs = mock_fastmcp.call_args[1]
    instructions = call_kwargs.get("instructions", "")
    assert "Data Commons" in instructions


def test_app_initialization_override(
    mock_settings, mock_fastmcp, tmp_path, create_test_file
):
    """Test that DCApp loads instructions from DC_INSTRUCTIONS_DIR."""
    custom_dir = tmp_path / "instructions"
    create_test_file("instructions/server.md", "Custom Server Instructions")

    mock_settings.return_value.instructions_dir = str(custom_dir)

    from datacommons_mcp.app import DCApp

    _ = DCApp()

    call_kwargs = mock_fastmcp.call_args[1]
    instructions = call_kwargs.get("instructions", "")
    assert instructions == "Custom Server Instructions"


def test_load_instruction_tool_override(mock_settings, tmp_path, create_test_file):
    """Test loading tool instructions with override."""
    custom_dir = tmp_path / "instructions"
    create_test_file("instructions/tools/test_tool.md", "Custom Tool Instructions")

    mock_settings.return_value.instructions_dir = str(custom_dir)

    from datacommons_mcp.app import DCApp

    app = DCApp()
    content = app._load_instructions("tools/test_tool.md")
    assert content == "Custom Tool Instructions"


def test_load_instruction_fallback(mock_settings, tmp_path):
    """Test that override falls back to default if file likely doesn't exist."""
    custom_dir = tmp_path / "instructions"
    custom_dir.mkdir()

    mock_settings.return_value.instructions_dir = str(custom_dir)

    from datacommons_mcp.app import DCApp

    app = DCApp()

    content = app._load_instructions("server.md")
    assert "Data Commons" in content


def test_register_tool(mock_settings, mock_fastmcp, tmp_path, create_test_file):
    """Test tool registration with instruction loading."""
    create_test_file("instructions/tools/sample.md", "Sample Tool Description")
    mock_settings.return_value.instructions_dir = str(tmp_path / "instructions")

    from datacommons_mcp.app import DCApp

    app = DCApp()
    mock_mcp_instance = mock_fastmcp.return_value

    def sample_tool():
        pass

    app.register_tool(sample_tool, "tools/sample.md")

    mock_mcp_instance.add_tool.assert_called_once()
    tool_arg = mock_mcp_instance.add_tool.call_args[0][0]
    assert tool_arg.description == "Sample Tool Description"
