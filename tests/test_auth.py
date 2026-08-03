# -*- coding: utf-8 -*-
"""Tests for Emby authentication and user functions."""

import pytest
from unittest.mock import patch, MagicMock
from emby_client.rest import ApiException
from emby_mcp.functions import (
    authenticate_with_emby,
    create_authenticated_client,
    get_users,
    logout_from_emby,
)


@pytest.fixture
def emby_config():
    """Patch the SDK Configuration and ApiClient used when building a client."""
    with patch('emby_mcp.functions.emby_client.Configuration') as mock_config, \
         patch('emby_mcp.functions.emby_client.ApiClient') as mock_client:
        config = MagicMock()
        mock_config.return_value = config
        client = MagicMock()
        client.configuration.api_key = {}
        mock_client.return_value = client
        yield config, client


class TestAuthentication:
    """Tests for logging in to Emby."""

    def test_successful_login(self, emby_config, sample_config):
        config, client = emby_config

        with patch('emby_mcp.functions.emby_client.UserServiceApi') as mock_user_api, \
             patch('emby_mcp.functions.emby_client.AuthenticateUserByName'):
            auth_response = MagicMock()
            auth_response.access_token = "test_token_123"
            auth_response.user.id = "user_456"
            auth_response.session_info = "session_xyz"
            mock_user_api.return_value.post_users_authenticatebyname.return_value = auth_response

            result = authenticate_with_emby(
                server_url=sample_config["server_url"],
                username=sample_config["username"],
                password=sample_config["password"],
                verify_ssl=True,
            )

        assert result["success"] == True
        assert result["access_token"] == "test_token_123"
        assert result["user_id"] == "user_456"
        assert result["session_info"] == "session_xyz"
        assert result["server_url"] == sample_config["server_url"]
        assert result["api_client"] is client
        assert client.configuration.api_key["access_token"] == "test_token_123"

    def test_login_sends_client_details_in_the_authorization_header(self, emby_config):
        with patch('emby_mcp.functions.emby_client.UserServiceApi') as mock_user_api, \
             patch('emby_mcp.functions.emby_client.AuthenticateUserByName'):
            authenticate_with_emby(
                "http://emby.test", "tester", "secret",
                client_name="Emby.MCP", client_version="9.9", device_name="laptop",
            )

            header = mock_user_api.return_value.post_users_authenticatebyname.call_args[1]["x_emby_authorization"]

        assert 'Client="Emby.MCP"' in header
        assert 'Device="laptop"' in header
        assert 'Version="9.9"' in header

    @pytest.mark.parametrize("requested,expected", [(True, True), (False, False), (None, True)])
    def test_ssl_verification_setting(self, emby_config, requested, expected):
        """verify_ssl=None means the caller did not choose, so verification stays on."""
        config, _ = emby_config

        with patch('emby_mcp.functions.emby_client.UserServiceApi'), \
             patch('emby_mcp.functions.emby_client.AuthenticateUserByName'):
            authenticate_with_emby("http://emby.test", "tester", "secret", verify_ssl=requested)

        assert config.verify_ssl == expected

    def test_failed_login_is_reported(self, emby_config):
        with patch('emby_mcp.functions.emby_client.UserServiceApi') as mock_user_api, \
             patch('emby_mcp.functions.emby_client.AuthenticateUserByName'):
            mock_user_api.return_value.post_users_authenticatebyname.side_effect = ApiException(status=401)

            result = authenticate_with_emby("http://emby.test", "tester", "wrong_password")

        assert result["success"] == False
        assert len(result["error"]) > 0


class TestCreateAuthenticatedClient:
    """Tests for rebuilding a client from a saved access token."""

    def test_token_is_applied(self, emby_config):
        config, client = emby_config

        result = create_authenticated_client("http://test.local", "token_123")

        assert result is client
        assert client.configuration.api_key["access_token"] == "token_123"
        assert config.host == "http://test.local"

    @pytest.mark.parametrize("requested,expected", [(True, True), (False, False), (None, True)])
    def test_ssl_verification_setting(self, emby_config, requested, expected):
        config, _ = emby_config

        create_authenticated_client("http://test.local", "token_123", verify_ssl=requested)

        assert config.verify_ssl == expected


class TestLogout:
    """Tests for logging out of Emby."""

    def test_successful_logout(self):
        with patch('emby_mcp.functions.emby_client.SessionsServiceApi') as mock_sessions:
            result = logout_from_emby(MagicMock())

            mock_sessions.return_value.post_sessions_logout.assert_called_once()

        assert result["success"] == True

    def test_failed_logout_is_reported(self):
        with patch('emby_mcp.functions.emby_client.SessionsServiceApi') as mock_sessions:
            mock_sessions.return_value.post_sessions_logout.side_effect = ApiException(status=500)

            result = logout_from_emby(MagicMock())

        assert result["success"] == False
        assert len(result["error"]) > 0


def make_user(name, user_id):
    """Build a mock Emby user."""
    user = MagicMock()
    user.name = name
    user.id = user_id
    return user


