# Project Plan: Multi‑Agent News Verification System

## 1️⃣ High‑Level Architecture (LangGraph State‑Graph)

```
┌─────────────────────┐
│  Scheduler (cron)   │
└───────┬─────────────┘
        │ trigger
        ▼
┌─────────────────────┐   ┌───────────────────────┐
│  Category Router    │──►│  News‑Fetcher Agent   │ (one per category)
└───────┬─────────────┘   └───────┬───────────────┘
        │                         │
        │  raw URLs + meta        │  clean text + metadata
        ▼                         ▼
┌─────────────────────┐   ┌───────────────────────┐
│  Dedup / Cache      │   │  Fact‑Check Agent     │ (parallel per source)
└───────┬─────────────┘   └───────┬───────────────┘
        │                         │
        │  unique articles        │  verification payloads
        ▼                         ▼
┌─────────────────────┐   ┌───────────────────────┐
│  Scoring / Aggregator│──►│  Persistence Layer    │ (PostgreSQL / ES)
└───────┬─────────────┘   └───────┬───────────────┘
        │                         │
        │  final record           │  query / dashboard
        ▼                         ▼
┌─────────────────────┐   ┌───────────────────────┐
│  Alert / API Layer  │   │  Monitoring / Eval    │
└─────────────────────┘   └───────────────────────┘
```

*Each box = a **LangGraph node** (or a sub‑graph).  
Edges carry typed Pydantic models → strong contracts, easy testing.*

---

## 2️⃣ Toolbox – Libraries & Services

| Need | Recommended Tool / Library | Why |
|------|----------------------------|-----|
| Web search (generic, news‑specific) | **SerpAPI**, **Bing News API**, **Google Custom Search JSON API**, **NewsAPI.org**, **GNews** | Reliable, paginated, returns title / url / source / publishedAt |
| RSS / Atom feeds | `feedparser` + curated feed list per category | Near‑real‑time, no rate‑limit |
| HTML → clean article text | **trafilatura** (fast, robust) *or* **newspaper3k** (fallback) | Handles paywalls, boilerplate, extracts author/date |
| Metadata extraction (schema.org, OpenGraph, JSON‑LD) | `extruct` + `w3lib` | Gives canonical URL, publish date, canonical source |
| Language detection | `fasttext` / `langdetect` | Filter / route non‑English articles |
| Deduplication / near‑duplicate detection | **MinHash + LSH** (`datasketch`) on article text + URL canonicalisation | Prevents re‑processing same story from multiple feeds |
| Entity / topic tagging (optional) | `spaCy` + custom NER or **LangChain** `LLMChain` with a “topic‑classifier” prompt | Enables finer‑grained routing |
| Fact‑checking / cross‑source verification | Custom LLM prompt + retrieval (same search APIs) + semantic similarity (`sentence‑transformers` + FAISS) | Core verification logic |
| Credibility / bias scoring | **Media Bias/Fact Check (MBFC) dataset** + **NewsGuard** (if license) + LLM‑based stance detection | Gives a numeric trust weight per outlet |
| Persistence | **PostgreSQL** (relational, ACID) + **pgvector** for embeddings *or* **ElasticSearch** (full‑text + vector) | Queryable, scalable, supports hybrid search |
| Scheduling / orchestration | **APScheduler** or **Celery Beat** → triggers LangGraph entry node | Decouples cron from graph execution |
| Observability | **LangSmith** (trace), **Prometheus + Grafana**, **Sentry** | Debug, latency, cost tracking |
| Secrets / config | **pydantic‑settings** + **dotenv** / **AWS Secrets Manager** | Secure API keys |
| Testing | **pytest**, **langchain‑testing** utilities, **hypothesis** for property‑based tests | Guarantees contract stability |
## 3️⃣ Detailed Work‑Packages (WP)

