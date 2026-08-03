# -*- coding: utf-8 -*-
"""Tests for the emby_mcp.server re-export shim."""

import emby_mcp_server
import emby_mcp.server


class TestServerModule:
    """The shim exists so the server can be reached as emby_mcp.server."""

    def test_every_exported_name_is_the_one_from_the_server_script(self):
        """A re-export that drifts would hand callers a different object of the same name."""
        for name in emby_mcp.server.__all__:
            assert getattr(emby_mcp.server, name) is getattr(emby_mcp_server, name)

    def test_the_shared_mcp_instance_is_not_a_second_server(self):
        """Two FastMCP instances would register tools that the running server never sees."""
        assert emby_mcp.server.mcp is emby_mcp_server.mcp
