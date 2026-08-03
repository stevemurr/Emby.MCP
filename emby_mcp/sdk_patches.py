# -*- coding: utf-8 -*-
"""
Corrections to the official ``embyclient`` SDK, applied at import time.

The published SDK has two defects that stop this project working. Both used to be handled
by copying whole patched module files over the installed package, which meant the fixes
were lost to any reinstall of ``embyclient`` and had to be reapplied by hand. Patching the
objects in memory instead keeps the fixes with the code that needs them and leaves the
installed SDK untouched.

Both patches are idempotent, so importing this module more than once is harmless.
"""

import emby_client


# The header Emby expects the access token in, and the name the SDK's endpoints use when
# they ask for it. Taken from the SDK's own auth_settings references.
_EMBY_AUTH_NAME = 'embyauth'
_EMBY_TOKEN_HEADER = 'X-Emby-Token'

_PATCH_MARKER = '_emby_mcp_patched'


def _patch_auth_settings() -> None:
    """
    Teach Configuration about the 'embyauth' scheme.

    Endpoints throughout the SDK declare ``auth_settings = ['apikeyauth', 'embyauth']``, but
    Configuration.auth_settings() only ever defines 'apikeyauth'. The unknown name is
    skipped rather than raising, so every authenticated request goes out with no
    X-Emby-Token header and Emby rejects it.
    """
    original = emby_client.Configuration.auth_settings
    if getattr(original, _PATCH_MARKER, False):
        return

    def auth_settings(self):
        settings = original(self)
        settings.setdefault(_EMBY_AUTH_NAME, {
            'type': 'access_token',
            'in': 'header',
            'key': _EMBY_TOKEN_HEADER,
            'value': self.get_api_key_with_prefix('access_token'),
        })
        return settings

    setattr(auth_settings, _PATCH_MARKER, True)
    emby_client.Configuration.auth_settings = auth_settings


def _patch_user_item_access() -> None:
    """
    Let /Users/ItemAccess be filtered by item.

    The endpoint accepts an ItemId query parameter and is useless to us without it, since
    it answers "who may access this playlist". The SDK omits it from the method's accepted
    parameters, so passing item_id raises TypeError, and omitting it asks for the access
    list of every item on the server.

    Rather than restate the whole generated method, this wraps it: the request is built by
    the SDK as usual and the ItemId parameter is added to the query on the way out. Only the
    _with_http_info form needs patching, because the public get_users_itemaccess is a thin
    wrapper that forwards its keyword arguments to this one.
    """
    api_class = emby_client.UserServiceApi
    original = api_class.get_users_itemaccess_with_http_info
    if getattr(original, _PATCH_MARKER, False):
        return

    def get_users_itemaccess_with_http_info(self, **kwargs):
        item_id = kwargs.pop('item_id', None)
        if item_id is None:
            return original(self, **kwargs)

        # call_api takes query_params as its fourth positional argument. Overriding it on
        # this client instance only, for the duration of this one call, leaves the shared
        # ApiClient class alone so concurrent callers are unaffected.
        api_client = self.api_client
        underlying_call_api = api_client.call_api
        had_own_call_api = 'call_api' in vars(api_client)

        def call_api(resource_path, method, path_params, query_params, *args, **kw):
            query_params = list(query_params) + [('ItemId', item_id)]
            return underlying_call_api(resource_path, method, path_params, query_params, *args, **kw)

        api_client.call_api = call_api
        try:
            return original(self, **kwargs)
        finally:
            if had_own_call_api:
                api_client.call_api = underlying_call_api
            else:
                # Drop the instance attribute so the class method is visible again
                del api_client.call_api

    setattr(get_users_itemaccess_with_http_info, _PATCH_MARKER, True)
    api_class.get_users_itemaccess_with_http_info = get_users_itemaccess_with_http_info


def apply_sdk_patches() -> None:
    """
    Apply every correction this project needs to the installed embyclient SDK.

    Args:
        None

    Returns:
        None
    """
    _patch_auth_settings()
    _patch_user_item_access()
