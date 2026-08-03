# -*- coding: utf-8 -*-
"""Configuration management for Emby MCP."""

import os
from typing import Optional
from dotenv import load_dotenv, find_dotenv


class EmbyConfig:
    """Manages Emby server configuration from environment variables."""

    def __init__(self, env_file: Optional[str] = None):
        self._load_env(env_file)
        self.server_url: Optional[str] = os.getenv("EMBY_SERVER_URL")
        self.username: Optional[str] = os.getenv("EMBY_USERNAME")
        self.password: Optional[str] = os.getenv("EMBY_PASSWORD")
        self.verify_ssl: bool = self._str_to_bool(
            os.getenv("EMBY_VERIFY_SSL", "True")
        )
        self.max_items: int = self._str_to_int(os.getenv("LLM_MAX_ITEMS"), 100)

    def _load_env(self, env_file: Optional[str] = None) -> None:
        """Load environment variables from .env file."""
        if env_file:
            load_dotenv(env_file, override=True)
        else:
            env_found = find_dotenv('.env', usecwd=True)
            if env_found:
                load_dotenv(env_found, override=True)

    @staticmethod
    def _str_to_bool(value: str) -> bool:
        """Convert string to boolean."""
        return str(value).strip().lower() in ("true", "1", "yes", "y", "on")

    @staticmethod
    def _str_to_int(value: Optional[str], default: int) -> int:
        """Convert string to integer, falling back to the default if it is missing or not a number."""
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return default

    @property
    def is_valid(self) -> bool:
        """Check if all required configuration is present."""
        return all([
            self.server_url,
            self.username,
            self.password,
        ])

    @property
    def error_message(self) -> str:
        """Generate error message for missing configuration."""
        missing = []
        if not self.server_url:
            missing.append("EMBY_SERVER_URL")
        if not self.username:
            missing.append("EMBY_USERNAME")
        if not self.password:
            missing.append("EMBY_PASSWORD")
        return f"Missing required variables: {', '.join(missing)}"