"""Local embedding model access.

The corpus is German and shoppers may ask in English, so the model has to be
multilingual: `bge-m3` retrieves German content from English questions that
share no vocabulary with it (design.md decision 1). It runs on CPU, so nothing
here needs a GPU.

Loading costs tens of seconds and ~2GB resident, so the model is loaded once
per process, under a lock: two requests arriving before the first load finishes
must share one load, not each pay for their own copy. Nothing loads it at
import time, and nothing loads it unless something embeds.
`sentence_transformers` is imported lazily for the same reason — importing this
module must stay cheap.

Tests install a deterministic `Embedder` with `set_embedder`; production never
does, so `embed` always reaches the real model.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Sequence
from typing import Any, Final, Literal, Protocol

from app.db.models import EMBEDDING_DIMENSIONS

logger = logging.getLogger(__name__)

MODEL_NAME: Final = "BAAI/bge-m3"

# Vectors are normalised at encode time so cosine distance reduces to a dot
# product — which is exactly what the HNSW `vector_cosine_ops` index is built
# for. Storing unnormalised vectors would make the index's distances wrong.
NORMALIZE: Final = True

# Small batches: the target machine has ~7GB free and peaked at 2.6GB during
# the benchmark. Larger batches buy little on CPU and risk the headroom.
DEFAULT_BATCH_SIZE: Final = 4


def _load_model() -> Any:
    """Construct the model.

    Kept as its own function so tests can substitute a stub here rather than
    reaching into the cache below.
    """
    from sentence_transformers import SentenceTransformer

    logger.info("loading embedding model %s", MODEL_NAME)
    return SentenceTransformer(MODEL_NAME)


ModelStatus = Literal["not_loaded", "loading", "ready", "failed"]

_LOAD_LOCK = threading.Lock()
_model: Any | None = None
_status: ModelStatus = "not_loaded"


def model_status() -> ModelStatus:
    """Where the process-wide model is: what /health reports as readiness."""
    return _status


def reset_model() -> None:
    """Forget the loaded model. For tests, which must not share one."""
    global _model, _status
    with _LOAD_LOCK:
        _model = None
        _status = "not_loaded"


def get_model() -> Any:
    """Return the process-wide model, loading it on first use.

    Double-checked under a lock: the fast path is a plain read once loaded,
    and concurrent first callers wait for one load rather than starting their
    own. The width check is the guard that makes a model swap fail loudly
    here rather than as a malformed write against the store much later.
    """
    global _model, _status
    if _model is not None:
        return _model
    with _LOAD_LOCK:
        if _model is None:
            _status = "loading"
            try:
                model = _load_model()
                width = model.get_embedding_dimension()
                if width != EMBEDDING_DIMENSIONS:
                    raise RuntimeError(
                        f"{MODEL_NAME} produces {width}-dimensional embeddings but the "
                        f"store is provisioned for {EMBEDDING_DIMENSIONS}. Change "
                        f"EMBEDDING_DIMENSIONS and migrate the chunks table together, or "
                        f"the two will disagree silently."
                    )
            except BaseException:
                _status = "failed"
                raise
            _model = model
            _status = "ready"
    return _model


class Embedder(Protocol):
    """Anything that turns texts into `EMBEDDING_DIMENSIONS`-wide, normalised vectors."""

    def __call__(self, texts: Sequence[str]) -> list[list[float]]: ...


_override: Embedder | None = None


def set_embedder(embedder: Embedder | None) -> None:
    """Install (or, with `None`, remove) a stand-in embedder. For tests."""
    global _override
    _override = embedder


def embed(
    texts: Sequence[str], *, batch_size: int = DEFAULT_BATCH_SIZE
) -> list[list[float]]:
    """Embed texts, preserving order. An empty input embeds to nothing."""
    if not texts:
        return []
    if _override is not None:
        return _override(texts)
    vectors = get_model().encode(
        list(texts), normalize_embeddings=NORMALIZE, batch_size=batch_size
    )
    return [[float(component) for component in vector] for vector in vectors]


def embed_one(text: str) -> list[float]:
    """Embed a single text — the query-side convenience over `embed`."""
    return embed([text])[0]
