"""Smoke test for the pytest bootstrap.

Confirms the package is importable and the shared brand palette is present.
This is the baseline test that proves the test infrastructure works.
"""

from __future__ import annotations

import python_app.config as config


def test_config_module_imports() -> None:
    """The central config module imports without side effects."""
    assert config is not None


def test_brand_palette_present() -> None:
    """The shared brand palette exposes the navy anchor colour."""
    assert config.BRAND_NAVY == "#002D72"
