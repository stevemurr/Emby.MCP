#!/usr/bin/env python3
"""CLI interface for Emby MCP management and testing."""

import typer
import sys
import json
import os
from pathlib import Path
from typing import Optional
from emby_mcp import __version__
from emby_mcp.config import EmbyConfig
from emby_mcp.functions import *
from emby_mcp.debug import test_emby_functions
from emby_mcp_server import serve

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


def print_warning(message: str) -> None:
    """Print a warning message in yellow."""
    typer.echo(f"{Colors.YELLOW}⚠ {message}{Colors.RESET}")


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
    
    # Try to load .env file
    if env_file:
        env_path = Path(env_file)
        if not env_path.exists():
            print_error(f"Environment file not found: {env_file}")
            sys.exit(1)
        os.environ["EMBY_SERVER_URL"] = os.getenv("EMBY_SERVER_URL", "")
        os.environ["EMBY_USERNAME"] = os.getenv("EMBY_USERNAME", "")
        os.environ["EMBY_PASSWORD"] = os.getenv("EMBY_PASSWORD", "")
        
        from dotenv import load_dotenv
        load_dotenv(env_path, override=True)
    
    # Validate required environment variables
    server_url = os.getenv("EMBY_SERVER_URL")
    username = os.getenv("EMBY_USERNAME")
    password = os.getenv("EMBY_PASSWORD")
    
    if not all([server_url, username, password]):
        print_warning("Missing required environment variables (EMBY_SERVER_URL, EMBY_USERNAME, EMBY_PASSWORD)")
        print_info("Use --env option to specify a .env file or set environment variables")


@app.command()
def serve():
    """Run the MCP server."""
    serve()  # Call the function from emby_mcp_server


@app.command()
def test_connection(
    env_file: Optional[str] = typer.Option(None, "--env", "-e"),
):
    """Test connection to Emby server."""
    server_url = os.getenv("EMBY_SERVER_URL")
    username = os.getenv("EMBY_USERNAME")
    password = os.getenv("EMBY_PASSWORD")
    verify_ssl = os.getenv("EMBY_VERIFY_SSL", "True").lower() in ("true", "1", "yes", "y", "on")
    
    if not all([server_url, username, password]):
        print_error("Missing required environment variables")
        sys.exit(1)
    
    print_info(f"Testing connection to {server_url}...")
    
    auth_result = authenticate_with_emby(
        server_url=server_url,
        username=username,
        password=password,
        verify_ssl=verify_ssl,
    )
    
    if auth_result["success"]:
        print_success("Connection successful!")
        print_info(f"Server: {server_url}")
        print_info(f"User: {username}")
    else:
        print_error(f"Connection failed: {auth_result['error']}")
        sys.exit(1)


