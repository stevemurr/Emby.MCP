# -*- coding: utf-8 -*-
"""Tests for server startup, the lifespan context, and the entry points."""

import asyncio
import io
import sys
import pytest
from unittest.mock import patch, MagicMock

import emby_mcp_server
from emby_mcp_server import app_lifespan, configure_utf8_streams, main, serve


ENV = {
    "EMBY_SERVER_URL": "http://emby.local",
    "EMBY_USERNAME": "testuser",
    "EMBY_PASSWORD": "testpassword",
}


def run_lifespan(collect=None):
    """
    Drive app_lifespan as an async context manager and return the context it yields.

    Args:
        collect (callable, optional): called with the yielded context while it is still open.

    Returns:
        dict: the context that was yielded.
    """
    async def drive():
        async with app_lifespan(MagicMock()) as context:
            if collect is not None:
                collect(context)
            return context

    return asyncio.run(drive())


@pytest.fixture
def logged_in():
    """Patch out the network so app_lifespan can run against a fake Emby server."""
    auth_result = {'success': True, 'api_client': MagicMock()}
    with patch('emby_mcp_server.find_dotenv', return_value=""), \
         patch('emby_mcp_server.authenticate_with_emby', return_value=auth_result) as auth, \
         patch('emby_mcp_server.logout_from_emby', return_value={'success': True}) as logout:
        yield auth, logout


class TestAppLifespan:
    """Tests for the lifespan context handed to every tool call."""

    def test_context_starts_with_nothing_selected(self, logged_in, monkeypatch):
        for name, value in ENV.items():
            monkeypatch.setenv(name, value)
        monkeypatch.delenv("LLM_MAX_ITEMS", raising=False)

        context = run_lifespan()

        assert context['available_libraries'] == []
        assert context['current_library'] == {}
        assert context['search_item_chunking'] == {}
        assert context['max_chunk_size'] == "100"

    def test_configured_chunk_size_is_carried_into_the_context(self, logged_in, monkeypatch):
        for name, value in ENV.items():
            monkeypatch.setenv(name, value)
        monkeypatch.setenv("LLM_MAX_ITEMS", "25")

        assert run_lifespan()['max_chunk_size'] == "25"

    def test_ssl_verification_setting_is_passed_to_login(self, logged_in, monkeypatch):
        auth, _ = logged_in
        for name, value in ENV.items():
            monkeypatch.setenv(name, value)
        monkeypatch.setenv("EMBY_VERIFY_SSL", "false")

        run_lifespan()

        # verify_ssl is the last positional argument to authenticate_with_emby
        assert auth.call_args[0][-1] == False

    def test_ssl_verification_defaults_to_on(self, logged_in, monkeypatch):
        auth, _ = logged_in
        for name, value in ENV.items():
            monkeypatch.setenv(name, value)
        monkeypatch.delenv("EMBY_VERIFY_SSL", raising=False)

        run_lifespan()

        assert auth.call_args[0][-1] == True

    def test_logout_happens_on_shutdown(self, logged_in, monkeypatch):
        """Leaving the session open would leave a stale device in the Emby server."""
        _, logout = logged_in
        for name, value in ENV.items():
            monkeypatch.setenv(name, value)

        run_lifespan()

        logout.assert_called_once()

    def test_logout_failure_does_not_mask_shutdown(self, logged_in, monkeypatch):
        """A failed logout is reported but must not raise out of the context manager."""
        _, logout = logged_in
        logout.return_value = {'success': False, 'error': 'already logged out'}
        for name, value in ENV.items():
            monkeypatch.setenv(name, value)

        run_lifespan()

        logout.assert_called_once()

    @pytest.mark.parametrize("missing", ["EMBY_SERVER_URL", "EMBY_USERNAME", "EMBY_PASSWORD"])
    def test_missing_credentials_stop_the_server(self, logged_in, monkeypatch, missing):
        for name, value in ENV.items():
            monkeypatch.setenv(name, value)
        monkeypatch.delenv(missing, raising=False)

        with pytest.raises(SystemExit) as exit_info:
            run_lifespan()

        assert exit_info.value.code == 1

    def test_failed_login_stops_the_server(self, monkeypatch):
        """Serving with no connection would fail every tool call instead of once here."""
        for name, value in ENV.items():
            monkeypatch.setenv(name, value)

        with patch('emby_mcp_server.find_dotenv', return_value=""), \
             patch('emby_mcp_server.authenticate_with_emby',
                   return_value={'success': False, 'error': 'bad password'}):
            with pytest.raises(SystemExit) as exit_info:
                run_lifespan()

        assert exit_info.value.code == 1

    def test_env_file_is_loaded_when_present(self, logged_in, monkeypatch):
        for name, value in ENV.items():
            monkeypatch.setenv(name, value)

        with patch('emby_mcp_server.find_dotenv', return_value="/somewhere/.env"), \
             patch('emby_mcp_server.load_dotenv') as load:
            run_lifespan()

        assert load.call_args[0][0] == "/somewhere/.env"


