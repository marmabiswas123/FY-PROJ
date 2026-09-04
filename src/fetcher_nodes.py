"""News‑Fetcher sub‑graph nodes (WP‑4) – part 2: RSS, Normalize, Dedup, registration."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import feedparser
import httpx
from pydantic import HttpUrl

from src.config import settings
from src.fetcher import canonicalize, _is_duplicate
from src.graph import PipelineState
from src.schemas import RawHit


# ---------------------------------------------------------------------------
# Node: RSSNode – pull RSS/Atom feeds for the category
# ---------------------------------------------------------------------------

async def rss_node(state: PipelineState) -> PipelineState:
    if not state.category_id:
        return state

    feeds = settings.rss_feeds_for_category(state.category_id)
    async with httpx.AsyncClient(timeout=10) as client:
        for feed_url in feeds:
            try:
                resp = await client.get(str(feed_url))
                parsed = feedparser.parse(resp.text)
                for entry in parsed.entries[:20]:
                    hit = RawHit(
                        url=entry.link,
                        title=entry.title,
                        source=parsed.feed.get("title", feed_url),
                        published_at=datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                            if entry.get("published_parsed")
                            else datetime.now(timezone.utc),
                        query=f"rss:{feed_url}",
                        run_id=state.run_id,
                    )
                    state.raw_hits.append(hit)
            except Exception as exc:
                state.errors.append(f"rss_node({feed_url}): {exc}")

    return state


# ---------------------------------------------------------------------------
# Node: NormalizeNode – canonicalise URLs, drop obvious dupes by URL
# ---------------------------------------------------------------------------

def normalize_node(state: PipelineState) -> PipelineState:
    seen = set()
    unique = []
    for hit in state.raw_hits:
        canon = canonicalize(str(hit.url))
        if canon in seen:
            continue
        seen.add(canon)
        hit.url = HttpUrl(canon)  # type: ignore[assignment]
        unique.append(hit)
    state.raw_hits = unique
    return state


# ---------------------------------------------------------------------------
# Node: DedupNode – near‑duplicate detection via MinHash LSH
# ---------------------------------------------------------------------------

async def dedup_node(state: PipelineState) -> PipelineState:
    """Keep only the first occurrence of near‑duplicate articles."""
    unique_hits = []
    for hit in state.raw_hits:
        if await _is_duplicate(str(hit.url), hit.title):
            continue
        unique_hits.append(hit)
    state.raw_hits = unique_hits
    return state


# ---------------------------------------------------------------------------
# Registration helper for the sub‑graph
# ---------------------------------------------------------------------------

from langgraph.graph import StateGraph

def register_fetcher_subgraph(graph: StateGraph) -> None:
    """Add the four fetcher nodes in sequence."""
    graph.add_node("search", "src.fetcher.search_node")
    graph.add_node("rss", rss_node)
    graph.add_node("normalize", normalize_node)
    graph.add_node("dedup", dedup_node)

    graph.add_edge("search", "rss")
    graph.add_edge("rss", "normalize")
    graph.add_edge("normalize", "dedup")