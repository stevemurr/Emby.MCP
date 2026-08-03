# -*- coding: utf-8 -*-
"""Tests for the playlist MCP tools exposed to the AI client."""

import json
import pytest
from unittest.mock import patch, MagicMock

from emby_mcp import server as emby_server
from emby_mcp.server import (
    add_items_to_playlist,
    create_playlist,
    modify_playlist_name,
    remove_items_from_playlist,
    reorder_items_on_playlist,
    retrieve_playlist_items,
    retrieve_playlist_list,
    share_playlist_public,
    share_playlist_user_access,
    stop_sharing_playlist,
)


class TestCreatePlaylist:
    """Tests for creating a playlist."""

    def test_playlist_is_created(self, selected_library):
        with patch('emby_mcp.server.new_playlist',
                   return_value={'success': True, 'playlist_id': 'pl_1'}) as create:
            result = json.loads(create_playlist("Road Trip", description="For the car"))

        assert result['playlist_id'] == 'pl_1'
        assert create.call_args[1] == {'media_type': 'Audio', 'overview': 'For the car'}

    def test_blank_description_is_omitted(self, selected_library):
        with patch('emby_mcp.server.new_playlist',
                   return_value={'success': True, 'playlist_id': 'pl_1'}) as create:
            create_playlist("Road Trip", description="")

        assert 'overview' not in create.call_args[1]

    def test_items_are_added_when_supplied(self, selected_library):
        with patch('emby_mcp.server.new_playlist', return_value={'success': True, 'playlist_id': 'pl_1'}), \
             patch('emby_mcp.server.add_playlist_items',
                   return_value={'success': True, 'item_count': 2}) as add:
            result = json.loads(create_playlist("Road Trip", item_ids="id_1,id_2"))

        assert result['playlist_id'] == 'pl_1'
        assert add.call_args[0][2:] == ('pl_1', 'id_1,id_2')

    def test_a_created_playlist_is_reported_even_if_adding_items_fails(self, selected_library):
        """
        The playlist really does exist at this point, so the ID must still reach the
        client or the playlist is orphaned with no way to refer to it.
        """
        with patch('emby_mcp.server.new_playlist', return_value={'success': True, 'playlist_id': 'pl_1'}), \
             patch('emby_mcp.server.add_playlist_items',
                   return_value={'success': False, 'error': 'unknown item'}):
            result = create_playlist("Road Trip", item_ids="id_bad")

        assert 'pl_1' in result
        assert 'unknown item' in result

    def test_creation_failure_is_reported(self, selected_library):
        with patch('emby_mcp.server.new_playlist',
                   return_value={'success': False, 'error': 'name already used'}):
            result = create_playlist("Road Trip")

        assert result.startswith("ERROR")
        assert 'name already used' in result

    def test_library_list_is_fetched_when_not_already_cached(self, mcp_context):
        library = {'name': 'Music', 'id': 'lib_1', 'type': 'music'}

        with patch('emby_mcp.server.get_library_list',
                   return_value={'success': True, 'items': [library]}) as fetch, \
             patch('emby_mcp.server.new_playlist', return_value={'success': True, 'playlist_id': 'pl_1'}):
            result = json.loads(create_playlist("Road Trip"))

        fetch.assert_called_once()
        assert result['playlist_id'] == 'pl_1'

    def test_server_with_no_libraries_is_reported(self, mcp_context):
        with patch('emby_mcp.server.get_library_list', return_value={'success': True, 'items': []}):
            result = create_playlist("Road Trip")

        assert result.startswith("ERROR")
        assert "retrieve_library_list" in result


class TestModifyPlaylistName:
    """Tests for renaming and re-describing a playlist."""

    def test_name_and_description_are_passed_through(self, selected_library):
        with patch('emby_mcp.server.set_playlist_meta', return_value={'success': True}) as modify:
            result = modify_playlist_name("pl_1", new_name="New Name", new_description="New words")

        assert "successfully modified" in result
        assert modify.call_args[1] == {'name': 'New Name', 'overview': 'New words'}

    def test_blank_fields_are_left_unchanged(self, selected_library):
        """An empty string means "no change", so it must not blank the stored value."""
        with patch('emby_mcp.server.set_playlist_meta', return_value={'success': True}) as modify:
            modify_playlist_name("pl_1", new_name="New Name", new_description="")

        assert modify.call_args[1] == {'name': 'New Name'}

    def test_failure_is_reported(self, selected_library):
        with patch('emby_mcp.server.set_playlist_meta',
                   return_value={'success': False, 'error': 'no such playlist'}):
            result = modify_playlist_name("pl_1", new_name="New Name")

        assert result.startswith("ERROR")
        assert 'no such playlist' in result

    def test_server_with_no_libraries_is_reported(self, mcp_context):
        with patch('emby_mcp.server.get_library_list', return_value={'success': True, 'items': []}):
            result = modify_playlist_name("pl_1", new_name="New Name")

        assert result.startswith("ERROR")


