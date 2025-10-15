from unittest import mock

from click.testing import CliRunner
from datacommons_mcp import cli as cli_module
from datacommons_mcp.cli import cli
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
