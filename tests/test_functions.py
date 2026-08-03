# -*- coding: utf-8 -*-
"""Tests for Emby library and item functions."""

import pytest
from unittest.mock import patch, MagicMock
from emby_mcp.functions import (
    get_library_list,
    get_genre_list,
    get_items,
    set_current_library
)


class TestLibraryFunctions:
    """Tests for library-related functions."""

    def test_get_library_list_success(self):
        """get_library_list should return list of libraries on success."""
        mock_api_client = MagicMock()
        
        with patch('emby_mcp.functions.emby_client.LibraryServiceApi') as mock_api_lib:
            mock_library_api = MagicMock()
            mock_api_lib.return_value = mock_library_api
            
            mock_library = MagicMock()
            mock_library.name = "Movies"
            mock_library.id = "123"
            mock_library.collection_type = "movies"
            mock_library.type = "CollectionFolder"
            
            mock_response = MagicMock()
            mock_response.total_record_count = 1
            mock_response.items = [mock_library]
            mock_library_api.get_library_mediafolders.return_value = mock_response
            
            result = get_library_list(mock_api_client)
            
            assert result["success"] == True
            assert len(result["items"]) == 1
            assert result["items"][0]["name"] == "Movies"
            assert result["items"][0]["type"] == "movies"

    def test_get_library_list_empty(self):
        """get_library_list should handle empty results."""
        mock_api_client = MagicMock()
        
        with patch('emby_mcp.functions.emby_client.LibraryServiceApi') as mock_api_lib:
            mock_library_api = MagicMock()
            mock_api_lib.return_value = mock_library_api
            
            mock_response = MagicMock()
            mock_response.total_record_count = 0
            mock_response.items = []
            mock_library_api.get_library_mediafolders.return_value = mock_response
            
            result = get_library_list(mock_api_client)
            
            assert result["success"] == True
            assert len(result["items"]) == 0

    def test_get_library_list_api_error(self):
        """get_library_list should handle API errors gracefully."""
        mock_api_client = MagicMock()
        
        with patch('emby_mcp.functions.emby_client.LibraryServiceApi') as mock_api_lib:
            mock_library_api = MagicMock()
            mock_api_lib.return_value = mock_library_api
            
            from emby_client.rest import ApiException
            mock_library_api.get_library_mediafolders.side_effect = ApiException(status=500)
            
            result = get_library_list(mock_api_client)
            
            assert result["success"] == False
            assert "error" in result
            assert len(result["error"]) > 0

    def test_get_genre_list_root(self):
        """get_genre_list should return root genres when no library_id."""
        mock_api_client = MagicMock()
        
        with patch('emby_mcp.functions.emby_client.GenresServiceApi') as mock_api_genres:
            mock_genres_api = MagicMock()
            mock_api_genres.return_value = mock_genres_api
            
            mock_genre1 = MagicMock()
            mock_genre1.name = "Action"
            mock_genre2 = MagicMock()
            mock_genre2.name = "Comedy"
            
            mock_response = MagicMock()
            mock_response.items = [mock_genre1, mock_genre2]
            mock_genres_api.get_genres.return_value = mock_response
            
            result = get_genre_list(mock_api_client)
            
            assert result["success"] == True
            assert len(result["genres"]) == 2
            assert "Action" in result["genres"]
            assert "Comedy" in result["genres"]

    def test_get_genre_list_with_library(self):
        """get_genre_list should filter by library when library_id provided."""
        mock_api_client = MagicMock()

        with patch('emby_mcp.functions.emby_client.GenresServiceApi') as mock_api_genres:
            mock_genres_api = MagicMock()
            mock_api_genres.return_value = mock_genres_api

            mock_genre = MagicMock()
            mock_genre.name = "Drama"

            mock_response = MagicMock()
            mock_response.items = [mock_genre]
            mock_genres_api.get_genres.return_value = mock_response

            result = get_genre_list(mock_api_client, library_id="lib_123")

            assert result["success"] == True
            assert "Drama" in result["genres"]
            assert mock_genres_api.get_genres.call_args[1]["parent_id"] == "lib_123"

    def test_get_genre_list_api_error(self):
        """get_genre_list should handle API errors gracefully."""
        with patch('emby_mcp.functions.emby_client.GenresServiceApi') as mock_api_genres:
            from emby_client.rest import ApiException
            mock_api_genres.return_value.get_genres.side_effect = ApiException(status=500)

            result = get_genre_list(MagicMock())

        assert result["success"] == False
        assert len(result["error"]) > 0

    def test_get_library_list_excludes_non_collection_folders(self):
        """Only CollectionFolder items are real libraries."""
        with patch('emby_mcp.functions.emby_client.LibraryServiceApi') as mock_api_lib:
            folder = MagicMock()
            folder.type = "Folder"
            library = MagicMock()
            library.type = "CollectionFolder"
            library.name = "Music"
            library.id = "lib_1"
            library.collection_type = "music"

            mock_response = MagicMock()
            mock_response.total_record_count = 2
            mock_response.items = [folder, library]
            mock_api_lib.return_value.get_library_mediafolders.return_value = mock_response

            result = get_library_list(MagicMock())

        assert result["items"] == [{"name": "Music", "type": "music", "id": "lib_1"}]

    @pytest.mark.parametrize("libraries", [[], None])
    def test_set_current_library_without_libraries(self, libraries):
        """Selecting a library before any have been retrieved should be reported."""
        result = set_current_library(libraries, name="Music")

        assert result["success"] == False
        assert "No libraries are available" in result["error"]

    def test_set_current_library_success(self):
        """set_current_library should find and return library by name."""
        libraries = [
            {"name": "Movies", "id": "123", "type": "movies"},
            {"name": "Music", "id": "456", "type": "music"}
        ]
        
        result = set_current_library(libraries, name="Movies")
        
        assert result["success"] == True
        assert result["library"]["name"] == "Movies"

    def test_set_current_library_not_found(self):
        """set_current_library should return error when library not found."""
        libraries = [
            {"name": "Movies", "id": "123", "type": "movies"},
        ]
        
        result = set_current_library(libraries, name="NonExistent")
        
        assert result["success"] == False
        assert "not found" in result["error"]

    def test_set_current_library_no_name(self):
        """set_current_library should return error when no name provided."""
        result = set_current_library([], name="")

        assert result["success"] == False
        assert "No library name" in result["error"]


