# -*- coding: utf-8 -*-
"""Tests for Emby configuration management."""

import os
import pytest
from unittest.mock import patch, MagicMock
from emby_mcp.config import EmbyConfig


class TestEmbyConfig:
    """Tests for EmbyConfig class."""

    def test_initialization_with_defaults(self, sample_config):
        """EmbyConfig should initialize with default values."""
        with patch.dict(os.environ, {
            "EMBY_SERVER_URL": sample_config["server_url"],
            "EMBY_USERNAME": sample_config["username"],
            "EMBY_PASSWORD": sample_config["password"],
            "EMBY_VERIFY_SSL": "True",
            "LLM_MAX_ITEMS": str(sample_config["max_items"]),
        }):
            config = EmbyConfig()
            assert config.server_url == sample_config["server_url"]
            assert config.username == sample_config["username"]
            assert config.password == sample_config["password"]
            assert config.verify_ssl == True
            assert config.max_items == sample_config["max_items"]

    def test_initialization_with_env_file(self):
        """EmbyConfig should load from env file if provided."""
        with patch('emby_mcp.config.load_dotenv') as mock_load:
            config = EmbyConfig(env_file="/path/to/.env")
            mock_load.assert_called_once_with("/path/to/.env", override=True)

    def test_discovered_env_file_is_loaded(self):
        """With no file named, EmbyConfig should fall back to searching for one."""
        with patch('emby_mcp.config.find_dotenv', return_value="/discovered/.env") as mock_find, \
             patch('emby_mcp.config.load_dotenv') as mock_load:
            EmbyConfig()

            mock_find.assert_called_once_with('.env', usecwd=True)
            mock_load.assert_called_once_with("/discovered/.env", override=True)

    def test_nothing_is_loaded_when_no_env_file_is_found(self):
        """A missing .env is normal when the variables are set in the environment."""
        with patch('emby_mcp.config.find_dotenv', return_value=""), \
             patch('emby_mcp.config.load_dotenv') as mock_load:
            EmbyConfig()

            mock_load.assert_not_called()

    def test_is_valid_with_all_values(self, sample_config):
        """is_valid should return True when all required values are present."""
        with patch.dict(os.environ, {
            "EMBY_SERVER_URL": sample_config["server_url"],
            "EMBY_USERNAME": sample_config["username"],
            "EMBY_PASSWORD": sample_config["password"],
        }):
            config = EmbyConfig()
            assert config.is_valid == True

    def test_is_valid_with_missing_values(self):
        """is_valid should return False when required values are missing."""
        with patch.dict(os.environ, {
            "EMBY_SERVER_URL": "",
            "EMBY_USERNAME": "",
            "EMBY_PASSWORD": "",
        }):
            config = EmbyConfig()
            assert config.is_valid == False

    def test_error_message_with_missing_values(self, sample_config):
        """error_message should list all missing required variables."""
        with patch.dict(os.environ, {
            "EMBY_SERVER_URL": "",
            "EMBY_USERNAME": "",
            "EMBY_PASSWORD": "password",
        }):
            config = EmbyConfig()
            error_msg = config.error_message
            assert "EMBY_SERVER_URL" in error_msg
            assert "EMBY_USERNAME" in error_msg
            assert "EMBY_PASSWORD" not in error_msg

    def test_error_message_with_all_missing(self):
        """error_message should list all missing variables when none are set."""
        with patch.dict(os.environ, {}, clear=True):
            config = EmbyConfig()
            error_msg = config.error_message
            assert "EMBY_SERVER_URL" in error_msg
            assert "EMBY_USERNAME" in error_msg
            assert "EMBY_PASSWORD" in error_msg

    def test_str_to_bool_true_values(self):
        """_str_to_bool should correctly identify true values."""
        true_values = ["true", "True", "TRUE", "1", "yes", "Yes", "YES", "y", "Y", "on", "On"]
        for value in true_values:
            assert EmbyConfig._str_to_bool(value) == True

    def test_str_to_bool_false_values(self):
        """_str_to_bool should correctly identify false values."""
        false_values = ["false", "False", "FALSE", "0", "no", "No", "NO", "n", "N", "off", "Off"]
        for value in false_values:
            assert EmbyConfig._str_to_bool(value) == False

    def test_str_to_bool_whitespace(self):
        """_str_to_bool should handle whitespace correctly."""
        assert EmbyConfig._str_to_bool(" true ") == True
        assert EmbyConfig._str_to_bool(" false ") == False