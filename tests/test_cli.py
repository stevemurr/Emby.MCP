# -*- coding: utf-8 -*-
"""Tests for the emby-mcp command line interface."""

import json
import pytest
from unittest.mock import patch, MagicMock
from typer.testing import CliRunner

from emby_mcp.cli.main import app

runner = CliRunner()


@pytest.fixture
def env_file(tmp_path):
    """A .env file holding usable credentials."""
    path = tmp_path / ".env"
    path.write_text(
        "EMBY_SERVER_URL=http://emby.test\n"
        "EMBY_USERNAME=tester\n"
        "EMBY_PASSWORD=secret\n"
    )
    return str(path)


@pytest.fixture
def no_env(monkeypatch):
    """No credentials anywhere: no environment variables and no discoverable .env."""
    for name in ("EMBY_SERVER_URL", "EMBY_USERNAME", "EMBY_PASSWORD", "EMBY_VERIFY_SSL", "LLM_MAX_ITEMS"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def authenticated():
    """Patch authenticate_with_emby so commands get a working client without a server."""
    auth_result = {"success": True, "api_client": MagicMock(), "user_id": "user_123"}
    with patch("emby_mcp.cli.main.authenticate_with_emby", return_value=auth_result) as mock_auth, \
         patch("emby_mcp.cli.main.logout_from_emby") as mock_logout:
        yield mock_auth, mock_logout


class TestVersion:
    """Tests for the version command."""

    def test_version_reports_the_package_version(self, no_env):
        from emby_mcp import __version__

        result = runner.invoke(app, ["version"])

        assert result.exit_code == 0
        assert __version__ in result.output


class TestConfigLoading:
    """Tests for locating the .env file."""

    def test_missing_env_file_is_reported(self, no_env, tmp_path):
        result = runner.invoke(app, ["--env", str(tmp_path / "nope.env"), "version"])

        assert result.exit_code == 1
        assert "Environment file not found" in result.output

    def test_missing_credentials_are_reported(self, no_env):
        result = runner.invoke(app, ["test-connection"])

        assert result.exit_code == 1
        assert "EMBY_SERVER_URL" in result.output

    def test_env_file_given_on_the_cli_reaches_the_subcommand(self, no_env, env_file, authenticated):
        """--env before the sub-command must not be lost when the sub-command loads config."""
        mock_auth, _ = authenticated

        result = runner.invoke(app, ["--env", env_file, "test-connection"])

        assert result.exit_code == 0
        assert mock_auth.call_args[1]["server_url"] == "http://emby.test"

    def test_env_file_given_on_the_subcommand_wins(self, no_env, env_file, tmp_path, authenticated):
        other = tmp_path / "other.env"
        other.write_text(
            "EMBY_SERVER_URL=http://other.test\nEMBY_USERNAME=u\nEMBY_PASSWORD=p\n"
        )
        mock_auth, _ = authenticated

        result = runner.invoke(app, ["--env", env_file, "test-connection", "--env", str(other)])

        assert result.exit_code == 0
        assert mock_auth.call_args[1]["server_url"] == "http://other.test"


class TestTestConnection:
    """Tests for the test-connection command."""

    def test_successful_connection(self, no_env, env_file, authenticated):
        _, mock_logout = authenticated

        result = runner.invoke(app, ["--env", env_file, "test-connection"])

        assert result.exit_code == 0
        assert "Connection successful" in result.output
        mock_logout.assert_called_once()

    def test_failed_connection(self, no_env, env_file):
        with patch(
            "emby_mcp.cli.main.authenticate_with_emby",
            return_value={"success": False, "error": "bad password"},
        ):
            result = runner.invoke(app, ["--env", env_file, "test-connection"])

        assert result.exit_code == 1
        assert "bad password" in result.output


class TestListLibraries:
    """Tests for the list-libraries command."""

    libraries = {
        "success": True,
        "items": [
            {"name": "Music", "id": "lib_1", "type": "music"},
            {"name": "Home Videos", "id": "lib_2", "type": None},
        ],
    }

    def test_text_output(self, no_env, env_file, authenticated):
        with patch("emby_mcp.cli.main.get_library_list", return_value=self.libraries):
            result = runner.invoke(app, ["--env", env_file, "list-libraries"])

        assert result.exit_code == 0
        assert "Music" in result.output
        # a library with no collection type must still be listed
        assert "Unknown" in result.output
        assert "Found 2 libraries" in result.output

    def test_json_output(self, no_env, env_file, authenticated):
        with patch("emby_mcp.cli.main.get_library_list", return_value=self.libraries):
            result = runner.invoke(app, ["--env", env_file, "list-libraries", "--format", "json"])

        assert result.exit_code == 0
        payload = json.loads(result.output[: result.output.index("]") + 1])
        assert [lib["name"] for lib in payload] == ["Music", "Home Videos"]

    def test_error_is_reported(self, no_env, env_file, authenticated):
        _, mock_logout = authenticated
        with patch(
            "emby_mcp.cli.main.get_library_list",
            return_value={"success": False, "error": "server down"},
        ):
            result = runner.invoke(app, ["--env", env_file, "list-libraries"])

        assert result.exit_code == 1
        assert "server down" in result.output
        # we still log out of the server even when the command fails
        mock_logout.assert_called_once()


class TestSearch:
    """Tests for the search command."""

    def items(self, count):
        return {
            "success": True,
            "items": [
                {"title": f"Track {i}", "media_type": "Audio", "production_year": 2024}
                for i in range(count)
            ],
        }

    def test_search_across_all_libraries(self, no_env, env_file, authenticated):
        with patch("emby_mcp.cli.main.get_items", return_value=self.items(2)) as mock_get:
            result = runner.invoke(app, ["--env", env_file, "search", "rain"])

        assert result.exit_code == 0
        assert "Found 2 results" in result.output
        assert "Track 0" in result.output
        assert mock_get.call_args[1]["library_id"] == ""

    def test_search_truncates_long_result_lists(self, no_env, env_file, authenticated):
        with patch("emby_mcp.cli.main.get_items", return_value=self.items(25)):
            result = runner.invoke(app, ["--env", env_file, "search", "rain"])

        assert result.exit_code == 0
        assert "and 5 more results" in result.output

    def test_search_within_a_named_library(self, no_env, env_file, authenticated):
        libraries = {"success": True, "items": [{"name": "Music", "id": "lib_1", "type": "music"}]}
        with patch("emby_mcp.cli.main.get_library_list", return_value=libraries), \
             patch("emby_mcp.cli.main.get_items", return_value=self.items(1)) as mock_get:
            result = runner.invoke(app, ["--env", env_file, "search", "rain", "--library", "Music"])

        assert result.exit_code == 0
        assert mock_get.call_args[1]["library_id"] == "lib_1"

    def test_unknown_library_is_reported(self, no_env, env_file, authenticated):
        libraries = {"success": True, "items": [{"name": "Music", "id": "lib_1", "type": "music"}]}
        with patch("emby_mcp.cli.main.get_library_list", return_value=libraries):
            result = runner.invoke(app, ["--env", env_file, "search", "rain", "--library", "Films"])

        assert result.exit_code == 1
        assert "Library not found" in result.output

    def test_library_lookup_failure_is_reported(self, no_env, env_file, authenticated):
        with patch(
            "emby_mcp.cli.main.get_library_list",
            return_value={"success": False, "error": "server down"},
        ):
            result = runner.invoke(app, ["--env", env_file, "search", "rain", "--library", "Music"])

        assert result.exit_code == 1
        assert "server down" in result.output

    def test_search_failure_is_reported(self, no_env, env_file, authenticated):
        with patch(
            "emby_mcp.cli.main.get_items",
            return_value={"success": False, "error": "bad query"},
        ):
            result = runner.invoke(app, ["--env", env_file, "search", "rain"])

        assert result.exit_code == 1
        assert "bad query" in result.output


class TestServe:
    """Tests for the serve command."""

    def test_serve_runs_the_mcp_server(self, no_env):
        """The command must call the server, not recurse into itself."""
        with patch("emby_mcp.cli.main.emby_mcp_server.serve") as mock_serve:
            result = runner.invoke(app, ["serve"])

        assert result.exit_code == 0
        mock_serve.assert_called_once_with()


class TestDebug:
    """Tests for the debug command."""

    def test_debug_passes_positional_arguments(self, no_env):
        """test_emby_functions takes positional name/version/platform/hostname."""
        with patch("emby_mcp.cli.main.test_emby_functions") as mock_debug:
            result = runner.invoke(app, ["debug"])

        assert result.exit_code == 0
        name, version, platform_name, hostname = mock_debug.call_args[0]
        assert name == "Emby.MCP"
        assert version and platform_name and hostname

    def test_debug_handles_interruption(self, no_env):
        with patch("emby_mcp.cli.main.test_emby_functions", side_effect=KeyboardInterrupt):
            result = runner.invoke(app, ["debug"])

        assert result.exit_code == 0
        assert "cancelled" in result.output

    def test_debug_reports_failure(self, no_env):
        with patch("emby_mcp.cli.main.test_emby_functions", side_effect=RuntimeError("boom")):
            result = runner.invoke(app, ["debug"])

        assert result.exit_code == 1
        assert "boom" in result.output
