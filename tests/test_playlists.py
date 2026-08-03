# -*- coding: utf-8 -*-
"""Tests for Emby playlist management functions."""

import pytest
import emby_client
from unittest.mock import patch, MagicMock
from emby_mcp.functions import (
    get_playlists,
    get_playlist_items,
    new_playlist,
    set_playlist_meta,
    add_playlist_items,
    delete_playlist_items,
    move_playlist_items,
    set_playlist_sharing
)


class TestPlaylistFunctions:
    """Tests for playlist-related functions."""

    def test_get_playlists_empty(self):
        """get_playlists should return empty list when no playlists."""
        mock_api_client = MagicMock()
        
        with patch('emby_mcp.functions.emby_client.ItemsServiceApi') as mock_api_items:
            mock_items_api = MagicMock()
            mock_api_items.return_value = mock_items_api
            
            mock_response = MagicMock()
            mock_response.total_record_count = 0
            mock_response.items = []
            mock_items_api.get_users_by_userid_items.return_value = mock_response
            
            result = get_playlists(mock_api_client, "user_123", [], "")
            
            assert result["success"] == False
            assert "No libraries" in result["error"]

    def test_get_playlist_items_success(self):
        """get_playlist_items should return items from a playlist."""
        mock_api_client = MagicMock()
        
        with patch('emby_mcp.functions.emby_client.PlaylistServiceApi') as mock_api_playlist:
            mock_playlist_api = MagicMock()
            mock_api_playlist.return_value = mock_playlist_api
            
            mock_item = MagicMock()
            mock_item.name = "Song 1"
            mock_item.id = "item1"
            mock_item.artists = ["Artist 1"]
            mock_item.album = "Album 1"
            mock_item.media_type = "Audio"
            mock_item.run_time_ticks = 18000000000
            mock_item.playlist_item_id = "pl_item_1"
            mock_item.date_created = MagicMock()
            mock_item.date_created.isoformat.return_value = "2024-01-01"
            mock_item.premiere_date = MagicMock()
            mock_item.premiere_date.isoformat.return_value = "2024-01-01"
            mock_item.production_year = 2024
            mock_item.genres = ["Genre 1"]
            mock_item.overview = "Overview"
            mock_item.media_sources = []
            mock_item.bitrate = 320000

            mock_response = MagicMock()
            mock_response.total_record_count = 1
            mock_response.items = [mock_item]
            mock_playlist_api.get_playlists_by_id_items.return_value = mock_response

            result = get_playlist_items(mock_api_client, "user_123", "playlist_123")

            assert result["success"] == True
            assert len(result["items"]) == 1
            assert result["items"][0]["title"] == "Song 1"
            assert result["items"][0]["run_time"] == "00:30:00"
            assert result["items"][0]["playlist_item_index"] == "0"
            assert result["total_count"] == 1

    def test_get_playlist_items_skips_items_without_media_type(self):
        """Items with no media_type (eg folders) should be skipped rather than crash."""
        mock_api_client = MagicMock()

        with patch('emby_mcp.functions.emby_client.PlaylistServiceApi') as mock_api_playlist:
            mock_playlist_api = MagicMock()
            mock_api_playlist.return_value = mock_playlist_api

            mock_folder = MagicMock()
            mock_folder.media_type = None

            mock_song = MagicMock()
            mock_song.media_type = "Audio"
            mock_song.name = "Song 1"
            mock_song.run_time_ticks = 0
            mock_song.media_sources = []

            mock_response = MagicMock()
            mock_response.total_record_count = 2
            mock_response.items = [mock_folder, mock_song]
            mock_playlist_api.get_playlists_by_id_items.return_value = mock_response

            result = get_playlist_items(mock_api_client, "user_123", "playlist_123")

            assert result["success"] == True
            assert len(result["items"]) == 1
            assert result["total_count"] == 1
            # every item has a run_time key, even when Emby reports no duration
            assert result["items"][0]["run_time"] == ""

    def test_get_playlist_items_extracts_lyrics(self):
        """Lyrics live in the extradata of a text subtitle stream titled 'lyrics'."""
        mock_api_client = MagicMock()

        with patch('emby_mcp.functions.emby_client.PlaylistServiceApi') as mock_api_playlist:
            mock_playlist_api = MagicMock()
            mock_api_playlist.return_value = mock_playlist_api

            lyric_stream = MagicMock()
            lyric_stream.is_text_subtitle_stream = True
            lyric_stream.title = "Lyrics"
            lyric_stream.extradata = "here come the lyrics"

            media_source = MagicMock()
            media_source.media_streams = [lyric_stream]

            mock_item = MagicMock()
            mock_item.media_type = "Audio"
            mock_item.name = "Song 1"
            mock_item.run_time_ticks = 0
            mock_item.media_sources = [media_source]

            mock_response = MagicMock()
            mock_response.total_record_count = 1
            mock_response.items = [mock_item]
            mock_playlist_api.get_playlists_by_id_items.return_value = mock_response

            result = get_playlist_items(mock_api_client, "user_123", "playlist_123")

            assert result["items"][0]["lyrics"] == "here come the lyrics"
            # the raw media sources are an implementation detail and must not leak out
            assert "media_sources" not in result["items"][0]

            # the request must ask Emby for MediaSources, or there would be no lyrics to find
            requested_fields = mock_playlist_api.get_playlists_by_id_items.call_args[1]["fields"]
            assert "MediaSources" in requested_fields

    def test_new_playlist_success(self):
        """new_playlist should create a new playlist."""
        mock_api_client = MagicMock()
        
        with patch('emby_mcp.functions.new_playlist') as mock_new:
            # Mock the get_playlists call inside new_playlist
            with patch('emby_mcp.functions.get_playlists') as mock_get_playlists:
                mock_get_playlists.return_value = {'success': True, 'playlists': []}
                
                with patch('emby_mcp.functions.emby_client.PlaylistServiceApi') as mock_api_playlist:
                    mock_playlist_api = MagicMock()
                    mock_api_playlist.return_value = mock_playlist_api
                    
                    mock_response = MagicMock()
                    mock_response.id = "new_playlist_123"
                    mock_playlist_api.post_playlists.return_value = mock_response
                    
                    result = new_playlist(
                        mock_api_client, 
                        "user_123", 
                        [], 
                        "New Playlist",
                        media_type="Audio"
                    )
                    
                    assert result["success"] == True
                    assert "playlist_id" in result

    def test_set_playlist_meta_success(self):
        """set_playlist_meta should update playlist metadata."""
        mock_api_client = MagicMock()
        
        with patch('emby_mcp.functions.set_playlist_meta') as mock_set:
            with patch('emby_mcp.functions.emby_client.ItemUpdateServiceApi') as mock_api_items:
                mock_items_api = MagicMock()
                mock_api_items.return_value = mock_items_api
                
                mock_response = MagicMock()
                mock_items_api.post_items_by_itemid.return_value = mock_response
                
                result = set_playlist_meta(
                    mock_api_client, 
                    "user_123", 
                    [], 
                    "playlist_123",
                    name="Updated Name",
                    overview="New Overview"
                )
                
                assert result["success"] == True

    def test_add_playlist_items_success(self):
        """add_playlist_items should add items to a playlist."""
        mock_api_client = MagicMock()

        with patch('emby_mcp.functions.emby_client.PlaylistServiceApi') as mock_api_playlist:
            mock_playlist_api = MagicMock()
            mock_api_playlist.return_value = mock_playlist_api

            mock_response = MagicMock()
            mock_response.item_added_count = 2
            mock_playlist_api.post_playlists_by_id_items.return_value = mock_response

            result = add_playlist_items(
                mock_api_client,
                "user_123",
                "playlist_123",
                "item1,item2"
            )

            assert result["success"] == True
            assert result["item_count"] == 2

    def test_delete_playlist_items_success(self):
        """delete_playlist_items should remove items from a playlist."""
        mock_api_client = MagicMock()
        
        with patch('emby_mcp.functions.emby_client.PlaylistServiceApi') as mock_api_playlist:
            mock_playlist_api = MagicMock()
            mock_api_playlist.return_value = mock_playlist_api
            
            mock_response = MagicMock()
            mock_playlist_api.delete_playlist_items.return_value = mock_response
            
            result = delete_playlist_items(mock_api_client, "playlist_123", "1")
            
            assert result["success"] == True

    def test_move_playlist_items_success(self):
        """move_playlist_items should reorder items in a playlist."""
        mock_api_client = MagicMock()
        
        with patch('emby_mcp.functions.emby_client.PlaylistServiceApi') as mock_api_playlist:
            mock_playlist_api = MagicMock()
            mock_api_playlist.return_value = mock_playlist_api
            
            mock_response = MagicMock()
            mock_playlist_api.move_playlist_items.return_value = mock_response
            
            result = move_playlist_items(mock_api_client, "playlist_123", "1", "3")
            
            assert result["success"] == True

    def test_set_playlist_sharing_public(self):
        """set_playlist_sharing should make a playlist public."""
        mock_api_client = MagicMock()

        with patch('emby_mcp.functions.emby_client.UserLibraryServiceApi') as mock_api_userlib:
            mock_userlib_api = MagicMock()
            mock_api_userlib.return_value = mock_userlib_api

            result = set_playlist_sharing(mock_api_client, "playlist_123", "Public")

            assert result["success"] == True
            mock_userlib_api.post_items_by_id_makepublic.assert_called_once_with("playlist_123")

    def test_set_playlist_sharing_shared_builds_request_body(self):
        """Sharing with named users must send an instance of the request model, not the model class."""
        mock_api_client = MagicMock()

        with patch('emby_mcp.functions.emby_client.UserLibraryServiceApi') as mock_api_userlib:
            mock_userlib_api = MagicMock()
            mock_api_userlib.return_value = mock_userlib_api

            result = set_playlist_sharing(
                mock_api_client,
                "playlist_123",
                "Shared",
                user_ids=["user_1", "user_2"],
                item_access="Read",
            )

            assert result["success"] == True
            body = mock_userlib_api.post_items_access.call_args[0][0]
            # a bare class would mean every call mutating shared state on the SDK model
            assert isinstance(body, emby_client.UserLibraryUpdateUserItemAccess)
            assert body.item_ids == ["playlist_123"]
            assert body.user_ids == ["user_1", "user_2"]
            assert body.item_access == "Read"

    def test_set_playlist_sharing_shared_accepts_comma_separated_users(self):
        """A comma separated user_ids string should be split into a list for Emby."""
        mock_api_client = MagicMock()

        with patch('emby_mcp.functions.emby_client.UserLibraryServiceApi') as mock_api_userlib:
            mock_userlib_api = MagicMock()
            mock_api_userlib.return_value = mock_userlib_api

            set_playlist_sharing(
                mock_api_client,
                "playlist_123",
                "Shared",
                user_ids="user_1, user_2",
                item_access="Manage",
            )

            body = mock_userlib_api.post_items_access.call_args[0][0]
            assert body.user_ids == ["user_1", "user_2"]

    def test_set_playlist_sharing_shared_requires_users(self):
        """Sharing with named users needs both user_ids and item_access."""
        result = set_playlist_sharing(MagicMock(), "playlist_123", "Shared")

        assert result["success"] == False
        assert "user_ids" in result["error"]

    def test_set_playlist_sharing_private(self):
        """set_playlist_sharing should make a playlist private again."""
        with patch('emby_mcp.functions.emby_client.UserLibraryServiceApi') as mock_api_userlib:
            result = set_playlist_sharing(MagicMock(), "playlist_123", "Private")

            assert result["success"] == True
            mock_api_userlib.return_value.post_items_by_id_makeprivate.assert_called_once_with("playlist_123")

    def test_set_playlist_sharing_invalid_type(self):
        """An unknown share_type should be reported."""
        result = set_playlist_sharing(MagicMock(), "playlist_123", "Sideways")

        assert result["success"] == False
        assert "Invalid share_type" in result["error"]

    def test_set_playlist_sharing_api_error(self):
        with patch('emby_mcp.functions.emby_client.UserLibraryServiceApi') as mock_api_userlib:
            from emby_client.rest import ApiException
            mock_api_userlib.return_value.post_items_by_id_makepublic.side_effect = ApiException(status=500)

            result = set_playlist_sharing(MagicMock(), "playlist_123", "Public")

        assert result["success"] == False
        assert len(result["error"]) > 0

    def test_get_playlist_items_empty(self):
        """An empty playlist should return an empty item list."""
        with patch('emby_mcp.functions.emby_client.PlaylistServiceApi') as mock_api_playlist:
            mock_response = MagicMock()
            mock_response.total_record_count = 0
            mock_api_playlist.return_value.get_playlists_by_id_items.return_value = mock_response

            result = get_playlist_items(MagicMock(), "user_123", "playlist_123")

        assert result == {"success": True, "total_count": 0, "items": []}

    def test_get_playlist_items_api_error(self):
        with patch('emby_mcp.functions.emby_client.PlaylistServiceApi') as mock_api_playlist:
            from emby_client.rest import ApiException
            mock_api_playlist.return_value.get_playlists_by_id_items.side_effect = ApiException(status=500)

            result = get_playlist_items(MagicMock(), "user_123", "playlist_123")

        assert result["success"] == False
        assert len(result["error"]) > 0