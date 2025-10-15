import logging
import sys

import click

from .version import __version__


@click.group()
@click.version_option(version=__version__)
def cli() -> None:
    """DataCommons MCP CLI - Model Context Protocol server for Data Commons."""
    logging.basicConfig(level=logging.INFO)


@cli.group()
def serve() -> None:
    """Serve the MCP server in different modes."""


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
