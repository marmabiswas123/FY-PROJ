"""RetrieveCounterpartsNode – find other sources covering the same story."""
from __future__ import annotations

import asyncio
from typing import List

import httpx
import numpy as np
from sentence_transformers import SentenceTransformer

from src.config import settings
from src.graph import PipelineState
from src.schemas import Article, Counterpart


# Load embedder once
_embedder = SentenceTransformer("all-MiniLM-L6-v2")


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


async def retrieve_counterparts(state: PipelineState) -> PipelineState:
    """For each article, query news API with title to find counterpart articles."""
    if not settings.newsapi_key:
        state.errors.append("retrieve_counterparts: NEWSAPI_KEY not set")
        return state

    async with httpx.AsyncClient(timeout=10) as client:
        for article in state.articles:
            # Build a query from the article title (first 80 chars)
            query = f"\"{article.title[:80]}\""
            params = {
                "q": query,
                "language": "en",
                "pageSize": 5,
                "apiKey": settings.newsapi_key,
            }
            resp = await client.get("https://newsapi.org/v2/everything", params=params)
            data = resp.json()

            counterparts: List[Counterpart] = []
            art_emb = _embedder.encode(article.text[:2000])

            for hit in data.get("articles", []):
                if hit["url"] == str(article.canonical_url):
                    continue
                cp_text = hit.get("content") or hit.get("description") or ""
                if len(cp_text) < 200:
                    continue
                cp_emb = _embedder.encode(cp_text[:2000])
                sim = _cosine(art_emb, cp_emb)
                if sim < 0.5:
                    continue

                # Placeholder trust weight – replace with MBFC/NewsGuard lookup
                trust = 0.7

                cp_article = Article(
                    canonical_url=hit["url"],
                    title=hit["title"],
                    text=cp_text,
                    authors=[],
                    publish_date=hit["publishedAt"],
                    language="en",
                    source=hit["source"]["name"],
                    run_id=state.run_id,
                )
                counterparts.append(Counterpart(article=cp_article, similarity=sim, trust_weight=trust))

            # Attach counterparts to the article for downstream nodes
            article._counterparts = counterparts  # type: ignore[attr-defined]

    return state