# -*- coding: utf-8 -*-
"""Tests for creating, listing and modifying Emby playlists."""

import pytest
from unittest.mock import patch, MagicMock
from emby_client.rest import ApiException
from emby_mcp.functions import (
    add_playlist_items,
    delete_playlist_items,
    get_playlists,
    move_playlist_items,
    new_playlist,
    set_playlist_meta,
)

LIBRARIES = [
    {"name": "Music", "id": "lib_1", "type": "music"},
    {"name": "Playlists", "id": "lib_pl", "type": "playlists"},
]


def make_playlist(name="My List", playlist_id="pl_1", item_type="Playlist", run_time_ticks=18000000000):
    """Build a mock Emby playlist item."""
    item = MagicMock()
    item.name = name
    item.id = playlist_id
    item.type = item_type
    item.overview = "notes"
    item.genres = ["Rock"]
    item.run_time_ticks = run_time_ticks
    item.date_created.isoformat.return_value = "2024-01-01"
    return item


def make_access(user_id, level):
    """Build a mock Emby per-user item access record."""
    access = MagicMock()
    access.id = user_id
    access.name = f"name_{user_id}"
    access.user_item_share_level = level
    return access


@pytest.fixture
def items_api():
    """Patch ItemsServiceApi, used to list the contents of the playlists library."""
    with patch('emby_mcp.functions.emby_client.ItemsServiceApi') as mock_api:
        yield mock_api.return_value


@pytest.fixture
def user_api():
    """Patch UserServiceApi, used to read per-user access to a playlist."""
    with patch('emby_mcp.functions.emby_client.UserServiceApi') as mock_api:
        mock_api.return_value.get_users_itemaccess.return_value.total_record_count = 0
        yield mock_api.return_value


def set_playlist_response(items_api, items):
    """Make the items API return the given playlist items."""
    response = MagicMock()
    response.total_record_count = len(items)
    response.items = items
    items_api.get_users_by_userid_items.return_value = response


