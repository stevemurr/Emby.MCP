# -*- coding: utf-8 -*-
"""
Tests for the post-install hook that patches the installed embyclient SDK.

This hook writes into site-packages, so every test here works against a temporary
directory rather than the real installation.
"""

import sys
import pytest
from pathlib import Path
from unittest.mock import patch

from emby_mcp.install_hotfixes import apply_hotfixs, find_emby_client_package


@pytest.fixture
def fake_site_packages(tmp_path):
    """A directory laid out like an installed emby_client package."""
    pkg = tmp_path / "site-packages" / "emby_client"
    (pkg / "api").mkdir(parents=True)
    (pkg / "configuration.py").write_text("upstream configuration\n")
    (pkg / "api" / "user_service_api.py").write_text("upstream user service\n")
    return pkg


@pytest.fixture
def fake_source(tmp_path):
    """A directory holding the patched files that ship inside this package."""
    src = tmp_path / "emby_mcp"
    src.mkdir()
    (src / "configuration.py").write_text("patched configuration\n")
    (src / "user_service_api.py").write_text("patched user service\n")
    return src


class TestFindEmbyClientPackage:
    """Tests for locating the installed SDK."""

    def test_package_is_found_on_the_path(self, fake_site_packages):
        with patch.object(sys, 'path', [str(fake_site_packages.parent)]):
            assert find_emby_client_package() == fake_site_packages

    def test_a_directory_without_configuration_is_skipped(self, tmp_path, fake_site_packages):
        """A same-named directory that is not the SDK must not be patched over."""
        decoy = tmp_path / "decoy" / "emby_client"
        decoy.mkdir(parents=True)

        with patch.object(sys, 'path', [str(decoy.parent), str(fake_site_packages.parent)]):
            assert find_emby_client_package() == fake_site_packages

    def test_a_missing_package_is_reported(self, tmp_path):
        """Silently doing nothing here would leave the SDK bugs in place."""
        with patch.object(sys, 'path', [str(tmp_path)]):
            with pytest.raises(RuntimeError) as error:
                find_emby_client_package()

        assert "embyclient" in str(error.value)


class TestApplyHotfixes:
    """Tests for copying the patched files into the SDK."""

    def test_both_files_are_patched(self, fake_site_packages, fake_source):
        with patch('emby_mcp.install_hotfixes.Path') as mock_path, \
             patch('emby_mcp.install_hotfixes.find_emby_client_package',
                   return_value=fake_site_packages):
            mock_path.return_value.resolve.return_value.parent = fake_source

            apply_hotfixs()

        assert fake_site_packages.joinpath("configuration.py").read_text() == "patched configuration\n"
        assert fake_site_packages.joinpath("api", "user_service_api.py").read_text() == "patched user service\n"

    def test_the_api_directory_is_created_when_absent(self, fake_site_packages, fake_source):
        """A wheel layout without the api/ directory must not crash the install."""
        target = fake_site_packages / "api" / "user_service_api.py"
        target.unlink()
        target.parent.rmdir()

        with patch('emby_mcp.install_hotfixes.Path') as mock_path, \
             patch('emby_mcp.install_hotfixes.find_emby_client_package',
                   return_value=fake_site_packages):
            mock_path.return_value.resolve.return_value.parent = fake_source

            apply_hotfixs()

        assert target.read_text() == "patched user service\n"

    def test_missing_patch_files_are_skipped_rather_than_fatal(self, fake_site_packages, tmp_path, capsys):
        """
        A partial install should leave the upstream files intact and warn, rather than
        raising and failing the whole installation.
        """
        empty_source = tmp_path / "empty"
        empty_source.mkdir()

        with patch('emby_mcp.install_hotfixes.Path') as mock_path, \
             patch('emby_mcp.install_hotfixes.find_emby_client_package',
                   return_value=fake_site_packages):
            mock_path.return_value.resolve.return_value.parent = empty_source

            apply_hotfixs()

        assert fake_site_packages.joinpath("configuration.py").read_text() == "upstream configuration\n"
        assert "Skipping configuration.py" in capsys.readouterr().err
