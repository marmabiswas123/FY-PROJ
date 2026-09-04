"""News‑Fetcher sub‑graph nodes (WP‑4) – part 1: helpers & SearchNode."""
from __future__ import annotations

import asyncio
import hashlib
import re
from datetime import datetime, timezone
from typing import List
from uuid import UUID

import feedparser
import httpx
from datasketch import MinHash, MinHashLSH
from pydantic import HttpUrl

from src.config import settings
from src.graph import PipelineState
from src.schemas import RawHit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_URL_CLEAN_RE = re.compile(r"[?&](utm_[^=]+|fbclid|gclid)=[^&]*")

def canonicalize(url: str) -> str:
    """Strip tracking params, lower‑case, remove trailing slash."""
    url = _URL_CLEAN_RE.sub("", url)
    return url.rstrip("/").lower()


def minhash_signature(text: str, num_perm: int = 128) -> MinHash:
    m = MinHash(num_perm=num_perm)
    for token in text.split():
        m.update(token.encode("utf-8"))
    return m


# Global LSH index (in‑memory; replace with Redis in prod)
_lsh = MinHashLSH(threshold=0.9, num_perm=128)


async def _is_duplicate(url: str, text: str) -> bool:
    """Return True if we have seen a near‑duplicate."""
    sig = minhash_signature(text)
    key = canonicalize(url)
    if key in _lsh.keys(sig):
        return True
    _lsh.insert(key, sig)
    return False


# ---------------------------------------------------------------------------
# Node: SearchNode – hit a news search API (NewsAPI.org example)
# ---------------------------------------------------------------------------

async def search_node(state: PipelineState) -> PipelineState:
    """Query configured search APIs for the current category keywords."""
    if not state.category_id:
        state.errors.append("search_node: category_id missing")
        return state

    if not settings.newsapi_key:
        state.errors.append("search_node: NEWSAPI_KEY not set")
        return state

    async with httpx.AsyncClient(timeout=10) as client:
        tasks = []
        for kw in settings.keywords_for_category(state.category_id):
            params = {
                "q": kw,
                "language": "en",
                "pageSize": 10,
                "apiKey": settings.newsapi_key,
            }
            tasks.append(client.get("https://newsapi.org/v2/everything", params=params))

        responses = await asyncio.gather(*tasks, return_exceptions=True)

    for resp in responses:
        if isinstance(resp, Exception):
            state.errors.append(f"search_node: {resp}")
            continue
        data = resp.json()
        for art in data.get("articles", []):
            hit = RawHit(
                url=art["url"],
                title=art["title"],
                source=art["source"]["name"],
                published_at=datetime.fromisoformat(art["publishedAt"].replace("Z", "+00:00")),
                query=kw,
                run_id=state.run_id,
            )
            state.raw_hits.append(hit)

    return state