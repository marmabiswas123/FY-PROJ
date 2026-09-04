"""Load and validate the category registry from YAML."""
from __future__ import annotations

from pathlib import Path
from typing import List

import yaml
from pydantic import BaseModel, ConfigDict, HttpUrl


class Category(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    keywords: List[str]
    rss_feeds: List[HttpUrl] = []
    search_queries: List[str] = []


def load_categories(path: str | Path = "categories.yaml") -> List[Category]:
    """Parse categories.yaml and return a list of Category objects."""
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return [Category(**cat) for cat in data.get("categories", [])]