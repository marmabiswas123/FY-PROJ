"""Entry point – run scheduler, API server, or a one‑off pipeline run."""
from __future__ import annotations

import argparse
import asyncio
import uvicorn

from src.scheduler import start_scheduler
from src.api import app
from src.main_graph import compiled_graph
from src.graph import PipelineState
from src.categories import load_categories
import uuid


async def run_once(category_id: str) -> None:
    """Run the pipeline a single time for a given category."""
    state = PipelineState(category_id=category_id, run_id=uuid.uuid4())
    await compiled_graph.ainvoke(state)
    print(f"Run completed for category {category_id}. Articles: {len(state.articles)}, Verifications: {len(state.verifications)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="News Verification Agent")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("scheduler", help="Start the periodic scheduler")
    sub.add_parser("api", help="Start the FastAPI HTTP server")
    run_once_parser = sub.add_parser("run-once", help="Run pipeline once for a category")
    run_once_parser.add_argument("category", help="Category ID (e.g., tech, health, finance)")

    args = parser.parse_args()

    if args.command == "scheduler":
        import signal
        import sys
        scheduler = start_scheduler()
        print("Scheduler started. Press Ctrl+C to exit.")
        signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
        asyncio.get_event_loop().run_forever()

    elif args.command == "api":
        uvicorn.run(app, host="0.0.0.0", port=8000)

    elif args.command == "run-once":
        asyncio.run(run_once(args.category))


if __name__ == "__main__":
    main()