def make_item(**overrides):
    """Build a mock Emby item with sensible defaults, overriding the named attributes."""
    item = MagicMock()
    item.name = overrides.get("name", "Track")
    item.artists = overrides.get("artists", [])
    item.genres = overrides.get("genres", [])
    item.overview = overrides.get("overview", "")
    item.media_sources = overrides.get("media_sources", [])
    item.run_time_ticks = overrides.get("run_time_ticks", 0)
    item.media_type = overrides.get("media_type", "Audio")
    return item


def patched_items_api(items):
    """Patch ItemsServiceApi so that get_users_by_userid_items returns the given items."""
    patcher = patch('emby_mcp.functions.emby_client.ItemsServiceApi')
    mock_api = patcher.start()
    mock_items_api = MagicMock()
    mock_api.return_value = mock_items_api

    mock_response = MagicMock()
    mock_response.total_record_count = len(items)
    mock_response.items = items
    mock_items_api.get_users_by_userid_items.return_value = mock_response
    return patcher, mock_items_api


class TestGetItems:
    """Tests for the item search function."""

    def test_date_filters_use_emby_parameter_names(self):
        """first_date / last_date must map to parameters the SDK actually accepts."""
        patcher, mock_items_api = patched_items_api([])
        try:
            result = get_items(
                MagicMock(), "user_123",
                first_date="2024-01-01", last_date="2024-12-31",
            )
        finally:
            patcher.stop()

        assert result["success"] == True
        called_kwargs = mock_items_api.get_users_by_userid_items.call_args[1]
        assert called_kwargs["min_start_date"] == "2024-01-01"
        assert called_kwargs["max_end_date"] == "2024-12-31"

    def test_false_flags_do_not_apply_filters(self):
        """Passing is_played=False must not ask Emby for played items."""
        patcher, mock_items_api = patched_items_api([])
        try:
            get_items(MagicMock(), "user_123", is_played=False, is_unplayed=False, is_favorite=False)
        finally:
            patcher.stop()

        assert "filters" not in mock_items_api.get_users_by_userid_items.call_args[1]

    def test_true_flags_are_combined(self):
        """Several true flags should be combined into one comma separated filter."""
        patcher, mock_items_api = patched_items_api([])
        try:
            get_items(MagicMock(), "user_123", is_played=True, is_favorite=True)
        finally:
            patcher.stop()

        assert mock_items_api.get_users_by_userid_items.call_args[1]["filters"] == "IsPlayed,IsFavorite"

    def test_lyrics_are_extracted_and_media_sources_removed(self):
        """Lyrics come from a text subtitle stream, and the raw media sources must not leak out."""
        lyric_stream = MagicMock()
        lyric_stream.is_text_subtitle_stream = True
        lyric_stream.title = "Lyrics"
        lyric_stream.extradata = "the words"

        other_stream = MagicMock()
        other_stream.is_text_subtitle_stream = False
        other_stream.title = "Audio"

        source = MagicMock()
        source.media_streams = [other_stream, lyric_stream]

        patcher, _ = patched_items_api([make_item(media_sources=[source], run_time_ticks=18000000000)])
        try:
            result = get_items(MagicMock(), "user_123")
        finally:
            patcher.stop()

        assert result["items"][0]["lyrics"] == "the words"
        assert result["items"][0]["run_time"] == "00:30:00"
        assert "media_sources" not in result["items"][0]
        assert "run_time_ticks" not in result["items"][0]

    def test_item_without_lyrics_still_drops_media_sources(self):
        """An item whose media sources hold no lyrics must still return a clean dictionary."""
        source = MagicMock()
        source.media_streams = []

        patcher, _ = patched_items_api([make_item(media_sources=[source])])
        try:
            result = get_items(MagicMock(), "user_123")
        finally:
            patcher.stop()

        assert result["items"][0]["lyrics"] == ""
        assert "media_sources" not in result["items"][0]

    def test_lyric_search_filters_items_and_count(self):
        """The lyric search happens locally, so the reported count must match what is returned."""
        match = make_item(name="Hit", overview="a song about rain")
        miss = make_item(name="Miss", overview="a song about sun")

        patcher, _ = patched_items_api([match, miss])
        try:
            result = get_items(MagicMock(), "user_123", lyrics="RAIN")
        finally:
            patcher.stop()

        assert [item["title"] for item in result["items"]] == ["Hit"]
        assert result["total_count"] == 1

    def test_query_terms_are_translated_to_emby_names(self):
        """Our parameter names differ from Emby's, and unknown ones are passed straight through."""
        patcher, mock_items_api = patched_items_api([])
        try:
            get_items(
                MagicMock(), "user_123", library_id="lib_1",
                artist="Bowie", genre="Rock", search_term="Heroes", years="1977", limit="10",
            )
        finally:
            patcher.stop()

        called_kwargs = mock_items_api.get_users_by_userid_items.call_args[1]
        assert called_kwargs["artists"] == "Bowie"
        assert called_kwargs["genres"] == "Rock"
        assert called_kwargs["search_term"] == "Heroes"
        assert called_kwargs["years"] == "1977"
        assert called_kwargs["limit"] == "10"
        assert called_kwargs["parent_id"] == "lib_1"
        # a genre filter was supplied, so media types are restricted after the query instead
        assert "media_types" not in called_kwargs

    def test_media_types_are_restricted_in_the_query_when_no_genre_is_used(self):
        patcher, mock_items_api = patched_items_api([])
        try:
            get_items(MagicMock(), "user_123", search_term="Heroes")
        finally:
            patcher.stop()

        assert mock_items_api.get_users_by_userid_items.call_args[1]["media_types"] == "Audio,Video"

    def test_genre_search_does_not_send_media_types(self):
        """
        Emby answers Genres combined with MediaTypes with a 500 (a SQLite exception), for
        every library and every MediaTypes value, so a genre search must not send both.
        """
        patcher, mock_items_api = patched_items_api([])
        try:
            get_items(MagicMock(), "user_123", genre="Rock")
        finally:
            patcher.stop()

        called_kwargs = mock_items_api.get_users_by_userid_items.call_args[1]
        assert called_kwargs["genres"] == "Rock"
        assert "media_types" not in called_kwargs

    def test_genre_search_still_returns_only_audio_and_video(self):
        """
        Dropping MediaTypes makes Emby return containers too (series, seasons, box sets),
        which have no media_type and must not reach the client as playable items.
        """
        wanted = make_item(name="A Song", media_type="Audio")
        also_wanted = make_item(name="A Film", media_type="Video")
        container = make_item(name="A Series", media_type=None)

        patcher, _ = patched_items_api([wanted, also_wanted, container])
        try:
            result = get_items(MagicMock(), "user_123", genre="Rock")
        finally:
            patcher.stop()

        assert [item['title'] for item in result['items']] == ["A Song", "A Film"]
        # Emby counted the containers, so report the count actually being returned
        assert result['total_count'] == 2

    def test_blank_query_terms_are_dropped(self):
        """Empty strings mean 'no filter' and must not be sent to Emby."""
        patcher, mock_items_api = patched_items_api([])
        try:
            get_items(MagicMock(), "user_123", artist="", genre="", search_term="", lyrics="",
                      first_date="", last_date="")
        finally:
            patcher.stop()

        called_kwargs = mock_items_api.get_users_by_userid_items.call_args[1]
        for name in ("artists", "genres", "search_term", "min_start_date", "max_end_date"):
            assert name not in called_kwargs

    @pytest.mark.parametrize("flags,expected", [
        ({"is_unplayed": True}, {"IsUnplayed"}),
        ({"is_played": True}, {"IsPlayed"}),
        ({"is_favorite": True}, {"IsFavorite"}),
        ({"is_favorite": True, "is_unplayed": True}, {"IsUnplayed", "IsFavorite"}),
        ({"is_favorite": True, "is_played": True}, {"IsPlayed", "IsFavorite"}),
    ])
    def test_filters_are_applied(self, flags, expected):
        """
        Emby's filters parameter is an order-insensitive comma-separated set, and get_items
        appends in whatever order the caller passed the flags, so compare as a set.
        """
        patcher, mock_items_api = patched_items_api([])
        try:
            get_items(MagicMock(), "user_123", **flags)
        finally:
            patcher.stop()

        applied = mock_items_api.get_users_by_userid_items.call_args[1]["filters"]
        assert set(applied.split(",")) == expected

    @pytest.mark.parametrize("flag", ["is_unplayed", "is_played", "is_favorite"])
    def test_false_flags_do_not_add_a_filter(self, flag):
        """A flag left at False must not narrow the search."""
        patcher, mock_items_api = patched_items_api([])
        try:
            get_items(MagicMock(), "user_123", **{flag: False})
        finally:
            patcher.stop()

        assert "filters" not in mock_items_api.get_users_by_userid_items.call_args[1]

    def test_no_results_returns_an_empty_list(self):
        patcher, _ = patched_items_api([])
        try:
            result = get_items(MagicMock(), "user_123")
        finally:
            patcher.stop()

        assert result == {"success": True, "total_count": 0, "items": []}

    def test_api_error_is_reported(self):
        """An Emby error should be returned rather than raised."""
        with patch('emby_mcp.functions.emby_client.ItemsServiceApi') as mock_api:
            from emby_client.rest import ApiException
            mock_items_api = MagicMock()
            mock_api.return_value = mock_items_api
            mock_items_api.get_users_by_userid_items.side_effect = ApiException(status=500)

            result = get_items(MagicMock(), "user_123")

        assert result["success"] == False
        assert len(result["error"]) > 0