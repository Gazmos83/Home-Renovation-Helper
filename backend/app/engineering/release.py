"""Developer acceptance receipt; missing evidence cannot enable the feature."""

import json
from pathlib import Path

from app.config import REPO_ROOT

RECEIPT = REPO_ROOT / "config/engineering_acceptance.json"


def release_ready(path: Path = RECEIPT) -> bool:
    try:
        receipt = json.loads(path.read_text())
        return receipt.get("change") == "furniture-engineering-rag-foundation" and all(
            receipt.get(check) == "passed"
            for check in (
                "backend_checks",
                "frontend_checks",
                "browser_checks",
                "retrieval_checks",
            )
        )
    except OSError, ValueError, AttributeError:
        return False
