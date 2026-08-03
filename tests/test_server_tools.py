# -*- coding: utf-8 -*-
"""Tests for the MCP tools exposed to the AI client."""

import json
import pytest
from unittest.mock import patch, MagicMock

import emby_mcp_server
from emby_mcp_server import (
    get_max_chunk_size,
    retrieve_current_library,
    retrieve_genre_list,
    retrieve_library_list,
    retrieve_next_search_chunk,
    retrieve_user_list,
    search_for_item,
    select_library,
    str_to_bool,
)


def make_items(count):
    """Build a list of distinct search result items."""
    return [{'title': f"Track {i}", 'item_id': f"id_{i}"} for i in range(count)]


class TestLibrarySelection:
    """Tests for the library selection tools."""

    def test_no_library_selected_is_reported(self, mcp_context):
        """An unselected library is an empty dict, which must be reported as an error."""
        result = retrieve_current_library()

        assert result.startswith("ERROR")

    def test_the_selected_library_is_reported(self, selected_library):
        result = json.loads(retrieve_current_library())

        assert result == {'name': 'Music', 'id': 'lib_1', 'type': 'music'}

    def test_search_without_library_is_reported(self, mcp_context):
        """Searching before selecting a library must not raise a KeyError."""
        result = json.loads(search_for_item(title_or_album="anything"))

        assert "ERROR" in result["error"]

    def test_select_library_without_name_is_reported(self, mcp_context):
        """An empty library name should be rejected with advice on where to get one."""
        result = select_library("")

        assert result.startswith("ERROR")
        assert "retrieve_library_list" in result


class TestSearchChunking:
    """Tests for chunking of large search results."""

    def test_small_result_is_returned_whole(self, mcp_context):
        """A result that fits in one chunk is returned as-is and marked as the last chunk."""
        mcp_context['current_library'] = {'name': 'Music', 'id': 'lib_1', 'type': 'music'}

        with patch('emby_mcp_server.get_items', return_value={'success': True, 'items': make_items(3)}):
            result = json.loads(search_for_item(title_or_album="track"))

        assert result['total_number_of_items'] == 3
        assert result['chunk_number'] == 1
        assert result['more_chunks_available'] == False
        assert len(result['items']) == 3

    def test_large_result_returns_a_usable_first_chunk(self, mcp_context):
        """A chunked search must return JSON, not a JSON string wrapped in another JSON string."""
        mcp_context['current_library'] = {'name': 'Music', 'id': 'lib_1', 'type': 'music'}
        mcp_context['max_chunk_size'] = '2'

        with patch('emby_mcp_server.get_items', return_value={'success': True, 'items': make_items(5)}):
            result = json.loads(search_for_item(title_or_album="track"))

        assert isinstance(result, dict)
        assert result['total_number_of_items'] == 5
        assert result['chunk_number'] == 1
        assert result['more_chunks_available'] == True
        assert [item['title'] for item in result['items']] == ["Track 0", "Track 1"]

    def test_remaining_chunks_are_returned_in_order(self, mcp_context):
        """Repeatedly asking for the next chunk should walk the whole result set exactly once."""
        mcp_context['current_library'] = {'name': 'Music', 'id': 'lib_1', 'type': 'music'}
        mcp_context['max_chunk_size'] = '2'

        with patch('emby_mcp_server.get_items', return_value={'success': True, 'items': make_items(5)}):
            first = json.loads(search_for_item(title_or_album="track"))

        seen = list(first['items'])
        result = first
        while result['more_chunks_available']:
            result = json.loads(retrieve_next_search_chunk())
            seen.extend(result['items'])

        assert [item['title'] for item in seen] == [f"Track {i}" for i in range(5)]
        assert result['chunk_number'] == 3
        # the saved results are cleared once the last chunk has been handed over
        assert mcp_context['search_item_chunking'] == {}

    def test_next_chunk_without_a_search_returns_empty(self, mcp_context):
        """Asking for more results when none were saved must return an empty result, not fail."""
        assert json.loads(retrieve_next_search_chunk()) == {}


class TestMaxChunkSize:
    """Tests for reading the LLM_MAX_ITEMS setting."""

    def test_valid_value_is_used(self):
        assert get_max_chunk_size({'max_chunk_size': '25'}) == 25

    @pytest.mark.parametrize("value", ["", None, "lots"])
    def test_unusable_value_falls_back_to_default(self, value):
        """A malformed LLM_MAX_ITEMS must not break the search tool."""
        assert get_max_chunk_size({'max_chunk_size': value}) == emby_mcp_server.DEFAULT_MAX_CHUNK_SIZE

    @pytest.mark.parametrize("value", ["0", "-1", 0, -20])
    def test_non_positive_value_falls_back_to_default(self, value):
        """
        A chunk size of zero or less would disable chunking while still reporting
        chunk_size 0, so the whole result set would be returned under a control field
        saying it was empty. Fall back to the default instead.
        """
        assert get_max_chunk_size({'max_chunk_size': value}) == emby_mcp_server.DEFAULT_MAX_CHUNK_SIZE

    def test_zero_chunk_size_still_reports_the_items_it_returns(self, selected_library):
        """The control data must agree with the items actually handed back."""
        selected_library['max_chunk_size'] = '0'

        with patch('emby_mcp_server.get_items', return_value={'success': True, 'items': make_items(3)}):
            result = json.loads(search_for_item(title_or_album="track"))

        assert result['chunk_size'] == len(result['items']) == 3