| WP | Deliverable | Key Steps | Dependencies |
|----|--------------|-----------|--------------|
| **WP‑0** – Project scaffolding | Repo, CI/CD, Dockerfile, `pyproject.toml` (poetry/uv) | Lint (ruff), type‑check (mypy), pre‑commit | – |
| **WP‑1** – Config & Secrets | `settings.py` (pydantic‑settings) | Load API keys, LLM endpoint, DB URL, category list | WP‑0 |
| **WP‑2** – Category Registry | `categories.yaml` → `Category(id, name, keywords, rss_feeds, search_queries)` | Human‑editable, version‑controlled | WP‑1 |
| **WP‑3** – Scheduler → LangGraph entry node | `scheduler.py` (APScheduler) → `graph.invoke({"run_id": uuid})` | One‑shot per category or global batch | WP‑2 |
| **WP‑4** – News‑Fetcher Sub‑graph (per category) | Nodes: `SearchNode`, `RSSNode`, `NormalizeNode`, `DedupNode` | • Build search queries from `keywords` <br>• Pull RSS in parallel <br>• Canonicalise URL (strip utm, www) <br>• MinHash dedup (store hash in Redis) | WP‑2, WP‑1 (search APIs) |
| **WP‑5** – Content‑Extractor Node | `extract_article(url) → Article(text, title, authors, publish_date, lang, raw_html)` | • `trafilatura.fetch_url` → `extract` <br>• Fallback to `newspaper3k` <br>• Language filter (keep en + configurable) | WP‑4 |
| **WP‑6** – Fact‑Check Sub‑graph | Nodes: `RetrieveCounterpartsNode`, `CompareNode`, `ScoreNode` | • For each article, query *k* other sources (search API with title+date) <br>• Pull top‑N counterpart articles <br>• Embed both texts (sentence‑transformers) → cosine similarity <br>• LLM prompt: “Given article A and B, list factual agreements / contradictions.” <br>• Aggregate: agreement_ratio, source_trust_weight → final credibility ∈[0,1] | WP‑5, search APIs, embedding model |
| **WP‑7** – Persistence Layer | SQLAlchemy models + Alembic migrations + vector index (pgvector) | Tables: `Article`, `Source`, `Verification`, `RunLog` <br>Upsert on canonical_url | WP‑5, WP‑6 |
| **WP‑8** – Alert / API Layer | FastAPI endpoints: `/articles?category=&min_score=`, `/verify/{id}`, websocket for live alerts | Serve dashboard / downstream consumers | WP‑7 |
| **WP‑9** – Observability & Evaluation | LangSmith project, Prometheus metrics (`articles_fetched`, `verification_latency`), unit/integration tests | Golden‑set of 200 manually labelled stories for regression | WP‑3‑WP‑8 |
## 4️⃣ Data Contracts (Pydantic models)

```python
# schemas.py
from pydantic import BaseModel, HttpUrl
from datetime import datetime
from typing import List, Optional
from uuid import UUID

class RawHit(BaseModel):
    url: HttpUrl
    title: str
    source: str
    published_at: datetime
    query: str
    run_id: UUID

class Article(BaseModel):
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
    article: Article
    similarity: float
    trust_weight: float

class Verification(BaseModel):
    article_id: UUID
    counterparts: List[Counterpart]
    agreement_ratio: float
    credibility: float
    llm_rationale: str
    run_id: UUID
```

All nodes accept/produce these models → static‑type safety, easy unit testing.

---

## 5️⃣ LLM‑Centric Prompts (LangChain `PromptTemplate`)

| Prompt name | Purpose | Example skeleton |
|-------------|---------|------------------|
| `topic_classifier` | Map raw title → category (fallback) | `"Classify the news title into one of: {categories}. Title: {title}"` |
| `extract_claims` | Pull atomic factual claims from article text | `"Extract a bullet list of verifiable claims from the following article:\n{text}"` |
| `compare_claims` | Given two claim‑lists, output agreements / contradictions | `"Claims A: {claims_a}\nClaims B: {claims_b}\nReturn JSON {agreements:[], contradictions:[]}"` |
| `credibility_score` | Fuse agreement_ratio + source trust → final score + rationale | `"Agreement: {agree}, SourceTrust: {trust}. Output JSON {score:0.x, rationale:'...'}"` |

All prompts live under `prompts/` and are version‑controlled.

---

## 6️⃣ Scaling & Resilience Considerations

| Concern | Mitigation |
|---------|------------|
| Rate limits on search APIs | Token‑bucket per provider (async `asyncio.Semaphore`), exponential back‑off, fallback to RSS |
| Paywalled / blocked pages | `trafilatura` respects `robots.txt`; keep a “failed‑url” table for retry with textise dot iitty |
| LLM cost | Cache embeddings (pgvector) + verification results keyed by `(canonical_url, counterpart_url)`; batch LLM calls (max 5 per request) |
| Schema drift | Pydantic `model_config = ConfigDict(extra='forbid')` + CI test that serialises/deserialises sample payloads |
| Multi‑language | Detect language early; spin a separate translation node (via `deep_translator` or LLM) before verification |
| Human‑in‑the‑loop | Expose low‑confidence (`credibility < 0.5`) items to a review UI; feed back as labeled data for prompt tuning |

---

## 7️⃣ Optional Extensions (future sprints)

1. **Trend detection** – sliding‑window clustering of embeddings → emerging topics.  
2. **Explainable UI** – highlight matching / contradictory sentences side‑by‑side.  
3. **Fine‑tuned verifier** – train a small classifier on the golden set to replace the LLM compare step for latency‑critical paths.  
4. **Knowledge‑graph enrichment** – link entities to Wikidata for richer context.

---

## 8️⃣ Next Steps (Plan‑Mode)

1. Confirm / refine the category list (≈10‑20 topics) and any region‑specific sources.  
2. Pick search provider(s) – do you already have API keys for SerpAPI / NewsAPI / Bing?  
3. Choose LLM host – OpenAI, Anthropic, or self‑hosted (vLLM / Ollama).  
4. Decide on persistence – PostgreSQL + pgvector (single‑node start) or ElasticSearch.  
5. Set up a minimal repo (WP‑0) so we can start implementing WP‑1 → WP‑4 in the first sprint.
| **WP‑10** – Documentation & Runbooks | `README`, `ARCHITECTURE.md`, `DEPLOY.md`, `ONCALL.md` | Enable hand‑off | All