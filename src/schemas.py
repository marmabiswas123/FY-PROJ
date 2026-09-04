"""Pydantic data contracts shared across all LangGraph nodes."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, HttpUrl


class RawHit(BaseModel):
    """A single hit coming from a search API or RSS feed."""
    model_config = ConfigDict(extra="forbid")

    url: HttpUrl
    title: str
    source: str
    published_at: datetime
    query: str          # which search query / feed produced this hit
    run_id: UUID        # correlation id for the whole pipeline run


class Article(BaseModel):
    """Fully extracted, canonical article ready for verification."""
    model_config = ConfigDict(extra="forbid")

    canonical_url: HttpUrl
    title: str
    text: str
    authors: List[str] = []
    publish_date: datetime
    language: str
    source: str
    raw_html: Optional[str] = None
    run_id: UUID


class Counterpart(BaseModel):
    """One counterpart article used for cross‑source verification."""
    model_config = ConfigDict(extra="forbid")

    article: Article
    similarity: float          # cosine similarity of embeddings (0‑1)
    trust_weight: float        # outlet credibility weight (0‑1)


class Verification(BaseModel):
    """Final verification result for one primary article."""
    model_config = ConfigDict(extra="forbid")

    article_id: UUID
    counterparts: List[Counterpart]
    agreement_ratio: float     # fraction of claims that agree
    credibility: float         # final score 0‑1
    llm_rationale: str        # human‑readable explanation
    run_id: UUID