class TestRetrievePlaylistList:
    """Tests for listing playlists."""

    def test_playlists_are_returned(self, selected_library):
        playlists = [{'name': 'Road Trip', 'playlist_id': 'pl_1', 'user_access': []}]
        with patch('emby_mcp.server.get_playlists', return_value={'success': True, 'playlists': playlists}):
            assert json.loads(retrieve_playlist_list()) == playlists

    def test_embys_access_name_is_replaced_with_the_friendly_one(self, selected_library):
        """
        share_playlist_user_access documents 'Full Control', so listing must report the
        same word rather than Emby's internal 'ManageDelete'.
        """
        playlists = [{
            'name': 'Road Trip',
            'playlist_id': 'pl_1',
            'user_access': [
                {'user_name': 'Alice', 'user_id': 'u1', 'access_level': 'ManageDelete'},
                {'user_name': 'Bob', 'user_id': 'u2', 'access_level': 'Read'},
            ],
        }]
        with patch('emby_mcp.server.get_playlists', return_value={'success': True, 'playlists': playlists}):
            result = json.loads(retrieve_playlist_list())

        levels = [user['access_level'] for user in result[0]['user_access']]
        assert levels == ['Full Control', 'Read']

    def test_a_single_playlist_can_be_requested(self, selected_library):
        with patch('emby_mcp.server.get_playlists',
                   return_value={'success': True, 'playlists': []}) as get:
            retrieve_playlist_list("pl_1")

        assert get.call_args[0][3] == 'pl_1'

    def test_failure_is_reported(self, selected_library):
        with patch('emby_mcp.server.get_playlists',
                   return_value={'success': False, 'error': 'access denied'}):
            result = retrieve_playlist_list()

        assert result.startswith("ERROR")
        assert 'access denied' in result

    def test_server_with_no_libraries_is_reported(self, mcp_context):
        with patch('emby_mcp.server.get_library_list', return_value={'success': True, 'items': []}):
            result = retrieve_playlist_list()

        assert result.startswith("ERROR")


class TestPlaylistItems:
    """Tests for reading and changing the items on a playlist."""

    def test_items_are_returned(self, mcp_context):
        items = [{'title': 'Track 1', 'item_id': 'id_1', 'playlist_item_number': 'pi_1'}]
        with patch('emby_mcp.server.get_playlist_items', return_value={'success': True, 'items': items}):
            assert json.loads(retrieve_playlist_items("pl_1")) == items

    def test_read_failure_is_reported(self, mcp_context):
        with patch('emby_mcp.server.get_playlist_items',
                   return_value={'success': False, 'error': 'no such playlist'}):
            result = retrieve_playlist_items("pl_1")

        assert result.startswith("ERROR")
        assert 'pl_1' in result

    def test_added_item_count_is_reported(self, mcp_context):
        with patch('emby_mcp.server.add_playlist_items',
                   return_value={'success': True, 'item_count': 3}) as add:
            result = add_items_to_playlist("pl_1", "id_1,id_2,id_3")

        assert "3 items" in result
        assert add.call_args[0][2:] == ('pl_1', 'id_1,id_2,id_3')

    def test_add_failure_is_reported(self, mcp_context):
        with patch('emby_mcp.server.add_playlist_items',
                   return_value={'success': False, 'error': 'wrong media type'}):
            result = add_items_to_playlist("pl_1", "id_1")

        assert result.startswith("ERROR")
        assert 'wrong media type' in result

    def test_items_are_removed(self, mcp_context):
        with patch('emby_mcp.server.delete_playlist_items', return_value={'success': True}) as delete:
            result = remove_items_from_playlist("pl_1", "pi_1,pi_2")

        assert "Successfully removed" in result
        assert delete.call_args[0][1:] == ('pl_1', 'pi_1,pi_2')

    def test_remove_failure_is_reported(self, mcp_context):
        with patch('emby_mcp.server.delete_playlist_items',
                   return_value={'success': False, 'error': 'not on this playlist'}):
            result = remove_items_from_playlist("pl_1", "pi_9")

        assert result.startswith("ERROR")
        assert 'not on this playlist' in result

    def test_items_are_reordered(self, mcp_context):
        with patch('emby_mcp.server.move_playlist_items', return_value={'success': True}) as move:
            result = reorder_items_on_playlist("pl_1", "pi_1", "0")

        assert "Successfully reordered" in result
        assert move.call_args[0][1:] == ('pl_1', 'pi_1', '0')

    def test_reorder_failure_is_reported(self, mcp_context):
        with patch('emby_mcp.server.move_playlist_items',
                   return_value={'success': False, 'error': 'index out of range'}):
            result = reorder_items_on_playlist("pl_1", "pi_1", "99")

        assert result.startswith("ERROR")
        assert 'index out of range' in result