class TestGetPlaylists:
    """Tests for listing playlists."""

    def test_playlists_are_returned(self, items_api, user_api):
        set_playlist_response(items_api, [make_playlist()])

        result = get_playlists(MagicMock(), "user_123", LIBRARIES)

        assert result["success"] == True
        playlist = result["playlists"][0]
        assert playlist["name"] == "My List"
        assert playlist["playlist_id"] == "pl_1"
        assert playlist["run_time"] == "00:30:00"
        assert playlist["can_share"] == False
        assert "run_time_ticks" not in playlist

    def test_the_playlists_library_is_searched(self, items_api, user_api):
        """Playlists live in their own library, which must be found by type not by name."""
        set_playlist_response(items_api, [])

        get_playlists(MagicMock(), "user_123", LIBRARIES)

        assert items_api.get_users_by_userid_items.call_args[1]["parent_id"] == "lib_pl"

    def test_non_playlist_items_are_excluded(self, items_api, user_api):
        set_playlist_response(items_api, [make_playlist(), make_playlist(item_type="Folder")])

        result = get_playlists(MagicMock(), "user_123", LIBRARIES)

        assert len(result["playlists"]) == 1

    def test_a_single_playlist_can_be_requested(self, items_api, user_api):
        set_playlist_response(items_api, [make_playlist()])

        get_playlists(MagicMock(), "user_123", LIBRARIES, playlist_id="pl_1")

        assert items_api.get_users_by_userid_items.call_args[1]["ids"] == "pl_1"

    def test_manage_access_means_we_can_share(self, items_api, user_api):
        set_playlist_response(items_api, [make_playlist()])
        access_response = MagicMock()
        access_response.total_record_count = 2
        access_response.items = [make_access("user_123", "Manage"), make_access("user_9", "Read")]
        user_api.get_users_itemaccess.return_value = access_response

        result = get_playlists(MagicMock(), "user_123", LIBRARIES)

        assert result["playlists"][0]["can_share"] == True
        assert len(result["playlists"][0]["user_access"]) == 2

    def test_read_access_means_we_cannot_share(self, items_api, user_api):
        set_playlist_response(items_api, [make_playlist()])
        access_response = MagicMock()
        access_response.total_record_count = 1
        access_response.items = [make_access("user_123", "Read")]
        user_api.get_users_itemaccess.return_value = access_response

        result = get_playlists(MagicMock(), "user_123", LIBRARIES)

        assert result["playlists"][0]["can_share"] == False

    def test_access_lookup_failure_is_not_fatal(self, items_api, user_api):
        """Access lookups fail for playlists we do not own, which must not fail the listing."""
        set_playlist_response(items_api, [make_playlist()])
        user_api.get_users_itemaccess.side_effect = ApiException(status=403)

        result = get_playlists(MagicMock(), "user_123", LIBRARIES)

        assert result["success"] == True
        assert result["playlists"][0]["user_access"] == []

    def test_no_playlists_returns_an_empty_list(self, items_api, user_api):
        set_playlist_response(items_api, [])

        result = get_playlists(MagicMock(), "user_123", LIBRARIES)

        assert result == {"success": True, "playlists": []}

    def test_api_error_is_reported(self, items_api, user_api):
        items_api.get_users_by_userid_items.side_effect = ApiException(status=500)

        result = get_playlists(MagicMock(), "user_123", LIBRARIES)

        assert result["success"] == False
        assert len(result["error"]) > 0

    def test_missing_playlists_library_is_reported(self):
        result = get_playlists(MagicMock(), "user_123", [{"name": "Music", "id": "lib_1", "type": "music"}])

        assert result["success"] == False
        assert "No playlist libraries" in result["error"]

    @pytest.mark.parametrize("libraries", [[], None])
    def test_missing_libraries_are_reported(self, libraries):
        result = get_playlists(MagicMock(), "user_123", libraries)

        assert result["success"] == False
        assert "No libraries" in result["error"]


