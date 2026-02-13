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
from datacommons_mcp.app import DCApp


@pytest.fixture
def mock_settings():
    from datacommons_mcp.data_models.settings import BaseDCSettings

    with patch("datacommons_mcp.app.settings.get_dc_settings") as mock:
        # Return a real BaseDCSettings object
        mock.return_value = BaseDCSettings(api_key="test-key")
        yield mock


@pytest.fixture
def mock_client():
    with patch("datacommons_mcp.app.create_dc_client") as mock:
        yield mock


@pytest.fixture
def mock_fastmcp():
    with patch("datacommons_mcp.app.FastMCP") as mock:
        # Return a mock instance
        mock_instance = MagicMock()
        mock.return_value = mock_instance
        yield mock


def test_app_initialization_default(mock_settings, mock_fastmcp):  # noqa: ARG001
    """Test that DCApp initializes with default instructions."""
    _ = DCApp()

    # Verify FastMCP was initialized with default instructions
    call_kwargs = mock_fastmcp.call_args[1]
    instructions = call_kwargs.get("instructions", "")
    # We expect "Data Commons" in the default server.md
    assert "Data Commons" in instructions


def test_app_initialization_override(
    mock_settings, mock_fastmcp, tmp_path, create_test_file
):
    """Test that DCApp loads instructions from DC_INSTRUCTIONS_DIR."""
    # Create custom instructions
    custom_dir = tmp_path / "instructions"
    create_test_file("instructions/server.md", "Custom Server Instructions")

    # Configure settings to use custom dir
    mock_settings.return_value.instructions_dir = str(custom_dir)

    _ = DCApp()

    # Verify FastMCP was initialized with custom instructions
    call_kwargs = mock_fastmcp.call_args[1]
    instructions = call_kwargs.get("instructions", "")
    assert instructions == "Custom Server Instructions"


def test_load_instruction_tool_override(mock_settings, tmp_path, create_test_file):
    """Test loading tool instructions with override."""
    # Create custom instructions
    custom_dir = tmp_path / "instructions"
    create_test_file("instructions/tools/test_tool.md", "Custom Tool Instructions")

    # Configure settings to use custom dir
    mock_settings.return_value.instructions_dir = str(custom_dir)

    app = DCApp()
    content = app._load_instruction("tools/test_tool.md")
    assert content == "Custom Tool Instructions"


def test_load_instruction_fallback(mock_settings, tmp_path):
    """Test that override falls back to default if file likely doesn't exist."""
    # Create custom dir but empty
    custom_dir = tmp_path / "instructions"
    custom_dir.mkdir()

    # Configure settings to use custom dir
    mock_settings.return_value.instructions_dir = str(custom_dir)

    app = DCApp()

    # Should fall back to default package resource (server.md exists in package)
    content = app._load_instruction("server.md")
    assert "Data Commons" in content


def test_register_tool(mock_settings, mock_fastmcp, tmp_path, create_test_file):
    """Test tool registration with instruction loading."""
    # Create custom instructions
    create_test_file("instructions/tools/sample.md", "Sample Tool Description")
    mock_settings.return_value.instructions_dir = str(tmp_path / "instructions")

    app = DCApp()
    mock_mcp_instance = mock_fastmcp.return_value

    def sample_tool():
        pass

    app.register_tool(sample_tool, "tools/sample.md")

    # Verify add_tool was called
    mock_mcp_instance.add_tool.assert_called_once()

    # Verify the description was loaded correctly
    tool_arg = mock_mcp_instance.add_tool.call_args[0][0]
    assert tool_arg.description == "Sample Tool Description"
