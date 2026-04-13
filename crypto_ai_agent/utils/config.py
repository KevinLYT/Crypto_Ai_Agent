"""Application configuration from environment variables."""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings. Extend here when adding chain APIs, vector DB, etc."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: Optional[str] = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    large_tx_multiplier: float = 3.0
    high_freq_tx_per_day: float = 8.0
    high_freq_burst_window_seconds: int = 3600
    high_freq_burst_min_count: int = 6


@lru_cache
def get_settings() -> Settings:
    return Settings()
