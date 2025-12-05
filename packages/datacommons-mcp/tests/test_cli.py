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
import os
from unittest import mock

from click.testing import CliRunner
from datacommons_mcp import cli as cli_module
from datacommons_mcp.cli import cli
from datacommons_mcp.exceptions import InvalidAPIKeyError
from datacommons_mcp.version import __version__


def test_main_calls_cli():
    """Tests that main() calls the cli() function."""
    with mock.patch.object(cli_module, "cli") as mock_cli:
        cli_module.main()
        mock_cli.assert_called_once()


def test_version_option():
    """Tests the --version flag."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert f"version {__version__}" in result.output


@mock.patch("datacommons_mcp.server.mcp.run")
@mock.patch("datacommons_mcp.cli.validate_api_key")
def test_serve_validates_key_by_default(mock_validate, mock_run):
    """Tests that the serve command calls validate_api_key by default."""
    runner = CliRunner()
    with mock.patch.dict(os.environ, {"DC_API_KEY": "test-key"}):
        runner.invoke(cli, ["serve", "http"])
        mock_validate.assert_called_once()
        mock_run.assert_called_once()


@mock.patch("datacommons_mcp.server.mcp.run")
@mock.patch("datacommons_mcp.cli.validate_api_key")
def test_serve_skip_validation_flag(mock_validate, mock_run):
    """Tests that the --skip-api-key-validation flag works."""
    runner = CliRunner()
    runner.invoke(cli, ["serve", "http", "--skip-api-key-validation"])
    mock_validate.assert_not_called()
    mock_run.assert_called_once()


@mock.patch("datacommons_mcp.server.mcp.run")
@mock.patch(
    "datacommons_mcp.cli.validate_api_key", side_effect=InvalidAPIKeyError("Test error")
)
def test_serve_validation_failure_exits(mock_validate, mock_run):
    """Tests that the command exits on validation failure."""
    runner = CliRunner()
    with mock.patch.dict(os.environ, {"DC_API_KEY": "test-key"}):
        result = runner.invoke(cli, ["serve", "http"])
        mock_validate.assert_called_once()
        mock_run.assert_not_called()
        assert result.exit_code == 1
        assert "Test error" in result.output


def test_serve_stdio_rejects_http_options():
    """Tests that stdio mode rejects http-specific options."""
    runner = CliRunner()

    def _assert_rejection(option, value):
        """Helper to assert rejection of an option."""
        result = runner.invoke(cli, ["serve", "stdio", option, value])
        assert result.exit_code == 2 # default exit code for click.UsageError
        assert "not applicable in 'stdio' mode" in result.output
        assert option in result.output

    _assert_rejection("--host", "localhost")
    _assert_rejection("--port", "8080")


@mock.patch("datacommons_mcp.server.mcp.run")
def test_serve_http_accepts_http_options(mock_run):
    """Tests that http mode accepts http-specific options."""
    runner = CliRunner()
    with mock.patch.dict(os.environ, {"DC_API_KEY": "test-key"}):
        result = runner.invoke(
            cli,
            [
                "serve",
                "http",
                "--host",
                "localhost",
                "--port",
                "9090",
                "--skip-api-key-validation",
            ],
        )
        assert result.exit_code == 0
        mock_run.assert_called_with(
            host="localhost",
            port=9090,
            transport="streamable-http",
            stateless_http=True,
        )


@mock.patch("datacommons_mcp.server.mcp.run")
@mock.patch("datacommons_mcp.cli.validate_api_key")
def test_serve_stdio_success(mock_validate, mock_run):
    """Tests that stdio mode starts the server correctly."""
    runner = CliRunner()
    with mock.patch.dict(os.environ, {"DC_API_KEY": "test-key"}):
        result = runner.invoke(cli, ["serve", "stdio"])
        assert result.exit_code == 0
        mock_validate.assert_called_once()
        mock_run.assert_called_with(transport="stdio")


def test_serve_missing_api_key():
    """Tests that the command fails if DC_API_KEY is missing."""
    runner = CliRunner()
    # The 'clean_env' autouse fixture in conftest.py ensures DC_API_KEY is not set.
    result = runner.invoke(cli, ["serve", "http"])
    assert result.exit_code == 1
    assert "DC_API_KEY is not set" in result.output


@mock.patch("datacommons_mcp.server.mcp.run")
@mock.patch("datacommons_mcp.cli.validate_api_key")
def test_cli_loads_dotenv_end_to_end(mock_validate, mock_run):
    """Tests that the CLI loads environment variables from .env in the current directory."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open(".env", "w") as f:
            f.write("DC_API_KEY=generated-key\n")

        result = runner.invoke(cli, ["serve", "http"])
        assert result.exit_code == 0
        # Verify validate_api_key was called with the key from .env
        mock_validate.assert_called_with("generated-key")
        mock_run.assert_called_once()
