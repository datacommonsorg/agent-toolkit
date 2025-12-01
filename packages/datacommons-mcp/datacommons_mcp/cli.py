import logging
import os
import sys

import click
from click.core import Context, Option, ParameterSource
from dotenv import load_dotenv

from .exceptions import APIKeyValidationError, InvalidAPIKeyError
from .utils import validate_api_key
from .version import __version__

# A map of server modes to the set of option names applicable to that mode.
MODE_SPECIFIC_OPTIONS: dict[str, set[str]] = {
    "http": {"host", "port"},
    "stdio": set(),
}

# Options that are common to all modes.
COMMON_OPTIONS: set[str] = {"skip_api_key_validation"}


@click.group()
@click.version_option(version=__version__)
def cli() -> None:
    """DataCommons MCP CLI - Model Context Protocol server for Data Commons."""
    load_dotenv()
    logging.basicConfig(level=logging.INFO)


def _validate_mode_options(ctx: Context, mode: str) -> None:
    """Checks for options that are not applicable to the selected mode."""
    provided_options = {
        param.name
        for param in ctx.command.params
        if isinstance(param, Option)
        and ctx.get_parameter_source(param.name) is not ParameterSource.DEFAULT
    }
    allowed_options = COMMON_OPTIONS.union(MODE_SPECIFIC_OPTIONS.get(mode, set()))
    invalidly_used_options = provided_options - allowed_options

    if invalidly_used_options:
        # Format a user-friendly error message.
        opts_str = ", ".join(f"--{opt}" for opt in sorted(invalidly_used_options))
        raise click.UsageError(
            f"The following option(s) are not applicable in '{mode}' mode: {opts_str}"
        )


def _run_api_key_validation(ctx: Context, *, skip_validation: bool) -> None:
    """Runs the API key validation unless skipped."""
    if skip_validation:
        click.echo("Skipping API key validation as requested.", err=True)
        return

    try:
        api_key = os.getenv("DC_API_KEY")
        if not api_key:
            raise InvalidAPIKeyError("DC_API_KEY is not set.")
        validate_api_key(api_key)
    except (InvalidAPIKeyError, APIKeyValidationError) as e:
        click.echo(str(e), err=True)
        click.echo(
            "To obtain an API key, go to https://apikeys.datacommons.org and "
            "request a key for the api.datacommons.org domain.",
            err=True,
        )
        sys.stderr.flush()
        ctx.exit(1)


def _run_http_server(host: str, port: int) -> None:
    """Starts the server in Streamable HTTP mode."""
    from datacommons_mcp.server import mcp

    click.echo("Starting DataCommons MCP server in Streamable HTTP mode")
    click.echo(f"Version: {__version__}")
    click.echo(f"Server URL: http://{host}:{port}")
    click.echo(f"Streamable HTTP endpoint: http://{host}:{port}/mcp")
    click.echo("Press CTRL+C to stop")
    mcp.run(host=host, port=port, transport="streamable-http", stateless_http=True)


def _run_stdio_server() -> None:
    """Starts the server in stdio mode."""
    from datacommons_mcp.server import mcp

    click.echo("Starting DataCommons MCP server in stdio mode", err=True)
    click.echo(f"Version: {__version__}", err=True)
    click.echo("Server is ready to receive requests via stdin/stdout", err=True)
    mcp.run(transport="stdio")


@cli.command()
@click.argument("mode", type=click.Choice(["http", "stdio"]))
@click.option(
    "--skip-api-key-validation",
    is_flag=True,
    default=False,
    help="Skip the validation of the DC_API_KEY at startup.",
)
@click.option("--host", default="localhost", help="Host to bind (http mode only).")
@click.option("--port", default=8080, help="Port to bind (http mode only).", type=int)
@click.pass_context
def serve(
    ctx: click.Context,
    *,
    mode: str,
    skip_api_key_validation: bool,
    host: str,
    port: int,
) -> None:
    """Serve the MCP server in different modes."""
    _validate_mode_options(ctx, mode)
    _run_api_key_validation(ctx, skip_validation=skip_api_key_validation)

    try:
        if mode == "http":
            _run_http_server(host, port)
        elif mode == "stdio":
            _run_stdio_server()
    except ImportError as e:
        click.echo(f"Error starting server: {e}", err=True)
        sys.exit(1)


def main() -> None:
    """Main entry point for the CLI."""
    cli()