class TestUserList:
    """Tests for the user list tool."""

    def test_users_are_returned_as_json(self, mcp_context):
        users = [{'user_id': 'u1', 'user_name': 'Alice'}]
        with patch('emby_mcp_server.get_users', return_value={'success': True, 'users': users}):
            assert json.loads(retrieve_user_list()) == users

    def test_failure_is_reported(self, mcp_context):
        with patch('emby_mcp_server.get_users', return_value={'success': False, 'error': 'no route to host'}):
            result = retrieve_user_list()

        assert result.startswith("ERROR")
        assert "no route to host" in result


class TestLibraryList:
    """Tests for the library list tool."""

    def test_libraries_are_returned_and_cached(self, mcp_context):
        libraries = [{'name': 'Music', 'id': 'lib_1', 'type': 'music'}]
        with patch('emby_mcp_server.get_library_list', return_value={'success': True, 'items': libraries}):
            result = retrieve_library_list()

        assert json.loads(result) == libraries
        # later tools reuse the cached list rather than asking the server again
        assert mcp_context['available_libraries'] == libraries

    def test_failure_clears_the_cache(self, mcp_context):
        """A stale library list must not survive a failed refresh."""
        mcp_context['available_libraries'] = [{'name': 'Old', 'id': 'lib_0', 'type': 'music'}]

        with patch('emby_mcp_server.get_library_list', return_value={'success': False, 'error': 'timed out'}):
            result = retrieve_library_list()

        assert result.startswith("ERROR")
        assert mcp_context['available_libraries'] == []


class TestSelectLibrary:
    """Tests for selecting the library that later tools operate on."""

    def test_selection_is_saved_to_the_context(self, mcp_context):
        library = {'name': 'Music', 'id': 'lib_1', 'type': 'music'}
        mcp_context['available_libraries'] = [library]

        with patch('emby_mcp_server.set_current_library', return_value={'success': True, 'library': library}):
            assert select_library("Music") == 'Success'

        assert mcp_context['current_library'] == library

    def test_library_list_is_fetched_when_not_already_cached(self, mcp_context):
        """Selecting before listing should fetch the list rather than refusing."""
        library = {'name': 'Music', 'id': 'lib_1', 'type': 'music'}

        with patch('emby_mcp_server.get_library_list', return_value={'success': True, 'items': [library]}) as fetch, \
             patch('emby_mcp_server.set_current_library', return_value={'success': True, 'library': library}):
            assert select_library("Music") == 'Success'

        fetch.assert_called_once()

    def test_unknown_library_name_is_reported(self, mcp_context):
        mcp_context['available_libraries'] = [{'name': 'Music', 'id': 'lib_1', 'type': 'music'}]

        with patch('emby_mcp_server.set_current_library',
                   return_value={'success': False, 'error': 'library "Films" not found'}):
            result = select_library("Films")

        assert result.startswith("ERROR")
        assert 'Films' in result
        # a failed selection must not disturb whatever was already selected
        assert mcp_context['current_library'] == {}

    def test_server_with_no_libraries_is_reported(self, mcp_context):
        with patch('emby_mcp_server.get_library_list', return_value={'success': True, 'items': []}):
            result = select_library("Music")

        assert result.startswith("ERROR")
        assert "retrieve_library_list" in result


class TestGenreList:
    """Tests for the genre list tool."""

    def test_genres_are_returned_for_the_current_library(self, selected_library):
        with patch('emby_mcp_server.get_genre_list',
                   return_value={'success': True, 'genres': ['Jazz', 'Rock']}) as get_genres:
            assert json.loads(retrieve_genre_list()) == ['Jazz', 'Rock']

        assert get_genres.call_args[1]['library_id'] == 'lib_1'

    def test_genres_without_a_library_are_reported(self, mcp_context):
        result = retrieve_genre_list()

        assert result.startswith("ERROR")
        assert "select_library" in result

    def test_failure_is_reported(self, selected_library):
        with patch('emby_mcp_server.get_genre_list', return_value={'success': False, 'error': 'bad request'}):
            result = retrieve_genre_list()

        assert result.startswith("ERROR")
        assert "bad request" in result


