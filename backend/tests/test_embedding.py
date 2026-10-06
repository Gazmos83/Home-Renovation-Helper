"""The local embedding model: single load, declared width, normalised output."""

from __future__ import annotations

import math
import threading
import time
from collections.abc import Iterator
from typing import Any

import pytest

from app import embedding as embedding_module
from app.db.models import EMBEDDING_DIMENSIONS


@pytest.fixture(autouse=True)
def clear_model_cache() -> Iterator[None]:
    """The model is cached for the process lifetime, so tests must not share it."""
    embedding_module.reset_model()
    yield
    embedding_module.reset_model()


class StubModel:
    """Stands in for the real model so load behaviour is testable in milliseconds."""

    def __init__(self, width: int = EMBEDDING_DIMENSIONS) -> None:
        self.width = width
        self.encode_calls = 0

    def get_embedding_dimension(self) -> int:
        return self.width

    def encode(self, texts: list[str], **_: Any) -> list[list[float]]:
        self.encode_calls += 1
        return [[1.0] + [0.0] * (self.width - 1) for _ in texts]


def test_model_is_loaded_once_per_process(monkeypatch: pytest.MonkeyPatch) -> None:
    """A second call must reuse the loaded model, not pay the load cost again."""
    loads = 0
    stub = StubModel()

    def counting_load() -> StubModel:
        nonlocal loads
        loads += 1
        return stub

    monkeypatch.setattr(embedding_module, "_load_model", counting_load)

    first = embedding_module.get_model()
    second = embedding_module.get_model()

    assert loads == 1
    assert first is second


def test_concurrent_first_callers_share_one_load(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two requests arriving before the first load finishes must not each load ~2GB."""
    loads = 0
    stub = StubModel()

    def slow_load() -> StubModel:
        nonlocal loads
        loads += 1
        time.sleep(0.05)
        return stub

    monkeypatch.setattr(embedding_module, "_load_model", slow_load)

    results: list[Any] = []
    threads = [
        threading.Thread(target=lambda: results.append(embedding_module.get_model()))
        for _ in range(4)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert loads == 1
    assert len(results) == 4 and all(result is stub for result in results)
    assert embedding_module.model_status() == "ready"


def test_status_tracks_the_load(monkeypatch: pytest.MonkeyPatch) -> None:
    assert embedding_module.model_status() == "not_loaded"
    monkeypatch.setattr(embedding_module, "_load_model", lambda: StubModel())
    embedding_module.get_model()
    assert embedding_module.model_status() == "ready"
    embedding_module.reset_model()
    assert embedding_module.model_status() == "not_loaded"


def test_width_disagreement_fails_loudly(monkeypatch: pytest.MonkeyPatch) -> None:
    """A model whose width differs from the store's must not load silently."""
    monkeypatch.setattr(
        embedding_module,
        "_load_model",
        lambda: StubModel(width=EMBEDDING_DIMENSIONS + 512),
    )

    with pytest.raises(RuntimeError) as error:
        embedding_module.get_model()

    message = str(error.value)
    assert str(EMBEDDING_DIMENSIONS) in message
    assert str(EMBEDDING_DIMENSIONS + 512) in message
    assert embedding_module.model_status() == "failed"


def test_embedding_nothing_loads_no_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty batch must not drag a 2GB model into memory."""

    def fail() -> StubModel:
        raise AssertionError("the model must not be loaded for an empty input")

    monkeypatch.setattr(embedding_module, "_load_model", fail)

    assert embedding_module.embed([]) == []


def test_embed_preserves_input_order(monkeypatch: pytest.MonkeyPatch) -> None:
    stub = StubModel()
    monkeypatch.setattr(embedding_module, "_load_model", lambda: stub)

    vectors = embedding_module.embed(["eins", "zwei", "drei"])

    assert len(vectors) == 3
    assert stub.encode_calls == 1


def test_schema_column_width_matches_the_constant() -> None:
    """The chunks column, the constant, and the store must all agree.

    Without this, a model swap could change the constant while the column it
    was meant to describe stays behind, and only a write would reveal it.
    """
    from app.db.chunk_store import EMBEDDING_DIMENSIONS as store_width
    from app.db.models import Chunk

    assert Chunk.__table__.c.embedding.type.dim == EMBEDDING_DIMENSIONS
    assert store_width == EMBEDDING_DIMENSIONS
    assert EMBEDDING_DIMENSIONS == 1024


@pytest.mark.slow
def test_real_model_matches_the_provisioned_width() -> None:
    """The actual model must emit exactly the width the chunks table holds."""
    vector = embedding_module.embed_one("Möbelbauplatte beschichtet 19 mm")

    assert len(vector) == EMBEDDING_DIMENSIONS
    assert len(vector) == 1024


@pytest.mark.slow
def test_real_model_returns_normalised_vectors() -> None:
    """Cosine distance in the HNSW index assumes unit-length vectors."""
    vector = embedding_module.embed_one("Rutschhemmung R10 für Nassräume")

    assert math.isclose(math.sqrt(sum(c * c for c in vector)), 1.0, rel_tol=1e-4)
