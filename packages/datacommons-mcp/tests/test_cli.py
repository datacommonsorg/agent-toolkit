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


@mock.patch.dict(os.environ, {"DC_API_KEY": "test-key"})
@mock.patch("datacommons_mcp.server.mcp.run")
@mock.patch("datacommons_mcp.cli.validate_api_key")
def test_serve_validates_key_by_default(mock_validate, mock_run):
    """Tests that the serve command calls validate_api_key by default."""
    runner = CliRunner()
    runner.invoke(cli, ["serve", "http"])
    mock_validate.assert_called_once()
    mock_run.assert_called_once()


@mock.patch.dict(os.environ, {"DC_API_KEY": "test-key"})
@mock.patch("datacommons_mcp.server.mcp.run")
@mock.patch("datacommons_mcp.cli.validate_api_key")
def test_serve_skip_validation_flag(mock_validate, mock_run):
    """Tests that the --skip-api-key-validation flag works."""
    runner = CliRunner()
    runner.invoke(cli, ["serve", "http", "--skip-api-key-validation"])
    mock_validate.assert_not_called()
    mock_run.assert_called_once()


@mock.patch.dict(os.environ, {"DC_API_KEY": "test-key"})
@mock.patch("datacommons_mcp.server.mcp.run")
@mock.patch(
    "datacommons_mcp.cli.validate_api_key", side_effect=InvalidAPIKeyError("Test error")
)
def test_serve_validation_failure_exits(mock_validate, mock_run):
    """Tests that the command exits on validation failure."""
    runner = CliRunner()
    result = runner.invoke(cli, ["serve", "http"])
    mock_validate.assert_called_once()
    mock_run.assert_not_called()
    assert result.exit_code == 1
    assert "Test error" in result.output
