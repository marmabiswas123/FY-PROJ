"""LangGraph state definition – the single source of truth flowing through the graph."""
from __future__ import annotations

from typing import Annotated, List, Optional
from uuid import UUID, uuid4

from langgraph.graph import StateGraph, END
from pydantic import BaseModel, ConfigDict, Field

from src.schemas import Article, RawHit, Verification


class PipelineState(BaseModel):
    """Immutable state passed between nodes (LangGraph uses `add_messages`‑style reducers)."""
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    # Run correlation
    run_id: UUID = Field(default_factory=uuid4)

    # Category being processed (set by router)
    category_id: Optional[str] = None

    # Raw hits collected from search + RSS
    raw_hits: Annotated[List[RawHit], "extend"] = []

    # Extracted articles (post dedup)
    articles: Annotated[List[Article], "extend"] = []

    # Verification results
    verifications: Annotated[List[Verification], "extend"] = []

    # Errors / logs
    errors: Annotated[List[str], "extend"] = []


# ---------------------------------------------------------------------------
# Graph construction helper – each work‑package will register its own nodes.
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    """Create an empty StateGraph with the correct state schema."""
    return StateGraph(PipelineState)