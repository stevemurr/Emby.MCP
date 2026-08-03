# -*- coding: utf-8 -*-
"""Test configuration for Emby MCP package."""

import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def isolate_dotenv():
    """
    Stop the tests discovering a real .env file.

    EmbyConfig and app_lifespan both load .env with override=True, so without this a
    developer's local credentials would silently replace the environment the tests set up,
    and the suite would pass or fail depending on whose machine it runs on. A .env named
    explicitly by a test is still loaded, since only discovery is blocked.

    app_lifespan also falls back to a bare Path('.env') when find_dotenv finds nothing,
    which discovery blocking alone does not cover, so its loader is stubbed as well. Tests
    that assert on loading patch load_dotenv themselves, and the inner patch wins.
    """
    from emby_mcp import server as emby_server  # noqa: F401  (imported for patching)

    with patch("emby_mcp.config.find_dotenv", return_value=""), \
         patch("emby_mcp.server.find_dotenv", return_value=""), \
         patch("emby_mcp.server.load_dotenv"):
        yield


@pytest.fixture
def auth_context():
    """A lifespan context as built by app_lifespan, with nothing selected yet."""
    return {
        'api_client': MagicMock(),
        'user_id': 'user_123',
        'available_libraries': [],
        'current_library': {},
        'max_chunk_size': '100',
        'search_item_chunking': {},
    }


@pytest.fixture
def mcp_context(auth_context):
    """Patch mcp.get_context() so the tools can run outside a live MCP session."""
    from emby_mcp import server as emby_server

    ctx = MagicMock()
    ctx.request_context.lifespan_context = auth_context
    with patch.object(emby_server.mcp, 'get_context', return_value=ctx):
        yield auth_context


@pytest.fixture
def selected_library(mcp_context):
    """A lifespan context with a music library already selected."""
    mcp_context['current_library'] = {'name': 'Music', 'id': 'lib_1', 'type': 'music'}
    mcp_context['available_libraries'] = [mcp_context['current_library']]
    return mcp_context


@pytest.fixture
def sample_config():
    """Sample configuration for testing."""
    return {
        "server_url": "http://test-emby-server.local",
        "username": "testuser",
        "password": "testpassword",
        "verify_ssl": True,
        "max_items": 100,
    }


@pytest.fixture
def mock_auth_response():
    """Mock authentication response from Emby server."""
    return {
        "success": True,
        "api_client": None,  # Will be replaced with mock in tests
    }


@pytest.fixture
def sample_library():
    """Sample library structure."""
    return {
        "Name": "Movies",
        "Id": "library-123",
        "CollectionType": "movies",
    }


@pytest.fixture
def sample_item():
    """Sample media item structure."""
    return {
        "Name": "Test Movie",
        "Id": "item-456",
        "Type": "Movie",
        "ProductionYear": 2024,
    }