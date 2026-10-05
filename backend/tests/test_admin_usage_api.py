"""dev-panel: token usage per model per day."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.accounts import ensure_owner
from app.db.models import ModelUsage
from app.db.session import make_engine
from conftest import OWNER_EMAIL, OWNER_PASSWORD
from tests.api_helpers import sign_in
from tests.test_admin_models_api import _client

DESIGNER = "deepseek/deepseek-v4-pro-0813"


@pytest.fixture
def client(migrated_database: str, render_root: Path, fake_blender: Path) -> TestClient:
    app_client = _client(migrated_database, render_root, fake_blender, dev=True)
    sign_in(app_client)
    yield app_client
    app_client.__exit__(None, None, None)


def test_usage_today_after_three_designer_calls(
    client: TestClient, migrated_database: str
) -> None:
    engine = make_engine(migrated_database)
    with Session(engine) as session:
        owner = ensure_owner(session, OWNER_EMAIL, OWNER_PASSWORD)
        for _ in range(3):
            session.add(
                ModelUsage(
                    id=uuid4(),
                    model_id=DESIGNER,
                    operation="chat.designer",
                    input_tokens=10,
                    output_tokens=4,
                    user_id=owner.id,
                )
            )
        session.commit()
    engine.dispose()

    response = client.get("/admin/usage", params={"days": 1})
    assert response.status_code == 200
    designer = [row for row in response.json() if row["model"] == DESIGNER]
    assert designer
    assert designer[0]["input_tokens"] >= 30
    assert designer[0]["output_tokens"] >= 12
    assert designer[0]["calls"] >= 3


def test_days_over_31_is_refused(client: TestClient) -> None:
    assert client.get("/admin/usage", params={"days": 40}).status_code == 422