class TestNewPlaylist:
    """Tests for creating a playlist."""

    @pytest.fixture
    def playlist_api(self):
        with patch('emby_mcp.functions.emby_client.PlaylistServiceApi') as mock_api:
            mock_api.return_value.post_playlists.return_value.id = "pl_new"
            yield mock_api.return_value

    @pytest.fixture
    def no_existing_playlists(self):
        with patch('emby_mcp.functions.get_playlists', return_value={"success": True, "playlists": []}):
            yield

    def test_playlist_is_created(self, playlist_api, no_existing_playlists):
        result = new_playlist(MagicMock(), "user_123", LIBRARIES, "New List")

        assert result == {"success": True, "playlist_id": "pl_new"}
        assert playlist_api.post_playlists.call_args[1]["media_type"] == "Audio"

    def test_media_type_can_be_chosen(self, playlist_api, no_existing_playlists):
        new_playlist(MagicMock(), "user_123", LIBRARIES, "New List", media_type="Video")

        assert playlist_api.post_playlists.call_args[1]["media_type"] == "Video"

    def test_overview_is_applied_as_a_second_step(self, playlist_api, no_existing_playlists):
        """Emby cannot set an overview at creation time, so the item is updated afterwards."""
        with patch('emby_mcp.functions.emby_client.UserLibraryServiceApi') as mock_userlib, \
             patch('emby_mcp.functions.emby_client.ItemUpdateServiceApi') as mock_update:
            playlist_object = MagicMock()
            mock_userlib.return_value.get_users_by_userid_items_by_id.return_value = playlist_object

            result = new_playlist(MagicMock(), "user_123", LIBRARIES, "New List", overview="notes")

        assert result["success"] == True
        assert playlist_object.overview == "notes"
        assert mock_update.return_value.post_items_by_itemid.call_args[1]["item_id"] == "pl_new"

    def test_overview_lookup_failure_is_reported(self, playlist_api, no_existing_playlists):
        with patch('emby_mcp.functions.emby_client.UserLibraryServiceApi') as mock_userlib:
            mock_userlib.return_value.get_users_by_userid_items_by_id.side_effect = ApiException(status=404)

            result = new_playlist(MagicMock(), "user_123", LIBRARIES, "New List", overview="notes")

        assert result["success"] == False

    def test_overview_update_failure_is_reported(self, playlist_api, no_existing_playlists):
        with patch('emby_mcp.functions.emby_client.UserLibraryServiceApi'), \
             patch('emby_mcp.functions.emby_client.ItemUpdateServiceApi') as mock_update:
            mock_update.return_value.post_items_by_itemid.side_effect = ApiException(status=500)

            result = new_playlist(MagicMock(), "user_123", LIBRARIES, "New List", overview="notes")

        assert result["success"] == False

    @pytest.mark.parametrize("name", ["", "   ", None])
    def test_blank_names_are_rejected(self, name):
        result = new_playlist(MagicMock(), "user_123", LIBRARIES, name)

        assert result["success"] == False
        assert "cannot be empty" in result["error"]

    def test_duplicate_names_are_rejected(self, playlist_api):
        existing = {"success": True, "playlists": [{"name": "New List", "playlist_id": "pl_1"}]}
        with patch('emby_mcp.functions.get_playlists', return_value=existing):
            result = new_playlist(MagicMock(), "user_123", LIBRARIES, "new list")

        assert result["success"] == False
        assert "already exists" in result["error"]

    def test_unknown_parameters_are_rejected(self, playlist_api, no_existing_playlists):
        result = new_playlist(MagicMock(), "user_123", LIBRARIES, "New List", colour="red")

        assert result["success"] == False
        assert "Unknown function parameter" in result["error"]

    def test_a_server_that_returns_no_id_is_reported(self, playlist_api, no_existing_playlists):
        playlist_api.post_playlists.return_value = None

        result = new_playlist(MagicMock(), "user_123", LIBRARIES, "New List")

        assert result["success"] == False
        assert "Failed to create playlist" in result["error"]

    def test_api_error_is_reported(self, playlist_api, no_existing_playlists):
        playlist_api.post_playlists.side_effect = ApiException(status=500)

        result = new_playlist(MagicMock(), "user_123", LIBRARIES, "New List")

        assert result["success"] == False
        assert len(result["error"]) > 0