class TestPlaylistSharing:
    """Tests for the playlist sharing tools."""

    def test_playlist_is_shared_publicly(self, mcp_context):
        with patch('emby_mcp.server.set_playlist_sharing', return_value={'success': True}) as share:
            result = share_playlist_public("pl_1")

        assert "Successfully shared" in result
        assert share.call_args[0][1:] == ('pl_1', 'Public')

    def test_public_share_failure_is_reported(self, mcp_context):
        with patch('emby_mcp.server.set_playlist_sharing',
                   return_value={'success': False, 'error': 'not permitted'}):
            result = share_playlist_public("pl_1")

        assert result.startswith("ERROR")
        assert 'not permitted' in result

    def test_sharing_is_stopped(self, mcp_context):
        with patch('emby_mcp.server.set_playlist_sharing', return_value={'success': True}) as share:
            result = stop_sharing_playlist("pl_1")

        assert "Successfully stopped sharing" in result
        assert share.call_args[0][1:] == ('pl_1', 'Private')

    def test_stop_sharing_failure_is_reported(self, mcp_context):
        with patch('emby_mcp.server.set_playlist_sharing',
                   return_value={'success': False, 'error': 'not permitted'}):
            result = stop_sharing_playlist("pl_1")

        assert result.startswith("ERROR")

    def test_unknown_access_level_is_rejected(self, mcp_context):
        """An unknown level must be refused rather than sent on to Emby."""
        with patch('emby_mcp.server.set_playlist_sharing') as share:
            result = share_playlist_user_access("pl_1", "u1", "Admin")

        assert result.startswith("ERROR")
        assert 'Admin' in result
        share.assert_not_called()

    def test_friendly_access_level_is_translated_for_emby(self, mcp_context):
        with patch('emby_mcp.server.set_playlist_sharing', return_value={'success': True}) as share:
            share_playlist_user_access("pl_1", "u1", "Full Control")

        assert share.call_args[1]['item_access'] == 'ManageDelete'

    @pytest.mark.parametrize("access_level", ['None', 'Read', 'Write', 'Manage', 'ManageDelete'])
    def test_accepted_access_levels_are_passed_through(self, mcp_context, access_level):
        with patch('emby_mcp.server.set_playlist_sharing', return_value={'success': True}) as share:
            share_playlist_user_access("pl_1", "u1", access_level)

        assert share.call_args[1]['item_access'] == access_level

    def test_user_share_failure_is_reported(self, mcp_context):
        with patch('emby_mcp.server.set_playlist_sharing',
                   return_value={'success': False, 'error': 'unknown user'}):
            result = share_playlist_user_access("pl_1", "u1", "Read")

        assert result.startswith("ERROR")
        assert 'unknown user' in result

    def test_spaced_user_ids_reach_emby_trimmed(self, mcp_context):
        """
        An AI client naturally writes "u1, u2". set_playlist_sharing only trims when it is
        given the raw string, so a pre-split list would send Emby a user ID of " u2".
        """
        with patch('emby_mcp.functions.emby_client.UserLibraryServiceApi') as mock_api, \
             patch('emby_mcp.functions.emby_client.UserLibraryUpdateUserItemAccess') as mock_body:
            mock_api.return_value = MagicMock()

            result = share_playlist_user_access("pl_1", "u1, u2", "Read")

        assert "Successfully shared" in result
        assert mock_body.call_args[1]['user_ids'] == ['u1', 'u2']

    def test_empty_user_ids_are_rejected_rather_than_sent_as_a_blank_user(self, mcp_context):
        """
        "".split(",") is [""], a non-empty list holding one empty ID, which slips past the
        "no users supplied" check and grants access to a user that does not exist.
        """
        with patch('emby_mcp.functions.emby_client.UserLibraryServiceApi') as mock_api, \
             patch('emby_mcp.functions.emby_client.UserLibraryUpdateUserItemAccess') as mock_body:
            mock_api.return_value = MagicMock()

            result = share_playlist_user_access("pl_1", "", "Read")

        assert result.startswith("ERROR")
        mock_body.assert_not_called()
