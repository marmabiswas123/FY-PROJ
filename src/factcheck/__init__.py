"""Fact-check sub-package initialization."""
from src.factcheck.retrieve import retrieve_counterparts
from src.factcheck.compare import compare_node
from src.factcheck.score import score_node
from langgraph.graph import StateGraph

def register_factcheck_subgraph(graph: StateGraph) -> None:
    """Add the three fact-check nodes in sequence."""
    graph.add_node("retrieve_counterparts", retrieve_counterparts)
    graph.add_node("compare_claims", compare_node)
    graph.add_node("score_verification", score_node)

    graph.add_edge("retrieve_counterparts", "compare_claims")
    graph.add_edge("compare_claims", "score_verification")