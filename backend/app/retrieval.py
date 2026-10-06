"""Question in, attributed chunks out.

The store takes vectors; a question is text. This is the seam that joins them,
kept out of `chunk_store` so the store stays testable with fixed vectors and
free of any dependency on a 2GB model.

Relevance threshold: measured, not guessed. Against the ingested toom corpus,
chunks that genuinely answer a question score above it and questions the
corpus cannot answer fall below — see `docs/retrieval-benchmark.md` in the
change for the run these numbers come from.
"""

from __future__ import annotations

import logging
from collections.abc import Collection
from typing import Final

from sqlalchemy.orm import Session

from app.db.chunk_store import SearchHit, search_hybrid, search_similar
from app.embedding import embed_one

logger = logging.getLogger(__name__)

# Measured against the ingested toom corpus, not guessed. Seven questions the
# corpus can answer scored 0.535-0.731 by vector and 0.374-0.811 hybrid; four
# it cannot (flights, medicine, cooking, CSS) peaked at 0.435 and 0.304. These
# sit in the gap. The two modes need separate values because a hybrid score is
# a weighted blend on a different scale — one constant would silently be
# strict in one mode and useless in the other.
MIN_RELEVANCE_VECTOR: Final = 0.48
MIN_RELEVANCE_HYBRID: Final = 0.34


def search_knowledge(
    session: Session,
    question: str,
    *,
    limit: int = 5,
    sources: Collection[str] | None = None,
    categories: Collection[str] | None = None,
    min_relevance: float | None = None,
    hybrid: bool = True,
) -> list[SearchHit]:
    """Retrieve chunks that answer `question`.

    Returning nothing is a valid answer: it is what lets the agent say it does
    not know rather than assemble a specification out of the nearest text.
    """
    if not question.strip():
        return []

    vector = embed_one(question)
    if min_relevance is None:
        min_relevance = MIN_RELEVANCE_HYBRID if hybrid else MIN_RELEVANCE_VECTOR

    if hybrid:
        hits = search_hybrid(
            session, vector, question, limit=limit, sources=sources, categories=categories
        )
    else:
        hits = search_similar(session, vector, limit=limit, sources=sources)

    if min_relevance is not None:
        hits = [hit for hit in hits if hit.similarity >= min_relevance]

    logger.info(
        "retrieved %d chunks for a %d-character question", len(hits), len(question)
    )
    return hits