def set_queryable_users(mock_user_api, users):
    """
    Answer the authenticated /Users/Query listing with the given users.

    This is the endpoint get_users prefers, and it wraps its results in an object with an
    'items' attribute rather than returning a bare list.
    """
    mock_user_api.return_value.get_users_query.return_value.items = users


class TestGetUsers:
    """Tests for listing Emby users."""

    def test_all_users_are_listed(self):
        with patch('emby_mcp.functions.emby_client.UserServiceApi') as mock_user_api:
            set_queryable_users(mock_user_api, [
                make_user("Alice", "user_1"),
                make_user("Bob", "user_2"),
            ])

            result = get_users(MagicMock())

        assert result["success"] == True
        assert result["users"] == [
            {"user_name": "Alice", "user_id": "user_1"},
            {"user_name": "Bob", "user_id": "user_2"},
        ]

    def test_lookup_by_user_id_uses_the_direct_endpoint(self):
        with patch('emby_mcp.functions.emby_client.UserServiceApi') as mock_user_api:
            mock_user_api.return_value.get_users_by_id.return_value = make_user("Alice", "user_1")

            result = get_users(MagicMock(), user_id="user_1")

            mock_user_api.return_value.get_users_by_id.assert_called_once_with("user_1")
            mock_user_api.return_value.get_users_query.assert_not_called()
            mock_user_api.return_value.get_users_public.assert_not_called()

        assert result["users"] == [{"user_name": "Alice", "user_id": "user_1"}]

    def test_lookup_by_name_ignores_case_and_accents(self):
        with patch('emby_mcp.functions.emby_client.UserServiceApi') as mock_user_api:
            set_queryable_users(mock_user_api, [
                make_user("Renée", "user_1"),
                make_user("Bob", "user_2"),
            ])

            result = get_users(MagicMock(), user_name="renee")

        assert result["users"] == [{"user_name": "Renée", "user_id": "user_1"}]

    def test_user_without_a_name_does_not_break_the_search(self):
        """Emby can return a user with no name, which must not stop the lookup."""
        with patch('emby_mcp.functions.emby_client.UserServiceApi') as mock_user_api:
            set_queryable_users(mock_user_api, [
                make_user(None, "user_1"),
                make_user("Bob", "user_2"),
            ])

            result = get_users(MagicMock(), user_name="Bob")

        assert result["users"] == [{"user_name": "Bob", "user_id": "user_2"}]

    def test_users_missing_a_name_or_id_become_blank_strings(self):
        with patch('emby_mcp.functions.emby_client.UserServiceApi') as mock_user_api:
            set_queryable_users(mock_user_api, [make_user(None, None)])

            result = get_users(MagicMock())

        assert result["users"] == [{"user_name": "", "user_id": ""}]

    def test_empty_kwargs_are_ignored(self):
        """Blank filters mean 'no filter', not 'match blank'."""
        with patch('emby_mcp.functions.emby_client.UserServiceApi') as mock_user_api:
            set_queryable_users(mock_user_api, [make_user("Alice", "user_1")])

            result = get_users(MagicMock(), user_id="", user_name="")

        assert len(result["users"]) == 1

    def test_no_users_returns_an_empty_list(self):
        with patch('emby_mcp.functions.emby_client.UserServiceApi') as mock_user_api:
            set_queryable_users(mock_user_api, [])

            result = get_users(MagicMock())

        assert result == {"success": True, "users": []}

    def test_the_authenticated_listing_is_preferred(self):
        """
        /Users/Public only lists accounts that opted in to the login screen, so a server
        that hides them would report no users at all and leave playlist sharing unusable.
        """
        with patch('emby_mcp.functions.emby_client.UserServiceApi') as mock_user_api:
            set_queryable_users(mock_user_api, [make_user("Alice", "user_1")])

            result = get_users(MagicMock())

            mock_user_api.return_value.get_users_query.assert_called_once()
            mock_user_api.return_value.get_users_public.assert_not_called()

        assert result["users"] == [{"user_name": "Alice", "user_id": "user_1"}]

    def test_a_non_admin_account_falls_back_to_the_public_listing(self):
        """/Users/Query needs administrator rights and answers 403 without them."""
        with patch('emby_mcp.functions.emby_client.UserServiceApi') as mock_user_api:
            mock_user_api.return_value.get_users_query.side_effect = ApiException(status=403)
            mock_user_api.return_value.get_users_public.return_value = [make_user("Alice", "user_1")]

            result = get_users(MagicMock())

        assert result["success"] == True
        assert result["users"] == [{"user_name": "Alice", "user_id": "user_1"}]

    def test_api_error_is_reported(self):
        """A failure of both listings is an error, not an empty server."""
        with patch('emby_mcp.functions.emby_client.UserServiceApi') as mock_user_api:
            mock_user_api.return_value.get_users_query.side_effect = ApiException(status=403)
            mock_user_api.return_value.get_users_public.side_effect = ApiException(status=500)

            result = get_users(MagicMock())

        assert result["success"] == False
        assert len(result["error"]) > 0