@app.command()
def list_libraries(
    env_file: Optional[str] = typer.Option(None, "--env", "-e"),
    output_format: str = typer.Option("text", "--format", "-f", help="Output format: text, json"),
):
    """List all libraries from Emby server."""
    server_url = os.getenv("EMBY_SERVER_URL")
    username = os.getenv("EMBY_USERNAME")
    password = os.getenv("EMBY_PASSWORD")
    verify_ssl = os.getenv("EMBY_VERIFY_SSL", "True").lower() in ("true", "1", "yes", "y", "on")
    
    if not all([server_url, username, password]):
        print_error("Missing required environment variables")
        sys.exit(1)
    
    auth_result = authenticate_with_emby(
        server_url=server_url,
        username=username,
        password=password,
        verify_ssl=verify_ssl,
    )
    
    if not auth_result["success"]:
        print_error(f"Authentication failed: {auth_result['error']}")
        sys.exit(1)
    
    api_client = auth_result["api_client"]
    
    # Get libraries
    from emby_client import ApiLibraryApi
    library_api = ApiLibraryApi(api_client)
    
    try:
        # Get user info first
        users_api = emby_client.ApiUsersApi(api_client)
        user_response = users_api.get_current_user()
        user_id = user_response.Id
        
        # Get libraries
        library_items = library_api.get_libraries(
            user_id=user_id,
            include_item_types="Music,BoxSet,Movies,Photo,Playlists,TVShows",
        )
        
        if output_format == "json":
            libraries = [{"name": lib.Name, "id": lib.Id, "type": lib.CollectionType} for lib in library_items.Items]
            print(json.dumps(libraries, indent=2))
        else:
            typer.echo(f"{'Library':<30} {'Type':<15} {'ID':<40}")
            typer.echo("-" * 85)
            for lib in library_items.Items:
                typer.echo(f"{lib.Name:<30} {lib.CollectionType or 'Unknown':<15} {lib.Id:<40}")
        
        print_success(f"Found {len(library_items.Items)} libraries")
        
    except Exception as e:
        print_error(f"Failed to retrieve libraries: {e}")
        sys.exit(1)
    finally:
        # Cleanup
        logout_from_emby(api_client)


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    media_type: Optional[str] = typer.Option(None, "--type", "-t", help="Filter by media type: Movie, Series, Music, Audio"),
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum results to return"),
    env_file: Optional[str] = typer.Option(None, "--env", "-e"),
):
    """Search for media items in Emby library."""
    server_url = os.getenv("EMBY_SERVER_URL")
    username = os.getenv("EMBY_USERNAME")
    password = os.getenv("EMBY_PASSWORD")
    verify_ssl = os.getenv("EMBY_VERIFY_SSL", "True").lower() in ("true", "1", "yes", "y", "on")
    
    if not all([server_url, username, password]):
        print_error("Missing required environment variables")
        sys.exit(1)
    
    auth_result = authenticate_with_emby(
        server_url=server_url,
        username=username,
        password=password,
        verify_ssl=verify_ssl,
    )
    
    if not auth_result["success"]:
        print_error(f"Authentication failed: {auth_result['error']}")
        sys.exit(1)
    
    api_client = auth_result["api_client"]
    
    try:
        # Get user and library info
        users_api = emby_client.ApiUsersApi(api_client)
        user_response = users_api.get_current_user()
        user_id = user_response.Id
        
        # Get libraries
        library_api = emby_client.ApiLibraryApi(api_client)
        library_items = library_api.get_libraries(user_id=user_id)
        
        # Get items matching search
        from emby_client import ApiItemsApi
        items_api = ApiItemsApi(api_client)
        
        kwargs = {
            'search_term': query,
            'limit': limit,
            'include_item_types': media_type if media_type else None,
        }
        kwargs = {k: v for k, v in kwargs.items() if v is not None}
        
        items_result = get_items(api_client, user_id, **kwargs)
        
        if items_result['success']:
            items = items_result['items']
            typer.echo(f"Found {len(items)} results for '{query}'")
            typer.echo("-" * 60)
            
            for i, item in enumerate(items[:20], 1):  # Show first 20
                item_type = item.get('Type', 'Unknown')
                name = item.get('Name', 'Unknown')
                year = item.get('ProductionYear', '')
                typer.echo(f"{i:3d}. [{item_type}] {name} ({year})")
                
            if len(items) > 20:
                typer.echo(f"... and {len(items) - 20} more results")
        else:
            print_error(f"Search failed: {items_result['error']}")
            sys.exit(1)
            
    except Exception as e:
        print_error(f"Search failed: {e}")
        sys.exit(1)
    finally:
        logout_from_emby(api_client)


@app.command()
def debug():
    """Run interactive debugging tests on Emby functions."""
    print_info("Starting interactive debugging session...")
    print_info("This will test various Emby API functions interactively.\n")
    
    # Set debug mode for the test
    import emby_mcp.server as server_module
    server_module.MY_DEBUG = True
    
    try:
        test_emby_functions(
            name="Emby.MCP",
            version=__version__,
            platform="Unknown",
            hostname="debug-host",
        )
    except KeyboardInterrupt:
        typer.echo("\nDebug session cancelled.")
    except Exception as e:
        print_error(f"Debug session failed: {e}")
        sys.exit(1)


@app.command()
def version():
    """Show version information."""
    typer.echo(f"Emby MCP v{__version__}")
    typer.echo(f"Python: {sys.version.split()[0]}")
    typer.echo(f"Platform: {sys.platform}")


if __name__ == "__main__":
    app()