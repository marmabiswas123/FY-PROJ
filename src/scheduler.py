"""APScheduler job that runs the pipeline for each category."""
from __future__ import annotations

import asyncio
import uuid
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from src.config import settings
from src.categories import load_categories
from src.main_graph import compiled_graph
from src.graph import PipelineState


async def run_pipeline_for_category(category_id: str) -> None:
    """Invoke the compiled graph for a single category."""
    initial_state = PipelineState(category_id=category_id, run_id=uuid.uuid4())
    await compiled_graph.ainvoke(initial_state)


async def scheduled_job() -> None:
    """Run pipeline for all configured categories."""
    categories = load_categories()
    for cat in categories:
        try:
            await run_pipeline_for_category(cat.id)
        except Exception as exc:
            # Log error but continue with other categories
            print(f"Category {cat.id} failed: {exc}")


def start_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        scheduled_job,
        IntervalTrigger(minutes=settings.fetch_interval_minutes),
        id="news_fetch_job",
        replace_existing=True,
    )
    scheduler.start()
    return scheduler


if __name__ == "__main__":
    import signal
    import sys

    scheduler = start_scheduler()
    print("Scheduler started. Press Ctrl+C to exit.")
    # Keep process alive
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    asyncio.get_event_loop().run_forever()