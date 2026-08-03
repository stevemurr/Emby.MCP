# -*- coding: utf-8 -*-
"""Tests for the media player MCP tools exposed to the AI client."""

import json
import pytest
from unittest.mock import patch, MagicMock

from emby_mcp import server as emby_server
from emby_mcp.server import (
    control_media_player,
    retrieve_player_list,
    retrieve_player_queue,
)


class TestPlayerList:
    """Tests for listing the players we can control."""

    def test_sessions_are_returned(self, mcp_context):
        sessions = [{'client_name': 'Living Room', 'session_id': 'sess_1'}]
        with patch('emby_mcp.server.get_player_sessions',
                   return_value={'success': True, 'sessions': sessions}):
            assert json.loads(retrieve_player_list()) == sessions

    def test_media_type_narrows_the_list(self, mcp_context):
        with patch('emby_mcp.server.get_player_sessions',
                   return_value={'success': True, 'sessions': []}) as get:
            retrieve_player_list("Audio")

        assert get.call_args[1]['media_type'] == 'Audio'
        assert get.call_args[1]['user_id'] == 'user_123'

    def test_failure_is_reported(self, mcp_context):
        with patch('emby_mcp.server.get_player_sessions',
                   return_value={'success': False, 'error': 'server busy'}):
            result = retrieve_player_list()

        assert result.startswith("ERROR")
        assert 'server busy' in result


class TestPlayerQueue:
    """Tests for reading a player's play queue."""

    def test_queue_items_are_returned(self, mcp_context):
        items = [{'title': 'Track 1', 'item_id': 'id_1', 'playlist_item_id': 'pq_1'}]
        with patch('emby_mcp.server.get_playqueue_items', return_value={'success': True, 'items': items}) as get:
            assert json.loads(retrieve_player_queue("sess_1")) == items

        assert get.call_args[0][1] == 'sess_1'

    def test_failure_is_reported(self, mcp_context):
        with patch('emby_mcp.server.get_playqueue_items',
                   return_value={'success': False, 'error': 'session gone'}):
            result = retrieve_player_queue("sess_1")

        assert result.startswith("ERROR")
        assert 'session gone' in result


class TestControlMediaPlayer:
    """Tests for sending commands to a player."""

    def test_command_is_sent(self, mcp_context):
        with patch('emby_mcp.server.send_player_command', return_value={'success': True}) as send:
            assert control_media_player("sess_1", "Pause") == "Success"

        assert send.call_args[0][1:] == ('sess_1', 'Pause')
        assert send.call_args[1]['user_id'] == 'user_123'

    def test_play_is_accepted_as_an_alias_for_playnow(self, mcp_context):
        """An AI client is likely to say "play", which Emby does not recognise."""
        with patch('emby_mcp.server.send_player_command', return_value={'success': True}) as send:
            control_media_player("sess_1", "play", item_ids="id_1")

        assert send.call_args[0][2] == 'PlayNow'

    def test_omitted_optional_arguments_become_emby_defaults(self, mcp_context):
        """None must not reach the API layer, which expects a string and an int."""
        with patch('emby_mcp.server.send_player_command', return_value={'success': True}) as send:
            control_media_player("sess_1", "NextTrack")

        assert send.call_args[1]['item_ids'] == ""
        assert send.call_args[1]['time_ms'] == 0

    def test_seek_time_is_passed_through(self, mcp_context):
        with patch('emby_mcp.server.send_player_command', return_value={'success': True}) as send:
            control_media_player("sess_1", "Seek", time_milliseconds=30000)

        assert send.call_args[1]['time_ms'] == 30000

    def test_missing_session_id_is_reported(self, mcp_context):
        with patch('emby_mcp.server.send_player_command') as send:
            result = control_media_player("", "Pause")

        assert result.startswith("ERROR")
        assert "retrieve_player_list" in result
        send.assert_not_called()

    def test_missing_command_is_reported(self, mcp_context):
        """The error should list the commands, since the client has to pick one."""
        with patch('emby_mcp.server.send_player_command') as send:
            result = control_media_player("sess_1", "")

        assert result.startswith("ERROR")
        assert "PlayNow" in result
        send.assert_not_called()

    def test_failure_is_reported(self, mcp_context):
        with patch('emby_mcp.server.send_player_command',
                   return_value={'success': False, 'error': 'player refused'}):
            result = control_media_player("sess_1", "Pause")

        assert result.startswith("ERROR")
        assert 'player refused' in result