class TestConfigureUtf8Streams:
    """Tests for the stdio transport stream setup."""

    def test_streams_are_wrapped_as_line_buffered_utf8(self, monkeypatch):
        """
        The MCP stdio transport needs UTF-8 and immediate flushing, and non-UTF-8 default
        encodings (notably on Windows) would mangle media titles.
        """
        fake = MagicMock()
        monkeypatch.setattr(sys, 'stdin', fake)
        monkeypatch.setattr(sys, 'stdout', fake)
        monkeypatch.setattr(sys, 'stderr', fake)

        with patch('emby_mcp_server.io.TextIOWrapper') as wrapper:
            configure_utf8_streams()

        assert wrapper.call_count == 3
        for call in wrapper.call_args_list:
            assert call[1] == {'line_buffering': True, 'encoding': 'utf-8'}


class TestServe:
    """Tests for the entry point used by the emby-mcp CLI."""

    def test_stdio_transport_is_started(self):
        with patch('emby_mcp_server.configure_utf8_streams') as configure, \
             patch.object(emby_mcp_server.mcp, 'run') as run:
            serve()

        configure.assert_called_once()
        assert run.call_args[1] == {'transport': 'stdio'}

    def test_streams_are_configured_before_serving(self):
        """Wrapping the streams after mcp.run() starts would be too late to matter."""
        order = []
        with patch('emby_mcp_server.configure_utf8_streams', side_effect=lambda: order.append('configure')), \
             patch.object(emby_mcp_server.mcp, 'run', side_effect=lambda **kwargs: order.append('run')):
            serve()

        assert order == ['configure', 'run']


class TestMain:
    """Tests for the standalone entry point that runs startup checks first."""

    @pytest.fixture(autouse=True)
    def quiet_streams(self):
        """main() calls configure_utf8_streams, which would replace pytest's streams."""
        with patch('emby_mcp_server.configure_utf8_streams'):
            yield

    def test_startup_checks_run_before_serving(self, monkeypatch):
        for name, value in ENV.items():
            monkeypatch.setenv(name, value)

        with patch('emby_mcp_server.find_dotenv', return_value="/somewhere/.env"), \
             patch('emby_mcp_server.load_dotenv'), \
             patch('emby_mcp_server.authenticate_with_emby',
                   return_value={'success': True, 'api_client': MagicMock()}), \
             patch('emby_mcp_server.get_library_list',
                   return_value={'success': True, 'items': [{'name': 'Music'}]}), \
             patch('emby_mcp_server.logout_from_emby', return_value={'success': True}) as logout, \
             patch.object(emby_mcp_server.mcp, 'run') as run:
            main()

        logout.assert_called_once()
        assert run.call_args[1] == {'transport': 'stdio'}

    def test_missing_env_file_stops_startup(self):
        with patch('emby_mcp_server.find_dotenv', return_value=""), \
             patch.object(emby_mcp_server.mcp, 'run') as run:
            with pytest.raises(SystemExit) as exit_info:
                main()

        assert exit_info.value.code == 1
        run.assert_not_called()

    def test_missing_credentials_stop_startup(self, monkeypatch):
        for name in ENV:
            monkeypatch.delenv(name, raising=False)

        with patch('emby_mcp_server.find_dotenv', return_value="/somewhere/.env"), \
             patch('emby_mcp_server.load_dotenv'), \
             patch.object(emby_mcp_server.mcp, 'run') as run:
            with pytest.raises(SystemExit) as exit_info:
                main()

        assert exit_info.value.code == 1
        run.assert_not_called()

    def test_failed_login_stops_startup(self, monkeypatch):
        for name, value in ENV.items():
            monkeypatch.setenv(name, value)

        with patch('emby_mcp_server.find_dotenv', return_value="/somewhere/.env"), \
             patch('emby_mcp_server.load_dotenv'), \
             patch('emby_mcp_server.authenticate_with_emby',
                   return_value={'success': False, 'error': 'bad password'}), \
             patch.object(emby_mcp_server.mcp, 'run') as run:
            with pytest.raises(SystemExit) as exit_info:
                main()

        assert exit_info.value.code == 1
        run.assert_not_called()

    def test_failed_library_list_stops_startup(self, monkeypatch):
        """If the account cannot see any libraries, no tool would work."""
        for name, value in ENV.items():
            monkeypatch.setenv(name, value)

        with patch('emby_mcp_server.find_dotenv', return_value="/somewhere/.env"), \
             patch('emby_mcp_server.load_dotenv'), \
             patch('emby_mcp_server.authenticate_with_emby',
                   return_value={'success': True, 'api_client': MagicMock()}), \
             patch('emby_mcp_server.get_library_list',
                   return_value={'success': False, 'error': 'access denied'}), \
             patch.object(emby_mcp_server.mcp, 'run') as run:
            with pytest.raises(SystemExit) as exit_info:
                main()

        assert exit_info.value.code == 2
        run.assert_not_called()

    def test_failed_logout_stops_startup(self, monkeypatch):
        for name, value in ENV.items():
            monkeypatch.setenv(name, value)

        with patch('emby_mcp_server.find_dotenv', return_value="/somewhere/.env"), \
             patch('emby_mcp_server.load_dotenv'), \
             patch('emby_mcp_server.authenticate_with_emby',
                   return_value={'success': True, 'api_client': MagicMock()}), \
             patch('emby_mcp_server.get_library_list',
                   return_value={'success': True, 'items': []}), \
             patch('emby_mcp_server.logout_from_emby',
                   return_value={'success': False, 'error': 'session lost'}), \
             patch.object(emby_mcp_server.mcp, 'run') as run:
            with pytest.raises(SystemExit) as exit_info:
                main()

        assert exit_info.value.code == 2
        run.assert_not_called()
