"""ScoreNode – final credibility score using agreement ratio and source trust."""
from __future__ import annotations

import json
import numpy as np
from uuid import uuid4

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from src.config import settings
from src.graph import PipelineState
from src.schemas import Article, Counterpart, Verification


_score_prompt = ChatPromptTemplate.from_template(
    "Agreement ratio: {agree:.2f}. Source trust weight: {trust:.2f}.\n"
    "Output JSON: {{\"score\": 0.x, \"rationale\": \"...\"}}"
)

_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=settings.openai_api_key)
_score_chain = _score_prompt | _llm


async def score_node(state: PipelineState) -> PipelineState:
    """Produce Verification objects for each article."""
    verifications = []

    for article in state.articles:
        counterparts = getattr(article, "_counterparts", [])
        agreement_ratio = getattr(article, "_agreement_ratio", 0.0)
        avg_trust = np.mean([c.trust_weight for c in counterparts]) if counterparts else 0.5

        score_resp = await _score_chain.ainvoke(
            {"agree": agreement_ratio, "trust": avg_trust}
        )
        score_data = json.loads(score_resp.content)

        verif = Verification(
            article_id=uuid4(),  # replace with DB PK later
            counterparts=counterparts,
            agreement_ratio=agreement_ratio,
            credibility=score_data["score"],
            llm_rationale=score_data["rationale"],
            run_id=state.run_id,
        )
        verifications.append(verif)

    state.verifications = verifications
    return state