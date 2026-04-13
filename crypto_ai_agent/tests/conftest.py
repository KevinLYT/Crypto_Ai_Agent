"""Pytest fixtures shared across tests."""

from __future__ import annotations

import pytest

from utils.config import get_settings


@pytest.fixture(autouse=True)
def _reset_settings_cache() -> None:
    """Avoid cross-test pollution from `get_settings` lru_cache + env overrides."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
