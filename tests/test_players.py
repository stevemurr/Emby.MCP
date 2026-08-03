# -*- coding: utf-8 -*-
"""Tests for Emby player management functions."""

import pytest
from unittest.mock import patch, MagicMock
from emby_mcp.functions import (
    get_player_sessions,
    full_player_sessions,
    get_playqueue_items,
    send_player_command
)


class TestPlayerFunctions:
    """Tests for player-related functions."""

    def test_get_player_sessions_success(self):
        """get_player_sessions should return active player sessions."""
        mock_api_client = MagicMock()
        
        with patch('emby_mcp.functions.emby_client.SessionsServiceApi') as mock_api_sessions:
            mock_sessions_api = MagicMock()
            mock_api_sessions.return_value = mock_sessions_api
            
            mock_session = MagicMock()
            mock_session.client = "Test Client"
            mock_session.id = "session_123"
            mock_session.device_id = "device_123"
            mock_session.device_name = "Test Device"
            mock_session.remote_end_point = "192.168.1.1"
            mock_session.playable_media_types = ["Video", "Audio"]
            mock_session.now_playing_item = MagicMock()
            mock_session.now_playing_item.name = "Now Playing"
            mock_session.now_playing_item.artists = ["Artist 1"]
            mock_session.now_playing_item.album = "Album 1"
            mock_session.now_playing_item.index_number = 1
            mock_session.now_playing_item.parent_index_number = 1
            mock_session.now_playing_item.id = "item_123"
            mock_session.now_playing_item.run_time_ticks = 36000000000
            mock_session.play_state = MagicMock()
            mock_session.play_state.position_ticks = 18000000000
            mock_session.play_state.is_paused = False

            # get_sessions returns a plain list of sessions, not a query result object
            mock_sessions_api.get_sessions.return_value = [mock_session]

            result = get_player_sessions(mock_api_client, user_id="user_123")

            assert result["success"] == True
            assert len(result["sessions"]) == 1
            assert result["sessions"][0]["client_name"] == "Test Client"
            assert result["sessions"][0]["now_playing_total_time"] == "01:00:00"
            assert result["sessions"][0]["now_playing_position_time"] == "00:30:00"

    def test_get_player_sessions_unknown_duration(self):
        """get_player_sessions should cope with items that have no run time, eg live streams."""
        mock_api_client = MagicMock()

        with patch('emby_mcp.functions.emby_client.SessionsServiceApi') as mock_api_sessions:
            mock_sessions_api = MagicMock()
            mock_api_sessions.return_value = mock_sessions_api

            mock_session = MagicMock()
            mock_session.playable_media_types = ["Video"]
            mock_session.remote_end_point = "192.168.1.1"
            mock_session.now_playing_item = MagicMock()
            mock_session.now_playing_item.run_time_ticks = None
            mock_session.play_state = MagicMock()
            mock_session.play_state.position_ticks = None
            mock_session.play_state.is_paused = False

            mock_sessions_api.get_sessions.return_value = [mock_session]

            result = get_player_sessions(mock_api_client)

            assert result["success"] == True
            session = result["sessions"][0]
            assert session["now_playing_total_milliseconds"] is None
            assert session["now_playing_total_time"] == ""
            assert session["now_playing_position_time"] == ""

    def test_get_player_sessions_position_zero(self):
        """A play position of zero should be reported as a time, not as blank."""
        mock_api_client = MagicMock()

        with patch('emby_mcp.functions.emby_client.SessionsServiceApi') as mock_api_sessions:
            mock_sessions_api = MagicMock()
            mock_api_sessions.return_value = mock_sessions_api

            mock_session = MagicMock()
            mock_session.playable_media_types = ["Audio"]
            mock_session.remote_end_point = "127.0.0.1"
            mock_session.now_playing_item = MagicMock()
            mock_session.now_playing_item.run_time_ticks = 36000000000
            mock_session.play_state = MagicMock()
            mock_session.play_state.position_ticks = 0
            mock_session.play_state.is_paused = True

            mock_sessions_api.get_sessions.return_value = [mock_session]

            result = get_player_sessions(mock_api_client)

            session = result["sessions"][0]
            assert session["now_playing_position_time"] == "00:00:00"
            assert session["now_playing_total_time"] == "01:00:00"
            assert session["local_to_media_server"] == True

    def test_get_player_sessions_empty(self):
        """get_player_sessions should handle empty sessions."""
        mock_api_client = MagicMock()

        with patch('emby_mcp.functions.emby_client.SessionsServiceApi') as mock_api_sessions:
            mock_sessions_api = MagicMock()
            mock_api_sessions.return_value = mock_sessions_api

            mock_sessions_api.get_sessions.return_value = []

            result = get_player_sessions(mock_api_client)

            assert result["success"] == True
            assert len(result["sessions"]) == 0

    def test_full_player_sessions_success(self):
        """full_player_sessions should return detailed player information."""
        mock_api_client = MagicMock()
        
        with patch('emby_mcp.functions.emby_client.SessionsServiceApi') as mock_api_sessions:
            mock_sessions_api = MagicMock()
            mock_api_sessions.return_value = mock_sessions_api
            
            mock_session = MagicMock()
            mock_session.client = "Full Client"
            mock_session.id = "session_456"
            mock_session.device_id = "device_456"
            mock_session.device_name = "Full Device"
            mock_session.remote_end_point = "192.168.1.2"
            mock_session.playable_media_types = ["Video"]
            mock_session.now_playing_item = MagicMock()
            mock_session.now_playing_item.name = "Full Detail"
            mock_session.play_state = MagicMock()
            mock_session.play_state.position_ticks = None
            mock_session.play_state.is_paused = True

            mock_sessions_api.get_sessions.return_value = [mock_session]

            result = full_player_sessions(mock_api_client, user_id="user_123")

            assert result["success"] == True
            assert len(result["sessions"]) == 1

    def test_get_playqueue_items_success(self):
        """get_playqueue_items should return playqueue items."""
        mock_api_client = MagicMock()

        with patch('emby_mcp.functions.emby_client.SessionsServiceApi') as mock_api_sessions:
            mock_sessions_api = MagicMock()
            mock_api_sessions.return_value = mock_sessions_api

            mock_item = MagicMock()
            mock_item.name = "Queue Item 1"
            mock_item.id = "queue_item_1"
            mock_item.media_type = "Audio"
            mock_item.index_number = 1
            mock_item.run_time_ticks = 18000000000

            mock_response = MagicMock()
            mock_response.total_record_count = 1
            mock_response.items = [mock_item]
            mock_sessions_api.get_sessions_playqueue.return_value = mock_response

            result = get_playqueue_items(mock_api_client, "session_123")

            assert result["success"] == True
            assert len(result["items"]) == 1
            assert result["items"][0]["title"] == "Queue Item 1"
            assert result["items"][0]["run_time"] == "00:30:00"
            assert "run_time_ticks" not in result["items"][0]

    def test_get_playqueue_items_empty(self):
        """An empty play queue should return an empty item list."""
        with patch('emby_mcp.functions.emby_client.SessionsServiceApi') as mock_api_sessions:
            mock_response = MagicMock()
            mock_response.total_record_count = 0
            mock_api_sessions.return_value.get_sessions_playqueue.return_value = mock_response

            result = get_playqueue_items(MagicMock(), "session_123")

        assert result == {"success": True, "items": []}

    def test_get_playqueue_items_api_error(self):
        with patch('emby_mcp.functions.emby_client.SessionsServiceApi') as mock_api_sessions:
            from emby_client.rest import ApiException
            mock_api_sessions.return_value.get_sessions_playqueue.side_effect = ApiException(status=500)

            result = get_playqueue_items(MagicMock(), "session_123")

        assert result["success"] == False
        assert len(result["error"]) > 0

    def test_get_playqueue_items_requires_session_id(self):
        """get_playqueue_items should reject an empty session_id."""
        result = get_playqueue_items(MagicMock(), "")

        assert result["success"] == False
        assert "session_id" in result["error"]

    def test_get_player_sessions_filters_by_media_type(self):
        """Asking for audio players must exclude sessions that cannot play audio."""
        with patch('emby_mcp.functions.emby_client.SessionsServiceApi') as mock_api_sessions:
            audio_player = MagicMock()
            audio_player.client = "Speaker"
            audio_player.playable_media_types = ["Audio"]
            audio_player.remote_end_point = "::1"
            audio_player.now_playing_item = None
            audio_player.play_state = None

            video_player = MagicMock()
            video_player.client = "TV"
            video_player.playable_media_types = ["Video"]
            video_player.remote_end_point = "192.168.1.5"
            video_player.now_playing_item = None
            video_player.play_state = None

            silent_player = MagicMock()
            silent_player.playable_media_types = []

            mock_api_sessions.return_value.get_sessions.return_value = [
                audio_player, video_player, silent_player,
            ]

            result = get_player_sessions(MagicMock(), media_type="audio")

        assert [session["client_name"] for session in result["sessions"]] == ["Speaker"]
        # a session on the same host as Emby is flagged so the AI knows it is the local player
        assert result["sessions"][0]["local_to_media_server"] == True

    def test_get_player_sessions_api_error(self):
        with patch('emby_mcp.functions.emby_client.SessionsServiceApi') as mock_api_sessions:
            from emby_client.rest import ApiException
            mock_api_sessions.return_value.get_sessions.side_effect = ApiException(status=500)

            result = get_player_sessions(MagicMock())

        assert result["success"] == False
        assert len(result["error"]) > 0

    def test_full_player_sessions_without_a_user_lists_every_session(self):
        """With no user_id, Emby is asked for all sessions rather than controllable ones."""
        with patch('emby_mcp.functions.emby_client.SessionsServiceApi') as mock_api_sessions:
            session = MagicMock()
            session.playable_media_types = ["Audio"]
            mock_api_sessions.return_value.get_sessions.return_value = [session]

            result = full_player_sessions(MagicMock())

            mock_api_sessions.return_value.get_sessions.assert_called_once_with()

        assert len(result["sessions"]) == 1

    def test_full_player_sessions_api_error(self):
        with patch('emby_mcp.functions.emby_client.SessionsServiceApi') as mock_api_sessions:
            from emby_client.rest import ApiException
            mock_api_sessions.return_value.get_sessions.side_effect = ApiException(status=500)

            result = full_player_sessions(MagicMock())

        assert result["success"] == False
        assert len(result["error"]) > 0

    def test_playnow_api_error_is_reported(self):
        with patch('emby_mcp.functions.emby_client.SessionsServiceApi') as mock_api_sessions:
            from emby_client.rest import ApiException
            mock_api_sessions.return_value.post_sessions_by_id_playing.side_effect = ApiException(status=500)

            result = send_player_command(MagicMock(), "session_123", "PlayNow", item_ids="item1")

        assert result["success"] == False
        assert len(result["error"]) > 0

    @pytest.mark.parametrize("command,expected_ticks", [
        ("Rewind", -300000000),
        ("FastForward", 300000000),
        ("SeekRelative", 300000000),
    ])
    def test_relative_seeks_default_to_thirty_seconds(self, command, expected_ticks):
        """Skipping commands need a sensible default when the caller gives no time."""
        with patch('emby_mcp.functions.emby_client.SessionsServiceApi'), \
             patch('emby_mcp.functions.emby_client.PlaystateRequest') as mock_playstate:
            result = send_player_command(MagicMock(), "session_123", command, user_id="user_123")

        assert result["success"] == True
        assert mock_playstate.call_args[0][1] == expected_ticks

    def test_playstate_commands_need_a_user(self):
        result = send_player_command(MagicMock(), "session_123", "Pause")

        assert result["success"] == False
        assert "No user_id" in result["error"]

    def test_send_player_command_success(self):
        """send_player_command should send playstate commands to players."""
        mock_api_client = MagicMock()

        with patch('emby_mcp.functions.emby_client.SessionsServiceApi') as mock_api_sessions:
            mock_sessions_api = MagicMock()
            mock_api_sessions.return_value = mock_sessions_api

            result = send_player_command(
                mock_api_client,
                "session_123",
                "Pause",
                user_id="user_123",
            )

            assert result["success"] == True
            mock_sessions_api.post_sessions_by_id_playing_by_command.assert_called_once()

    def test_send_player_command_playnow_splits_item_ids(self):
        """PlayNow should pass each item id to Emby separately, not as one comma joined string."""
        mock_api_client = MagicMock()

        with patch('emby_mcp.functions.emby_client.SessionsServiceApi') as mock_api_sessions:
            mock_sessions_api = MagicMock()
            mock_api_sessions.return_value = mock_sessions_api

            result = send_player_command(
                mock_api_client,
                "session_123",
                "PlayNow",
                item_ids="item1,item2,item3",
            )

            assert result["success"] == True
            passed_item_ids = mock_sessions_api.post_sessions_by_id_playing.call_args[0][1]
            assert passed_item_ids == ["item1", "item2", "item3"]

    def test_send_player_command_playnow_requires_item_ids(self):
        """PlayNow without item_ids should be rejected."""
        result = send_player_command(MagicMock(), "session_123", "PlayNow")

        assert result["success"] == False
        assert "item_ids" in result["error"]

    def test_send_player_command_rewind_becomes_negative_seek(self):
        """Rewind is translated into a negative SeekRelative because some players ignore Rewind."""
        mock_api_client = MagicMock()

        with patch('emby_mcp.functions.emby_client.SessionsServiceApi') as mock_api_sessions:
            mock_sessions_api = MagicMock()
            mock_api_sessions.return_value = mock_sessions_api

            with patch('emby_mcp.functions.emby_client.PlaystateRequest') as mock_playstate:
                result = send_player_command(
                    mock_api_client,
                    "session_123",
                    "Rewind",
                    user_id="user_123",
                    time_ms=5000,
                )

            assert result["success"] == True
            command, ticks, user_id = mock_playstate.call_args[0]
            assert command == "SeekRelative"
            assert ticks == -50000000
            assert user_id == "user_123"

    def test_send_player_command_rejects_non_numeric_time(self):
        """A non-numeric time_ms should be reported rather than silently mangled."""
        result = send_player_command(
            MagicMock(), "session_123", "Seek", user_id="user_123", time_ms="soon"
        )

        assert result["success"] == False
        assert "time_ms" in result["error"]

    def test_send_player_command_unknown_command(self):
        """An unsupported command should be reported."""
        result = send_player_command(MagicMock(), "session_123", "Explode", user_id="user_123")

        assert result["success"] == False
        assert "Unsupported command" in result["error"]

    def test_send_player_command_error(self):
        """send_player_command should handle errors."""
        mock_api_client = MagicMock()

        with patch('emby_mcp.functions.emby_client.SessionsServiceApi') as mock_api_sessions:
            mock_sessions_api = MagicMock()
            mock_api_sessions.return_value = mock_sessions_api

            from emby_client.rest import ApiException
            mock_sessions_api.post_sessions_by_id_playing_by_command.side_effect = ApiException(status=500)

            result = send_player_command(mock_api_client, "session_123", "Pause", user_id="user_123")

            assert result["success"] == False
            assert "error" in result
            assert len(result["error"]) > 0