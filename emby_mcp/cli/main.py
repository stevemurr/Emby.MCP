#!/usr/bin/env python3
"""CLI interface for Emby MCP management and testing."""

import typer
import sys
import json
import platform
from pathlib import Path
from typing import Optional
from emby_mcp import __version__
from emby_mcp.config import EmbyConfig
from emby_mcp.functions import *
from emby_mcp.debug import test_emby_functions
from emby_mcp import server as emby_server

app = typer.Typer(
    name="emby-mcp",
    help="Management and testing CLI for Emby Media Server integration.",
    add_completion=False,
)


# Colors and formatting for terminal output
class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def print_success(message: str) -> None:
    """Print a success message in green."""
    typer.echo(f"{Colors.GREEN}✓ {message}{Colors.RESET}")


def print_error(message: str) -> None:
    """Print an error message in red."""
    typer.echo(f"{Colors.RED}✗ {message}{Colors.RESET}")


def print_info(message: str) -> None:
    """Print an info message in blue."""
    typer.echo(f"{Colors.BLUE}ℹ {message}{Colors.RESET}")


@app.callback()
def main(
    ctx: typer.Context,
    env_file: Optional[str] = typer.Option(
        None, "--env", "-e",
        help="Path to .env file for Emby credentials",
    ),
    debug: bool = typer.Option(
        False, "--debug", "-d",
        help="Enable debug mode",
    ),
):
    """Emby MCP - Management CLI for Emby Media Server."""
    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug
    ctx.obj["env_file"] = env_file

    # Load the named .env file, or fall back to searching for one as the server does.
    # Commands that need credentials report any that are missing, so stay quiet here.
    load_config(ctx, env_file)


def load_config(ctx: typer.Context, env_file: Optional[str] = None) -> EmbyConfig:
    """Load configuration from the .env file named on the sub-command, else the one named on the CLI itself."""
    if env_file is None and ctx.obj:
        env_file = ctx.obj.get("env_file")
    if env_file and not Path(env_file).exists():
        print_error(f"Environment file not found: {env_file}")
        raise typer.Exit(code=1)
    return EmbyConfig(env_file)


def login(ctx: typer.Context, env_file: Optional[str] = None) -> dict:
    """Authenticate with the Emby server, exiting with an error if that is not possible."""
    config = load_config(ctx, env_file)

    if not config.is_valid:
        print_error(config.error_message)
        print_info("Use --env option to specify a .env file or set environment variables")
        raise typer.Exit(code=1)

    auth_result = authenticate_with_emby(
        server_url=config.server_url,
        username=config.username,
        password=config.password,
        verify_ssl=config.verify_ssl,
    )

    if not auth_result["success"]:
        print_error(f"Authentication failed: {auth_result['error']}")
        raise typer.Exit(code=1)

    return auth_result


@app.command()
def serve():
    """Run the MCP server."""
    emby_server.serve()


@app.command()
def test_connection(
    ctx: typer.Context,
    env_file: Optional[str] = typer.Option(None, "--env", "-e"),
):
    """Test connection to Emby server."""
    config = load_config(ctx, env_file)
    print_info(f"Testing connection to {config.server_url}...")

    auth_result = login(ctx, env_file)
    print_success("Connection successful!")
    print_info(f"Server: {config.server_url}")
    print_info(f"User: {config.username}")
    logout_from_emby(auth_result["api_client"])


@app.command()
def list_libraries(
    ctx: typer.Context,
    env_file: Optional[str] = typer.Option(None, "--env", "-e"),
    output_format: str = typer.Option("text", "--format", "-f", help="Output format: text, json"),
):
    """List all libraries from Emby server."""
    auth_result = login(ctx, env_file)
    api_client = auth_result["api_client"]

    try:
        result = get_library_list(api_client)
        if not result["success"]:
            print_error(f"Failed to retrieve libraries: {result['error']}")
            raise typer.Exit(code=1)

        libraries = result["items"]
        if output_format == "json":
            typer.echo(json.dumps(libraries, indent=2))
        else:
            typer.echo(f"{'Library':<30} {'Type':<15} {'ID':<40}")
            typer.echo("-" * 85)
            for lib in libraries:
                typer.echo(f"{lib['name']:<30} {lib['type'] or 'Unknown':<15} {lib['id']:<40}")

        print_success(f"Found {len(libraries)} libraries")

    finally:
        logout_from_emby(api_client)


@app.command()
def search(
    ctx: typer.Context,
    query: str = typer.Argument(..., help="Search query"),
    library: Optional[str] = typer.Option(None, "--library", "-L", help="Limit the search to this library name"),
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum results to return"),
    env_file: Optional[str] = typer.Option(None, "--env", "-e"),
):
    """Search for audio and video items in the Emby library."""
    auth_result = login(ctx, env_file)
    api_client = auth_result["api_client"]
    user_id = auth_result["user_id"]

    try:
        library_id = ""
        if library:
            library_result = get_library_list(api_client)
            if not library_result["success"]:
                print_error(f"Failed to retrieve libraries: {library_result['error']}")
                raise typer.Exit(code=1)
            selected = set_current_library(library_result["items"], library)
            if not selected["success"]:
                print_error(selected["error"])
                raise typer.Exit(code=1)
            library_id = selected["library"]["id"]

        items_result = get_items(api_client, user_id, library_id=library_id, search_term=query, limit=str(limit))

        if not items_result["success"]:
            print_error(f"Search failed: {items_result['error']}")
            raise typer.Exit(code=1)

        items = items_result["items"]
        typer.echo(f"Found {len(items)} results for '{query}'")
        typer.echo("-" * 60)

        for i, item in enumerate(items[:20], 1):  # Show first 20
            item_type = item["media_type"] or "Unknown"
            name = item["title"] or "Unknown"
            year = item["production_year"]
            typer.echo(f"{i:3d}. [{item_type}] {name} ({year})")

        if len(items) > 20:
            typer.echo(f"... and {len(items) - 20} more results")

    finally:
        logout_from_emby(api_client)


@app.command()
def debug():
    """Run interactive debugging tests on Emby functions."""
    print_info("Starting interactive debugging session...")
    print_info("This will test various Emby API functions interactively.\n")

    try:
        test_emby_functions(
            "Emby.MCP",
            __version__,
            platform.system(),
            platform.node(),
        )
    except KeyboardInterrupt:
        typer.echo("\nDebug session cancelled.")
    except Exception as e:
        print_error(f"Debug session failed: {e}")
        raise typer.Exit(code=1)


@app.command()
def version():
    """Show version information."""
    typer.echo(f"Emby MCP v{__version__}")
    typer.echo(f"Python: {sys.version.split()[0]}")
    typer.echo(f"Platform: {sys.platform}")


if __name__ == "__main__":
    app()