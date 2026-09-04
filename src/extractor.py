"""Content‑Extractor node (WP‑5) – fetch & clean article HTML → structured Article."""
from __future__ import annotations

import trafilatura
from langdetect import detect, LangDetectException
from newspaper import Article as NewspaperArticle

from src.graph import PipelineState
from src.schemas import Article, RawHit


async def extract_node(state: PipelineState) -> PipelineState:
    """Convert each RawHit into a full Article using trafilatura (fallback newspaper3k)."""
    articles: list[Article] = []

    for hit in state.raw_hits:
        try:
            # 1️⃣ Try trafilatura (fast, no JS)
            downloaded = trafilatura.fetch_url(str(hit.url))
            if downloaded:
                extracted = trafilatura.extract(
                    downloaded,
                    include_comments=False,
                    include_tables=False,
                    output_format="json",
                    with_metadata=True,
                )
                if extracted:
                    import json
                    meta = json.loads(extracted)
                    text = meta.get("text", "")
                    title = meta.get("title", hit.title)
                    authors = meta.get("author", "").split(", ") if meta.get("author") else []
                    publish_date = meta.get("date")
                    if publish_date:
                        from dateutil import parser as dtparser
                        publish_date = dtparser.isoparse(publish_date)
                    else:
                        publish_date = hit.published_at
                else:
                    raise ValueError("trafilatura returned no content")
            else:
                raise ValueError("fetch_url returned None")

        except Exception:
            # 2️⃣ Fallback to newspaper3k
            try:
                paper = NewspaperArticle(str(hit.url))
                paper.download()
                paper.parse()
                text = paper.text
                title = paper.title or hit.title
                authors = paper.authors
                publish_date = paper.publish_date or hit.published_at
            except Exception as exc:
                state.errors.append(f"extract_node({hit.url}): {exc}")
                continue

        # Language filter – keep English + configurable others
        try:
            lang = detect(text[:500])
        except LangDetectException:
            lang = "unknown"
        if lang != "en":
            continue  # skip non‑English for now

        article = Article(
            canonical_url=hit.url,
            title=title,
            text=text,
            authors=authors,
            publish_date=publish_date,
            language=lang,
            source=hit.source,
            run_id=state.run_id,
        )
        articles.append(article)

    state.articles = articles
    return state