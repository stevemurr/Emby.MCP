#!/usr/bin/env python3
"""Automatically apply embyclient hotfixes to the installed package.

This module is registered as a post-install hook so that every time the
emby-mcp package is installed into a virtual environment (via ``uv sync``,
``pip install``, etc.), the two patched embyclient files are written into
the site-packages directory alongside the upstream library.

The patches fix two bugs in the official ``embyclient`` SDK:
  1. Missing ``embyauth`` authentication header (configuration.py)
  2. Missing ``item_id`` parameter in user_service_api.py
"""

import os
import shutil
import sys
from pathlib import Path


def find_emby_client_package() -> Path:
    """Return the path to the ``emby_client`` package directory."""
    for lib_dir in sys.path:
        candidate = Path(lib_dir) / "emby_client"
        if candidate.is_dir() and (candidate / "configuration.py").exists():
            return candidate
    raise RuntimeError(
        "Could not locate installed emby_client package. "
        "Is embyclient installed?"
    )


def apply_hotfixs() -> None:
    """Copy the patched files into the emby_client package."""
    # The hotfix files live next to this module in the package
    script_dir = Path(__file__).resolve().parent

    emby_client_pkg = find_emby_client_package()

    # Patch configuration.py
    src_config = script_dir / "configuration.py"
    dst_config = emby_client_pkg / "configuration.py"
    if src_config.exists():
        shutil.copy2(str(src_config), str(dst_config))
        print(f"✏️  Patched {dst_config}")
    else:
        print(
            f"⚠️  emby-mcp: {src_config} not found. Skipping configuration.py patch.",
            file=sys.stderr,
        )

    # Patch user_service_api.py
    src_user_service = script_dir / "user_service_api.py"
    dst_user_service = emby_client_pkg / "api" / "user_service_api.py"
    if src_user_service.exists():
        dst_user_service.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src_user_service), str(dst_user_service))
        print(f"✏️  Patched {dst_user_service}")
    else:
        print(
            f"⚠️  emby-mcp: {src_user_service} not found. Skipping user_service_api.py patch.",
            file=sys.stderr,
        )

    print("✅  emby-mcp hotfixes applied successfully.")


if __name__ == "__main__":
    apply_hotfixs()