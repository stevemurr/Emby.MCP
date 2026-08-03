# -*- coding: utf-8 -*-
"""
Emby MCP server module.

The server itself lives in the top-level ``emby_mcp_server`` script, which is where the
MCP tools are defined and registered. This module simply re-exports it so that the server
can also be reached as ``emby_mcp.server``.
"""

from emby_mcp_server import (
    MY_DEBUG,
    MY_LICENSE,
    MY_NAME,
    MY_PURPOSE,
    MY_VERSION,
    app_lifespan,
    configure_utf8_streams,
    main,
    mcp,
    serve,
)

__all__ = [
    "MY_DEBUG",
    "MY_LICENSE",
    "MY_NAME",
    "MY_PURPOSE",
    "MY_VERSION",
    "app_lifespan",
    "configure_utf8_streams",
    "main",
    "mcp",
    "serve",
]


if __name__ == "__main__":
    main()
