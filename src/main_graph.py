"""Build the full LangGraph pipeline connecting all sub‑graphs."""
from __future__ import annotations

from langgraph.graph import StateGraph

from src.graph import PipelineState, build_graph
from src.fetcher_nodes import register_fetcher_subgraph
from src.extractor import extract_node
from src.factcheck import register_factcheck_subgraph
from src.persistence import persistence_node


def build_full_graph() -> StateGraph:
    """Construct the end‑to‑end graph."""
    graph = build_graph()

    # 1. Fetcher sub‑graph (search → rss → normalize → dedup)
    register_fetcher_subgraph(graph)

    # 2. Extractor node
    graph.add_node("extract", extract_node)

    # 3. Fact‑check sub‑graph
    register_factcheck_subgraph(graph)

    # 4. Persistence node
    graph.add_node("persist", persistence_node)

    # Wire edges
    graph.add_edge("dedup", "extract")
    graph.add_edge("extract", "retrieve_counterparts")  # first node of factcheck subgraph
    graph.add_edge("score_verification", "persist")
    graph.add_edge("persist", "__end__")

    # Set entry point
    graph.set_entry_point("search")
    return graph


# Compiled graph instance for reuse
compiled_graph = build_full_graph().compile()