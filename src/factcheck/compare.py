"""CompareNode – LLM based claim comparison between primary article and counterparts."""
from __future__ import annotations

import json
from typing import List

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from src.config import settings
from src.graph import PipelineState
from src.schemas import Article


# Prompt templates
_extract_claims_prompt = ChatPromptTemplate.from_template(
    "Extract a bullet list of verifiable factual claims from the article below.\n"
    "Return JSON: {{\"claims\": [\"claim 1\", \"claim 2\", ...]}}\n\nArticle:\n{text}"
)

_compare_claims_prompt = ChatPromptTemplate.from_template(
    "You are given two lists of claims from different articles about the same event.\n"
    "Claims A: {claims_a}\nClaims B: {claims_b}\n"
    "Return JSON with two arrays: {{\"agreements\": [...], \"contradictions\": [...]}}"
)

_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=settings.openai_api_key)

_extract_chain = _extract_claims_prompt | _llm
_compare_chain = _compare_claims_prompt | _llm


async def compare_node(state: PipelineState) -> PipelineState:
    """Compare claims of each article with its counterparts."""
    for article in state.articles:
        counterparts = getattr(article, "_counterparts", [])
        if not counterparts:
            continue

        # Extract claims from primary article
        primary_claims_resp = await _extract_chain.ainvoke({"text": article.text[:3000]})
        primary_claims = json.loads(primary_claims_resp.content).get("claims", [])

        agreements = 0
        total_claims = len(primary_claims)

        for cp in counterparts:
            cp_claims_resp = await _extract_chain.ainvoke({"text": cp.article.text[:3000]})
            cp_claims = json.loads(cp_claims_resp.content).get("claims", [])

            cmp_resp = await _compare_chain.ainvoke(
                {"claims_a": primary_claims, "claims_b": cp_claims}
            )
            cmp_data = json.loads(cmp_resp.content)
            agreements += len(cmp_data.get("agreements", []))

        agreement_ratio = agreements / max(total_claims, 1)
        article._agreement_ratio = agreement_ratio  # type: ignore[attr-defined]

    return state