class TestSetPlaylistMeta:
    """Tests for renaming a playlist and changing its description."""

    @pytest.fixture
    def emby(self):
        with patch('emby_mcp.functions.emby_client.PlaylistServiceApi'), \
             patch('emby_mcp.functions.emby_client.UserLibraryServiceApi') as mock_userlib, \
             patch('emby_mcp.functions.emby_client.ItemUpdateServiceApi') as mock_update, \
             patch('emby_mcp.functions.get_playlists', return_value={"success": True, "playlists": []}):
            playlist_object = MagicMock()
            mock_userlib.return_value.get_users_by_userid_items_by_id.return_value = playlist_object
            yield playlist_object, mock_userlib.return_value, mock_update.return_value

    def test_name_and_overview_are_updated(self, emby):
        playlist_object, _, update_api = emby

        result = set_playlist_meta(MagicMock(), "user_123", LIBRARIES, "pl_1", name="Renamed", overview="notes")

        assert result == {"success": True}
        assert playlist_object.name == "Renamed"
        assert playlist_object.overview == "notes"
        update_api.post_items_by_itemid.assert_called_once()

    def test_no_changes_is_rejected(self):
        result = set_playlist_meta(MagicMock(), "user_123", LIBRARIES, "pl_1")

        assert result["success"] == False
        assert "No changes specified" in result["error"]

    def test_unknown_parameters_are_rejected(self):
        result = set_playlist_meta(MagicMock(), "user_123", LIBRARIES, "pl_1", colour="red")

        assert result["success"] == False
        assert "Unknown function parameter" in result["error"]

    def test_renaming_onto_another_playlist_is_rejected(self, emby):
        existing = {"success": True, "playlists": [{"name": "Taken", "playlist_id": "pl_other"}]}
        with patch('emby_mcp.functions.get_playlists', return_value=existing):
            result = set_playlist_meta(MagicMock(), "user_123", LIBRARIES, "pl_1", name="Taken")

        assert result["success"] == False
        assert "already exists" in result["error"]

    def test_keeping_your_own_name_is_allowed(self, emby):
        """Renaming a playlist to the name it already has must not trip the duplicate check."""
        existing = {"success": True, "playlists": [{"name": "Mine", "playlist_id": "pl_1"}]}
        with patch('emby_mcp.functions.get_playlists', return_value=existing):
            result = set_playlist_meta(MagicMock(), "user_123", LIBRARIES, "pl_1", name="Mine", overview="notes")

        assert result["success"] == True

    def test_missing_playlist_is_reported(self, emby):
        _, userlib_api, _ = emby
        userlib_api.get_users_by_userid_items_by_id.return_value = None

        result = set_playlist_meta(MagicMock(), "user_123", LIBRARIES, "pl_1", overview="notes")

        assert result["success"] == False
        assert "not found" in result["error"]

    def test_lookup_failure_is_reported(self, emby):
        _, userlib_api, _ = emby
        userlib_api.get_users_by_userid_items_by_id.side_effect = ApiException(status=404)

        result = set_playlist_meta(MagicMock(), "user_123", LIBRARIES, "pl_1", overview="notes")

        assert result["success"] == False

    def test_update_failure_is_reported(self, emby):
        _, _, update_api = emby
        update_api.post_items_by_itemid.side_effect = ApiException(status=500)

        result = set_playlist_meta(MagicMock(), "user_123", LIBRARIES, "pl_1", overview="notes")

        assert result["success"] == False


class TestPlaylistContents:
    """Tests for adding, removing and reordering playlist items."""

    @pytest.fixture
    def playlist_api(self):
        with patch('emby_mcp.functions.emby_client.PlaylistServiceApi') as mock_api:
            yield mock_api.return_value

    def test_adding_nothing_is_reported(self, playlist_api):
        playlist_api.post_playlists_by_id_items.return_value.item_added_count = 0

        result = add_playlist_items(MagicMock(), "user_123", "pl_1", "item1")

        assert result["success"] == False
        assert "Failed to add" in result["error"]

    def test_add_api_error_is_reported(self, playlist_api):
        playlist_api.post_playlists_by_id_items.side_effect = ApiException(status=500)

        result = add_playlist_items(MagicMock(), "user_123", "pl_1", "item1")

        assert result["success"] == False

    def test_items_are_removed(self, playlist_api):
        result = delete_playlist_items(MagicMock(), "pl_1", "3,4")

        assert result == {"success": True}
        playlist_api.post_playlists_by_id_items_delete.assert_called_once_with("pl_1", "3,4")

    def test_remove_api_error_is_reported(self, playlist_api):
        playlist_api.post_playlists_by_id_items_delete.side_effect = ApiException(status=500)

        result = delete_playlist_items(MagicMock(), "pl_1", "3")

        assert result["success"] == False

    def test_an_item_is_moved(self, playlist_api):
        result = move_playlist_items(MagicMock(), "pl_1", "3", "0")

        assert result == {"success": True}
        playlist_api.post_playlists_by_id_items_by_itemid_move_by_newindex.assert_called_once_with("3", "pl_1", "0")

    def test_move_api_error_is_reported(self, playlist_api):
        playlist_api.post_playlists_by_id_items_by_itemid_move_by_newindex.side_effect = ApiException(status=500)

        result = move_playlist_items(MagicMock(), "pl_1", "3", "0")

        assert result["success"] == False
