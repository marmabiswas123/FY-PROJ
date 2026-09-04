"""FastAPI application for querying articles and verifications."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import FastAPI, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.db import get_db, Article, Verification, Source

app = FastAPI(title="News Verification API", version="0.1.0")


class ArticleOut(BaseModel):
    id: UUID
    canonical_url: str
    title: str
    text: str
    authors: List[str]
    publish_date: datetime
    language: str
    source_name: str
    credibility: Optional[float] = None

    class Config:
        from_attributes = True


class VerificationOut(BaseModel):
    id: UUID
    article_id: UUID
    agreement_ratio: float
    credibility: float
    llm_rationale: str
    created_at: datetime

    class Config:
        from_attributes = True


@app.get("/articles", response_model=List[ArticleOut])
def list_articles(
    category: Optional[str] = None,
    min_score: Optional[float] = Query(None, ge=0, le=1),
    limit: int = Query(20, le=100),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    q = db.query(Article).join(Source).order_by(Article.publish_date.desc())
    if category:
        # Assuming source name contains category or we have a category field; placeholder
        q = q.filter(Source.name.ilike(f"%{category}%"))
    if min_score is not None:
        # join verification for latest credibility
        subq = db.query(Verification.article_id, Verification.credibility).subquery()
        q = q.join(subq, Article.id == subq.c.article_id).filter(subq.c.credibility >= min_score)
    articles = q.offset(offset).limit(limit).all()
    result = []
    for a in articles:
        latest_verif = db.query(Verification).filter(Verification.article_id == a.id).order_by(Verification.created_at.desc()).first()
        result.append(ArticleOut(
            id=a.id,
            canonical_url=a.canonical_url,
            title=a.title,
            text=a.text,
            authors=a.authors,
            publish_date=a.publish_date,
            language=a.language,
            source_name=a.source.name,
            credibility=latest_verif.credibility if latest_verif else None,
        ))
    return result


@app.get("/articles/{article_id}", response_model=ArticleOut)
def get_article(article_id: UUID, db: Session = Depends(get_db)):
    a = db.query(Article).filter(Article.id == article_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Article not found")
    latest_verif = db.query(Verification).filter(Verification.article_id == a.id).order_by(Verification.created_at.desc()).first()
    return ArticleOut(
        id=a.id,
        canonical_url=a.canonical_url,
        title=a.title,
        text=a.text,
        authors=a.authors,
        publish_date=a.publish_date,
        language=a.language,
        source_name=a.source.name,
        credibility=latest_verif.credibility if latest_verif else None,
    )


@app.get("/verifications/{article_id}", response_model=List[VerificationOut])
def get_verifications(article_id: UUID, db: Session = Depends(get_db)):
    vers = db.query(Verification).filter(Verification.article_id == article_id).order_by(Verification.created_at.desc()).all()
    if not vers:
        raise HTTPException(status_code=404, detail="No verifications for this article")
    return vers


@app.get("/health")
def health():
    return {"status": "ok"}