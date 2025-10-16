import logging
import os
import sys

import click

from .exceptions import APIKeyValidationError, InvalidAPIKeyError
from .utils import validate_api_key
from .version import __version__


@click.group()
@click.version_option(version=__version__)
def cli() -> None:
    """DataCommons MCP CLI - Model Context Protocol server for Data Commons."""
    logging.basicConfig(level=logging.INFO)


@cli.group(context_settings={"allow_interspersed_args": True})
@click.option(
    "--skip-api-key-validation",
    is_flag=True,
    default=False,
    help="Skip the validation of the DC_API_KEY at startup.",
)
@click.pass_context
def serve(ctx: click.Context, *, skip_api_key_validation: bool) -> None:
    """Serve the MCP server in different modes."""
    if not skip_api_key_validation:
        try:
            validate_api_key(os.getenv("DC_API_KEY"))
        except (InvalidAPIKeyError, APIKeyValidationError) as e:
            click.echo(str(e), err=True)
            click.echo(
                "To obtain an API key, go to https://apikeys.datacommons.org and "
                "request a key for the api.datacommons.org domain.",
                err=True,
            )
            sys.stderr.flush()
            ctx.exit(1)
    else:
        click.echo("Skipping API key validation as requested.")


@serve.command()
@click.option("--host", default="localhost", help="Host to bind.")
@click.option("--port", default=8080, help="Port to bind.", type=int)
def http(host: str, port: int) -> None:
    """Start the MCP server in Streamable HTTP mode."""
    try:
        from datacommons_mcp.server import mcp

        click.echo("Starting DataCommons MCP server in Streamable HTTP mode")
        click.echo(f"Version: {__version__}")
        click.echo(f"Server URL: http://{host}:{port}")
        click.echo(f"Streamable HTTP endpoint: http://{host}:{port}/mcp")
        click.echo("Press CTRL+C to stop")

        mcp.run(host=host, port=port, transport="streamable-http", stateless_http=True)

    except ImportError as e:
        click.echo(f"Error importing server: {e}", err=True)
        sys.exit(1)


@serve.command()
def stdio() -> None:
    """Start the MCP server in stdio mode."""
    try:
        from datacommons_mcp.server import mcp

        click.echo("Starting DataCommons MCP server in stdio mode", err=True)
        click.echo(f"Version: {__version__}", err=True)
        click.echo("Server is ready to receive requests via stdin/stdout", err=True)

        mcp.run(transport="stdio")

    except ImportError as e:
        click.echo(f"Error importing server: {e}", err=True)
        sys.exit(1)


def main() -> None:
    """Main entry point for the CLI."""
    cli()
