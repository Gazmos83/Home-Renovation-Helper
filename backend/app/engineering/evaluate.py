"""Repeatable real-embedding acceptance measurement, only in a test database.

All fixture writes are rolled back. No cloud model, renderer or real document is
called. Development tuning is separated from held-out reporting.
"""

import argparse
import hashlib
import json
import statistics
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from types import SimpleNamespace

import yaml
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.config import load_settings
from app.db.session import make_engine
from app.embedding import MODEL_NAME, get_model
from app.engineering.chat import render_answer
from app.engineering.ingest import ingest_version
from app.engineering.registry import add_property, decide_rights, register_source
from app.engineering.retrieval import search_engineering
from app.engineering.schemas import (
    EvidenceBlock,
    PropertyIn,
    RightsIn,
    Scope,
    SearchIn,
    SourceIn,
)

FIXTURES = Path(__file__).resolve().parents[2] / "tests/fixtures/engineering_eval.yaml"


def evaluate(session, root, data):
    started = perf_counter()
    get_model()  # No fake_embedder; cold initialization is measured separately.
    cold_ms = (perf_counter() - started) * 1000
    ids, keys = {}, {}
    for source in data["sources"]:
        version = register_source(
            session,
            SourceIn.model_validate(
                {key: source[key] for key in ("key", "metadata", "collections")}
            ),
        )
        ids[source["key"]] = str(version.id)
        keys[str(version.id)] = source["key"]
        if source.get("rights") == "metadata_only":
            continue
        grants = {scope: {} for scope in Scope if scope != Scope.COMMERCIAL}
        if source.get("rights") == "local_only":
            del grants[Scope.REMOTE]
        decide_rights(
            session,
            version.id,
            RightsIn(
                action="approve",
                reviewer="original fixture author",
                evidence="Original synthetic project fixtures; permission for the listed test operations only",
                grants=grants,
            ),
        )
        block = EvidenceBlock(
            block_id="row-1",
            kind="table",
            content=source["text"],
            pages=[1],
            section="Synthetic fixture",
            headers=source["headers"],
            conditions=source["conditions"],
            verification_status="verified",
            reviewed_by="fixture author",
        )
        run = ingest_version(
            session,
            SimpleNamespace(guideline_root=root),
            version.id,
            reviewed_blocks=[block],
        )
        if run.state != "published":
            raise RuntimeError(run.reason)
        if source.get("property"):
            add_property(
                session,
                version.id,
                PropertyIn.model_validate(
                    {
                        **source["property"],
                        "block_id": "row-1",
                        "page_section": "p. 1 Synthetic fixture",
                        "conditions": {"fixture": "; ".join(source["conditions"])},
                        **{
                            key: source["metadata"].get(key)
                            for key in (
                                "standard_or_model",
                                "material_grade",
                                "thickness_mm",
                            )
                        },
                    }
                ),
            )
        if source.get("rights") == "revoked":
            decide_rights(
                session,
                version.id,
                RightsIn(
                    action="revoke",
                    reviewer="fixture author",
                    evidence="Withdrawn before evaluation",
                ),
            )

    timings, results = [], []
    for mode in ("hybrid", "vector", "keyword"):
        raw = []
        for case in data["cases"]:
            started = perf_counter()
            response = search_engineering(
                session,
                SearchIn(
                    query=case["query"],
                    filters=case["filters"],
                    mode=mode,
                    limit=5,
                    min_relevance=0,
                ),
            )
            timings.append((perf_counter() - started) * 1000)
            raw.append((case, response))
        # Choose a threshold only on development positives. Zero avoids using
        # an unmeasured retailer cutoff. A drop in recall disqualifies a choice.
        candidates = [0, 0.1, 0.2, 0.3, 0.4, 0.5]

        def dev_recall(threshold, raw=raw):
            positive = [
                (case, response)
                for case, response in raw
                if case["split"] == "development" and case["expected"]
            ]
            return statistics.mean(
                len(
                    set(case["expected"])
                    & {
                        keys[hit["version_id"]]
                        for hit in response["evidence"]
                        if hit["score"] >= threshold
                    }
                )
                / len(case["expected"])
                for case, response in positive
            )

        best = max(dev_recall(threshold) for threshold in candidates)
        threshold = max(value for value in candidates if dev_recall(value) == best)
        cases = []
        for case, response in raw:
            hits = [hit for hit in response["evidence"] if hit["score"] >= threshold]
            got = {keys[hit["version_id"]] for hit in hits}
            recall = (
                len(got & set(case["expected"])) / len(case["expected"])
                if case["expected"]
                else None
            )
            completeness = all(
                hit["block"]["pages"] == [1]
                and hit["block"]["headers"]
                and hit["block"]["conditions"]
                and hit["metadata"]["title"]
                and all(
                    prop["page_section"]
                    and prop["original_unit"]
                    and prop["conditions"]
                    for prop in hit["properties"]
                )
                for hit in hits
            )
            ids_this_turn = [hit["evidence_id"] for hit in hits]
            answer = render_answer(
                json.dumps(
                    {
                        "evidence_ids": ids_this_turn,
                        "property_ids": [
                            prop["id"] for hit in hits for prop in hit["properties"]
                        ],
                    }
                ),
                session,
                ids_this_turn,
                case["query"],
                enabled=True,
            )
            false_verified = (
                "NOT VERIFIED" not in answer or "not implemented" not in answer
            )
            denied = (
                len(got - set(case["expected"]))
                if not case["expected"]
                else len(got & {"eval-denied", "eval-local", "eval-standard"})
            )
            cases.append(
                {
                    "id": case["id"],
                    "split": case["split"],
                    "language": case["language"],
                    "retrieved": sorted(got),
                    "recall_at_5": recall,
                    "citation_condition_complete": bool(completeness),
                    "ineligible_returns": denied,
                    "false_verified": false_verified,
                }
            )
        results.append(
            {
                "mode": mode,
                "development_threshold": threshold,
                "development_recall_at_5": best,
                "held_out_recall_at_5": statistics.mean(
                    case["recall_at_5"]
                    for case in cases
                    if case["split"] == "held_out" and case["recall_at_5"] is not None
                ),
                "citation_condition_completeness": statistics.mean(
                    case["citation_condition_complete"] for case in cases
                ),
                "ineligible_returns": sum(case["ineligible_returns"] for case in cases),
                "false_verified": sum(case["false_verified"] for case in cases),
                "cases": cases,
            }
        )
    return {
        "embedding_model": MODEL_NAME,
        "embedding_dimensions": 1024,
        "fixture_sha256": hashlib.sha256(FIXTURES.read_bytes()).hexdigest(),
        "fixture_rights": "Original synthetic project fixtures only; fictitious products/values, not design evidence",
        "case_count": len(data["cases"]),
        "cold_model_initialization_ms": round(cold_ms, 1),
        "warm_retrieval_ms": {
            "median": round(statistics.median(timings), 1),
            "max": round(max(timings), 1),
        },
        "modes": results,
        "limitations": [
            "Small synthetic corpus, no real manufacturer/PDF validation or certified engineering methods",
            "Exact filters often leave one applicable block; this is not a broad-corpus quality guarantee",
            "Keyword recall can be lower across languages with no common tokens",
            "No real OpenRouter call; answer validation uses deliberately selected fixture IDs",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    settings = load_settings()
    url = str(settings.test_database_url or "")
    if not url or not (make_url(url).database or "").endswith("_test"):
        raise SystemExit("TEST_DATABASE_URL must name a designated *_test database")
    engine = make_engine(url)
    try:
        with (
            Session(engine) as session,
            TemporaryDirectory(prefix="engineering-eval-") as root,
        ):
            try:
                result = evaluate(
                    session, Path(root), yaml.safe_load(FIXTURES.read_text())
                )
            finally:
                session.rollback()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n")
        print(
            json.dumps({key: value for key, value in result.items() if key != "modes"})
        )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
