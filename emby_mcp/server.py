# -*- coding: utf-8 -*-
"""Emby MCP server module."""

import os
import sys
import io
from typing import Optional
from platform import system as get_platform_system
from platform import node as get_platform_hostname
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from mcp.server.fastmcp import FastMCP, Context

# Configuration
from emby_mcp import __version__
from emby_mcp.functions import *
from emby_mcp.config import EmbyConfig

# Application metadata
MY_NAME = "Emby.MCP"
MY_VERSION = "1.0.2"
MY_PURPOSE = """These MCP tools allow you to control an Emby media server. Using them you can retrieve
a list of libraries, genres, playlists, audio & video items, and player sessions. 
You can add items to playlists and play, pause and stop itens on a player session."""
MY_LICENSE = """Emby.MCP Copyright (C) 2025 Dominic Search <code@angeltek.co.uk>
This program comes with ABSOLUTELY NO WARRANTY. This is free software, and you are 
welcome to redistribute it under certain conditions; see LICENSE.txt for details."""

# Environment
MY_PLATFORM = get_platform_system()
MY_HOSTNAME = get_platform_hostname()

# Set UTF-8 encoding
sys.stdin = io.TextIOWrapper(sys.stdin.buffer, line_buffering=True, encoding='utf-8')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, line_buffering=True, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, line_buffering=True, encoding='utf-8')


def str_to_bool(s: str) -> bool:
    """Convert string to boolean."""
    return str(s).strip().lower() in ("true", "1", "yes", "y", "on")


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """Manage application lifecycle and authenticate with Emby."""
    from dotenv import load_dotenv, find_dotenv
    from pathlib import Path
    
    # Load .env file
    env_file = find_dotenv('.env', usecwd=True)
    if env_file:
        load_dotenv(env_file, override=True)
    else:
        local_env = Path('.env')
        if local_env.exists():
            load_dotenv(local_env, override=True)
    
    # Extract configuration
    server_url = os.getenv("EMBY_SERVER_URL")
    username = os.getenv("EMBY_USERNAME")
    password = os.getenv("EMBY_PASSWORD")
    verify_ssl = str_to_bool(os.getenv("EMBY_VERIFY_SSL", "True"))
    max_chunk_size = os.getenv("LLM_MAX_ITEMS", "100")
    
    if not server_url or not username or not password:
        print(
            "Fatal error: missing required environment variables. "
            "Set EMBY_SERVER_URL, EMBY_USERNAME, and EMBY_PASSWORD.",
            file=sys.stderr,
        )
        sys.exit(1)
    
    # Authenticate
    from emby_mcp.auth import authenticate_with_emby, logout_from_emby
    
    device_name = MY_HOSTNAME + " (" + MY_PLATFORM + ")"
    client_name = f"{MY_NAME} for AI"
    
    auth_context = authenticate_with_emby(
        server_url, username, password, client_name, MY_VERSION, device_name, verify_ssl
    )
    
    if auth_context['success']:
        e_api_client = auth_context['api_client']
        auth_context['available_libraries'] = []
        auth_context['current_library'] = {}
        auth_context['max_chunk_size'] = max_chunk_size
        auth_context['search_item_chunking'] = {}
        print(f"Logon to media server was successful. \n\n{MY_LICENSE}", file=sys.stderr)
    else:
        print(f"Fatal ERROR: login to media server failed: {auth_context['error']}", file=sys.stderr)
        sys.exit(1)
    
    try:
        yield auth_context
    finally:
        e_api_client = auth_context['api_client']
        logout_result = logout_from_emby(e_api_client)
        if logout_result['success']:
            print("Logout from media server was successful", file=sys.stderr)
        else:
            print(f"ERROR: logout from media server failed: {logout_result['error']}", file=sys.stderr)


# Create the MCP server
mcp = FastMCP(name=MY_NAME, instructions=MY_PURPOSE, lifespan=app_lifespan)

# Import and register all tools
from emby_mcp.tools import users
from emby_mcp.tools import library
from emby_mcp.tools import search
from emby_mcp.tools import playlists
from emby_mcp.tools import players

# Register tools
users.register_tools(mcp)
library.register_tools(mcp)
search.register_tools(mcp)
playlists.register_tools(mcp)
players.register_tools(mcp)


def serve() -> None:
    """Run the MCP server."""
    mcp.run(transport='stdio')


def main() -> None:
    """Main entry point."""
    serve()


if __name__ == "__main__":
    main()