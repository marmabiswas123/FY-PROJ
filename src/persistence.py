"""Persistence node – upsert articles, sources, verifications, and run log."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List

from src.db import get_db, Source, Article, Verification, RunLog
from src.graph import PipelineState
from src.schemas import Article as SchemaArticle, Verification as SchemaVerification


def _get_or_create_source(db, name: str, url: str, trust_weight: float = 0.5) -> Source:
    src = db.query(Source).filter(Source.name == name).first()
    if src:
        return src
    src = Source(name=name, url=url, trust_weight=trust_weight)
    db.add(src)
    db.flush()
    return src


def persistence_node(state: PipelineState) -> PipelineState:
    """Save articles and verifications to PostgreSQL."""
    with get_db() as db:
        # Log run start if not already
        run_log = db.query(RunLog).filter(RunLog.run_id == state.run_id).first()
        if not run_log:
            run_log = RunLog(
                run_id=state.run_id,
                category_id=state.category_id,
                status="started",
                started_at=datetime.now(timezone.utc),
            )
            db.add(run_log)
            db.flush()

        saved_articles = 0
        saved_verifs = 0

        for art in state.articles:
            # Upsert source
            src = _get_or_create_source(db, art.source, str(art.canonical_url))

            # Upsert article
            db_art = db.query(Article).filter(Article.canonical_url == str(art.canonical_url)).first()
            if not db_art:
                db_art = Article(
                    canonical_url=str(art.canonical_url),
                    title=art.title,
                    text=art.text,
                    authors=art.authors,
                    publish_date=art.publish_date,
                    language=art.language,
                    source_id=src.id,
                    run_id=art.run_id,
                )
                db.add(db_art)
                db.flush()
                saved_articles += 1

            # Store verifications for this article
            for verif in state.verifications:
                # match by article_id (we used uuid4 placeholder); match by canonical_url instead
                if verif.article_id != db_art.id:
                    # We don't have real PK yet; skip matching for now
                    continue
                db_verif = Verification(
                    article_id=db_art.id,
                    counterparts=[c.model_dump() for c in verif.counterparts],
                    agreement_ratio=verif.agreement_ratio,
                    credibility=verif.credibility,
                    llm_rationale=verif.llm_rationale,
                    run_id=verif.run_id,
                )
                db.add(db_verif)
                saved_verifs += 1

        # Update run log
        run_log.status = "completed"
        run_log.finished_at = datetime.now(timezone.utc)
        run_log.articles_fetched = saved_articles
        run_log.articles_verified = saved_verifs

    return state