class TestSearchArguments:
    """Tests that search arguments are translated for the underlying query."""

    def test_supplied_arguments_are_passed_through(self, selected_library):
        with patch('emby_mcp_server.get_items', return_value={'success': True, 'items': []}) as get:
            search_for_item(
                title_or_album="Kind of Blue",
                artist_name="Miles Davis",
                genre_name="Jazz",
                broadcast_release_years="1959,1960",
                lyrics_or_description="modal",
            )

        kwargs = get.call_args[1]
        assert kwargs['search_term'] == "Kind of Blue"
        assert kwargs['artist'] == "Miles Davis"
        assert kwargs['genre'] == "Jazz"
        assert kwargs['years'] == "1959,1960"
        assert kwargs['lyrics'] == "modal"
        assert kwargs['library_id'] == 'lib_1'

    def test_blank_arguments_are_omitted(self, selected_library):
        """Empty strings must not become empty filters that match nothing."""
        with patch('emby_mcp_server.get_items', return_value={'success': True, 'items': []}) as get:
            search_for_item(title_or_album="Kind of Blue", artist_name="", genre_name=None)

        kwargs = get.call_args[1]
        assert kwargs['search_term'] == "Kind of Blue"
        for name in ('artist', 'genre', 'years', 'lyrics'):
            assert name not in kwargs

    def test_search_failure_is_reported_as_json(self, selected_library):
        """The tool documents a JSON return, so errors must be JSON too."""
        with patch('emby_mcp_server.get_items', return_value={'success': False, 'error': 'query rejected'}):
            result = json.loads(search_for_item(title_or_album="anything"))

        assert "query rejected" in result['error']

    def test_a_new_search_discards_the_previous_saved_results(self, selected_library):
        """Stale chunks from an earlier search must not leak into a new one."""
        selected_library['max_chunk_size'] = '2'
        with patch('emby_mcp_server.get_items', return_value={'success': True, 'items': make_items(5)}):
            search_for_item(title_or_album="track")

        with patch('emby_mcp_server.get_items', return_value={'success': True, 'items': make_items(1)}):
            result = json.loads(search_for_item(title_or_album="other"))

        assert result['total_number_of_items'] == 1
        assert result['more_chunks_available'] == False
        assert selected_library['search_item_chunking'] == {}


class TestChunkingEdgeCases:
    """Tests for malformed or exhausted chunking state."""

    def test_missing_control_data_returns_empty(self, mcp_context):
        """Saved results without the control fields must not raise."""
        mcp_context['search_item_chunking'] = {'items': make_items(3)}

        assert json.loads(retrieve_next_search_chunk()) == {}
        assert mcp_context['search_item_chunking'] == {}

    def test_zeroed_control_data_returns_an_empty_result(self, mcp_context):
        mcp_context['search_item_chunking'] = {
            'search_id': 'search_1',
            'total_number_of_items': 0,
            'chunk_size': 0,
            'chunk_number': 0,
            'items': [],
        }

        result = json.loads(retrieve_next_search_chunk())

        assert result['total_number_of_items'] == 0
        assert result['more_chunks_available'] == False
        assert result['items'] == []
        assert mcp_context['search_item_chunking'] == {}

    def test_exhausted_search_returns_an_empty_last_chunk(self, mcp_context):
        """Asking past the end of the results must report zero remaining, not raise."""
        mcp_context['search_item_chunking'] = {
            'search_id': 'search_1',
            'total_number_of_items': 4,
            'chunk_size': 2,
            'chunk_number': 2,  # both chunks already handed over
            'items': make_items(4),
        }

        result = json.loads(retrieve_next_search_chunk())

        assert result['total_number_of_items'] == 4
        assert result['chunk_size'] == 0
        assert result['more_chunks_available'] == False
        assert result['items'] == []
        assert mcp_context['search_item_chunking'] == {}

    def test_search_id_is_stable_across_chunks(self, selected_library):
        """The client uses search_id to tell one search's chunks from another's."""
        selected_library['max_chunk_size'] = '2'

        with patch('emby_mcp_server.get_items', return_value={'success': True, 'items': make_items(5)}):
            first = json.loads(search_for_item(title_or_album="track"))

        second = json.loads(retrieve_next_search_chunk())

        assert first['search_id']
        assert first['search_id'] == second['search_id']


class TestStrToBool:
    """Tests for parsing the EMBY_VERIFY_SSL setting."""

    @pytest.mark.parametrize("value", ["true", "True", "TRUE", "1", "yes", "y", "on", " true "])
    def test_truthy_values(self, value):
        assert str_to_bool(value) == True

    @pytest.mark.parametrize("value", ["false", "False", "0", "no", "n", "off", "", "maybe", None])
    def test_falsy_values(self, value):
        assert str_to_bool(value) == False


class TestVersion:
    """The version reported to the Emby server identifies this client in its logs."""

    def test_reported_version_matches_the_package(self):
        """A hardcoded version silently drifts from the package it ships in."""
        from emby_mcp import __version__

        assert emby_mcp_server.MY_VERSION == __version__
