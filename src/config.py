"""Configuration management using pydantic-settings."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.categories import Category, load_categories


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    llm_provider: str = "openai"   # openai | anthropic | local

    # Search APIs
    serpapi_key: str | None = None
    newsapi_key: str | None = None
    gnews_key: str | None = None

    # Database
    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/newsdb"

    # Redis for dedup cache
    redis_url: str = "redis://localhost:6379/0"

    # Scheduler
    fetch_interval_minutes: int = 30

    # Category registry (loaded once)
    _categories: List[Category] | None = None

    def categories(self) -> List[Category]:
        if self._categories is None:
            self._categories = load_categories(Path(__file__).parents[1] / "categories.yaml")
        return self._categories

    def keywords_for_category(self, cat_id: str) -> List[str]:
        for cat in self.categories():
            if cat.id == cat_id:
                return cat.keywords
        return []

    def rss_feeds_for_category(self, cat_id: str) -> List[HttpUrl]:
        for cat in self.categories():
            if cat.id == cat_id:
                return cat.rss_feeds
        return []


settings = Settings()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return settings