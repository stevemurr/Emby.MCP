# -*- coding: utf-8 -*-
"""
Tests for the runtime corrections applied to the embyclient SDK.

These patches are what let the project talk to Emby at all, and they are applied against
whatever version of the SDK is installed, so they are exercised here against the real
emby_client classes rather than mocks of them.
"""

import pytest
from unittest.mock import patch

import emby_client
import emby_mcp.functions  # noqa: F401  (importing it applies the patches)
from emby_mcp.sdk_patches import apply_sdk_patches


@pytest.fixture
def configured_client():
    """A real ApiClient carrying an access token, as it would be after logging in."""
    config = emby_client.Configuration()
    config.api_key['access_token'] = 'token_abc'
    return emby_client.ApiClient(config)


def capture_call_api():
    """
    Patch ApiClient.call_api so a request can be inspected instead of sent.

    Returns the dict the call's arguments land in, and the patcher to stop afterwards.
    """
    captured = {}

    def fake_call_api(self, resource_path, method, path_params, query_params, *args, **kwargs):
        captured['resource_path'] = resource_path
        captured['query_params'] = list(query_params)
        return None

    patcher = patch.object(emby_client.ApiClient, 'call_api', fake_call_api)
    patcher.start()
    return captured, patcher


class TestAuthSettings:
    """Tests for the missing embyauth authentication scheme."""

    def test_embyauth_is_defined(self):
        """
        SDK endpoints declare auth_settings of ['apikeyauth', 'embyauth'], but the stock
        Configuration only defines the first. The unknown name is skipped rather than
        raising, so requests would go out with no token header at all.
        """
        config = emby_client.Configuration()
        config.api_key['access_token'] = 'token_abc'

        settings = config.auth_settings()

        assert settings['embyauth'] == {
            'type': 'access_token',
            'in': 'header',
            'key': 'X-Emby-Token',
            'value': 'token_abc',
        }

    def test_the_stock_scheme_is_left_alone(self):
        config = emby_client.Configuration()

        assert 'apikeyauth' in config.auth_settings()

    def test_the_token_is_read_at_call_time(self):
        """
        The client logs in after the Configuration is built, so the token arrives later
        than the patch does and must not be captured when the patch is applied.

        embyclient's Configuration shares api_key across instances, so the token is set
        and restored here rather than relying on a fresh instance being empty.
        """
        config = emby_client.Configuration()
        previous = config.api_key.get('access_token')
        try:
            config.api_key['access_token'] = 'token_first'
            assert config.auth_settings()['embyauth']['value'] == 'token_first'

            config.api_key['access_token'] = 'token_later'
            assert config.auth_settings()['embyauth']['value'] == 'token_later'
        finally:
            if previous is None:
                config.api_key.pop('access_token', None)
            else:
                config.api_key['access_token'] = previous


class TestUserItemAccess:
    """Tests for the missing ItemId parameter on /Users/ItemAccess."""

    def test_item_id_is_sent_as_a_query_parameter(self, configured_client):
        """Without this the endpoint answers for every item on the server, not the one asked about."""
        api = emby_client.UserServiceApi(configured_client)
        captured, patcher = capture_call_api()
        try:
            api.get_users_itemaccess(item_id='playlist_42')
        finally:
            patcher.stop()

        assert captured['resource_path'] == '/Users/ItemAccess'
        assert ('ItemId', 'playlist_42') in captured['query_params']

    def test_other_parameters_still_work(self, configured_client):
        api = emby_client.UserServiceApi(configured_client)
        captured, patcher = capture_call_api()
        try:
            api.get_users_itemaccess(item_id='playlist_42', limit=5)
        finally:
            patcher.stop()

        assert ('ItemId', 'playlist_42') in captured['query_params']
        assert ('Limit', 5) in captured['query_params']

    def test_omitting_item_id_sends_no_item_filter(self, configured_client):
        api = emby_client.UserServiceApi(configured_client)
        captured, patcher = capture_call_api()
        try:
            api.get_users_itemaccess()
        finally:
            patcher.stop()

        assert not any(name == 'ItemId' for name, _ in captured['query_params'])

    def test_the_shared_client_is_left_unchanged(self, configured_client):
        """
        The ItemId parameter is injected by overriding call_api on the client for the
        duration of one request, so a leaked override would corrupt every later call.
        """
        api = emby_client.UserServiceApi(configured_client)
        captured, patcher = capture_call_api()
        try:
            api.get_users_itemaccess(item_id='playlist_42')
        finally:
            patcher.stop()

        assert 'call_api' not in vars(configured_client)

    def test_a_clients_own_call_api_is_restored_not_deleted(self, configured_client):
        """
        Nothing in this project overrides call_api per client, but a test double or a
        wrapping library might, and deleting it would silently disarm them.
        """
        sentinel_calls = []

        def clients_own_call_api(resource_path, method, path_params, query_params, *args, **kwargs):
            sentinel_calls.append(list(query_params))
            return None

        configured_client.call_api = clients_own_call_api
        api = emby_client.UserServiceApi(configured_client)

        api.get_users_itemaccess(item_id='playlist_42')

        assert configured_client.call_api is clients_own_call_api
        assert ('ItemId', 'playlist_42') in sentinel_calls[0]

    def test_the_override_is_removed_even_when_the_request_fails(self, configured_client):
        api = emby_client.UserServiceApi(configured_client)

        with patch.object(emby_client.ApiClient, 'call_api', side_effect=RuntimeError("boom")):
            with pytest.raises(RuntimeError):
                api.get_users_itemaccess(item_id='playlist_42')

        assert 'call_api' not in vars(configured_client)


class TestIdempotence:
    """The patches are applied on import, which can happen more than once."""

    def test_reapplying_does_not_wrap_twice(self):
        """Stacked wrappers would append ItemId once per application."""
        before_auth = emby_client.Configuration.auth_settings
        before_access = emby_client.UserServiceApi.get_users_itemaccess_with_http_info

        apply_sdk_patches()
        apply_sdk_patches()

        assert emby_client.Configuration.auth_settings is before_auth
        assert emby_client.UserServiceApi.get_users_itemaccess_with_http_info is before_access

    def test_item_id_is_still_sent_only_once_after_reapplying(self, configured_client):
        apply_sdk_patches()
        api = emby_client.UserServiceApi(configured_client)
        captured, patcher = capture_call_api()
        try:
            api.get_users_itemaccess(item_id='playlist_42')
        finally:
            patcher.stop()

        item_ids = [value for name, value in captured['query_params'] if name == 'ItemId']
        assert item_ids == ['playlist_42']
