# News Verification Agent

Multi‑agent system that discovers news articles for configured categories, extracts clean text, and cross‑checks each story against multiple independent sources to produce a credibility score.

## Architecture Overview

```
Scheduler → Category Router → News‑Fetcher (search + RSS) → Dedup → Extractor
      → Fact‑Check (retrieve counterparts → compare claims → score) → Persistence
```

Built with **LangGraph** for workflow orchestration, **LangChain** for LLM chains, **FastAPI** for serving results, **PostgreSQL + pgvector** for storage, and **APScheduler** for periodic runs.

## Quick Start (Docker)

```bash
# 1. Copy example env and fill in your API keys
cp .env.example .env
# edit .env with OPENAI_API_KEY, NEWSAPI_KEY, etc.

# 2. Build and start services
docker compose up --build -d

# 3. API will be available at http://localhost:8000
#    - GET /articles?category=tech&min_score=0.6
#    - GET /articles/{id}
#    - GET /verifications/{article_id}
```

## Running Locally (without Docker)

```bash
# Install dependencies (requires Poetry)
poetry install

# Start Postgres & Redis (e.g., via docker compose up -d postgres redis)

# Export env vars or create .env
export $(cat .env | xargs)

# Run one‑off pipeline for a category
python -m src run-once tech

# Or start the periodic scheduler
python -m src scheduler

# Or start the API server
python -m src api
```

## Project Structure

```
src/
  config.py          # pydantic-settings
  categories.py      # YAML category registry loader
  schemas.py         # Pydantic data contracts
  graph.py           # LangGraph state definition
  fetcher.py         # SearchNode (news API)
  fetcher_nodes.py   # RSS, Normalize, Dedup nodes
  extractor.py       # Content extraction (trafilatura + newspaper3k)
  factcheck/         # Retrieve, Compare, Score nodes
  db/                # SQLAlchemy models & session
  persistence.py     # Persistence node
  main_graph.py      # Full graph assembly
  scheduler.py       # APScheduler job
  api.py             # FastAPI endpoints
  __main__.py        # CLI entry point
```

## Configuration

Edit `categories.yaml` to add/remove topics, keywords, RSS feeds, and search queries.

## Extending

- Add new search providers in `fetcher.py`.
- Replace LLM provider in `config.py` (`llm_provider`).
- Plug in a real credibility dataset (MBFC, NewsGuard) in `factcheck/retrieve.py`.
- Add Alembic migrations for schema changes.

## License

MIT