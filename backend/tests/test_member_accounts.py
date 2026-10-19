"""owner-auth: member accounts — the owner adds them, they never reach /admin, and each
account sees only its own house file."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent import house_file
from app.auth.accounts import (
    AccountExists,
    OwnerAccount,
    create_member,
    delete_member,
    get_owner,
    list_accounts,
)
from app.auth.passwords import WeakPassword
from app.blender import storage
from app.config import Settings
from app.db import scope as account_scope
from app.db.models import Piece, Room
from app.main import create_app
from conftest import OWNER_EMAIL, OWNER_PASSWORD
from tests.api_helpers import create, reset_owner
from tests.blender_fakes import fake_success_launch
from tests.conftest import clean_house_file

MEMBER_EMAIL = "member@example.com"
MEMBER_PASSWORD = "member-password-1"
SQUARE = [[0, 0], [3000, 0], [3000, 2000], [0, 2000]]


@pytest.fixture
def app_client(migrated_database: str, render_root: Path, fake_blender: Path) -> Iterator[TestClient]:
    settings = Settings(
        database_url=migrated_database,
        openrouter_api_key="sk-or-test",
        cors_origins="http://localhost:5173",
        owner_email=OWNER_EMAIL,
        owner_password=OWNER_PASSWORD,
        gateway_probe_enabled=False,
        render_root=render_root,
        blender_bin=fake_blender,
        dev_panel_enabled=True,
        _env_file=None,
    )
    reset_owner(migrated_database)
    app = create_app(settings)
    app.state.blender_launch = fake_success_launch()
    client = TestClient(app)
    client.__enter__()
    yield client
    client.__exit__(None, None, None)


def sign_in(client: TestClient, email: str, password: str) -> None:
    client.cookies.clear()
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text


def add_member(client: TestClient) -> str:
    sign_in(client, OWNER_EMAIL, OWNER_PASSWORD)
    response = client.post("/admin/users", json={"email": MEMBER_EMAIL, "password": MEMBER_PASSWORD})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_the_owner_adds_lists_and_removes_a_member(app_client: TestClient) -> None:
    member_id = add_member(app_client)
    listed = app_client.get("/admin/users").json()
    assert [(u["email"], u["is_owner"]) for u in listed] == [(OWNER_EMAIL, True), (MEMBER_EMAIL, False)]
    assert app_client.post("/admin/users", json={"email": MEMBER_EMAIL.upper(), "password": MEMBER_PASSWORD}).status_code == 409
    assert app_client.post("/admin/users", json={"email": "x@example.com", "password": "short"}).status_code == 422
    owner_id = listed[0]["id"]
    assert app_client.delete(f"/admin/users/{owner_id}").status_code == 409
    assert app_client.delete(f"/admin/users/{member_id}").status_code == 204
    assert [u["email"] for u in app_client.get("/admin/users").json()] == [OWNER_EMAIL]


def test_a_member_signs_in_but_never_reaches_admin(app_client: TestClient) -> None:
    add_member(app_client)
    sign_in(app_client, MEMBER_EMAIL, MEMBER_PASSWORD)
    assert app_client.get("/auth/me").json()["email"] == MEMBER_EMAIL
    assert app_client.get("/admin/users").status_code == 404
    assert app_client.get("/admin/models").status_code == 404


def test_a_member_sees_only_its_own_pieces(app_client: TestClient, render_root: Path) -> None:
    add_member(app_client)
    assert create(app_client, "owner-bench").status_code == 202
    sign_in(app_client, MEMBER_EMAIL, MEMBER_PASSWORD)
    assert app_client.get("/packages").json() == []
    assert app_client.get("/packages/owner-bench/versions/1").status_code == 404
    assert create(app_client, "member-bench").status_code == 202
    assert [p["package_id"] for p in app_client.get("/packages").json()] == ["member-bench"]
    sign_in(app_client, OWNER_EMAIL, OWNER_PASSWORD)
    assert [p["package_id"] for p in app_client.get("/packages").json()] == ["owner-bench"]


def test_a_member_reads_but_never_changes_shared_prices(app_client: TestClient) -> None:
    add_member(app_client)
    sign_in(app_client, MEMBER_EMAIL, MEMBER_PASSWORD)
    assert app_client.get("/price-list").status_code == 200
    refused = app_client.post("/price-list", json={"key": "x", "label": "x", "category": "board", "unit": "m2", "price_eur": 1})
    assert refused.status_code == 403


def test_accounts_rules(db_session: Session, migrated_database: str) -> None:
    reset_owner(migrated_database)
    with pytest.raises(RuntimeError):
        create_member(db_session, MEMBER_EMAIL, MEMBER_PASSWORD)
    from app.auth.accounts import ensure_owner

    owner = ensure_owner(db_session, OWNER_EMAIL, OWNER_PASSWORD)
    member = create_member(db_session, MEMBER_EMAIL, MEMBER_PASSWORD)
    with pytest.raises(AccountExists):
        create_member(db_session, MEMBER_EMAIL, MEMBER_PASSWORD)
    with pytest.raises(WeakPassword):
        create_member(db_session, "other@example.com", "short")
    with pytest.raises(OwnerAccount):
        delete_member(db_session, owner.id)
    assert get_owner(db_session).id == owner.id
    assert [a.email for a in list_accounts(db_session)] == [OWNER_EMAIL, MEMBER_EMAIL]
    assert delete_member(db_session, member.id) is True
    db_session.rollback()


def test_each_account_keeps_its_own_rooms_and_pieces(db_session: Session, migrated_database: str) -> None:
    reset_owner(migrated_database)
    from app.auth.accounts import ensure_owner

    ensure_owner(db_session, OWNER_EMAIL, OWNER_PASSWORD)
    member = create_member(db_session, MEMBER_EMAIL, MEMBER_PASSWORD)
    db_session.commit()
    house_file.upsert_room(db_session, "Hall", SQUARE, 2500)
    house_file.record_piece(db_session, "owner-shelf", "Shelf")
    db_session.commit()
    with account_scope.scoped(member.id):
        # The same room name is the member's own room, not the owner's.
        assert house_file.room_by_name(db_session, "Hall") is None
        house_file.upsert_room(db_session, "Hall", SQUARE, 2400)
        house_file.record_piece(db_session, "member-shelf", "Shelf")
        db_session.commit()
        db_session.expunge_all()
        assert [r.height_mm for r in db_session.scalars(select(Room))] == [2400]
        assert [p.package_id for p in db_session.scalars(select(Piece))] == ["member-shelf"]
        # The Designer's tools look pieces up through this check.
        assert house_file.piece_visible(db_session, "member-shelf")
        assert not house_file.piece_visible(db_session, "owner-shelf")
    db_session.expunge_all()
    assert [r.height_mm for r in db_session.scalars(select(Room))] == [2500]
    assert [p.package_id for p in db_session.scalars(select(Piece))] == ["owner-shelf"]
    stamped = db_session.scalars(
        select(Piece.owner_id).where(Piece.package_id == "member-shelf").execution_options(
            **{account_scope.ALL_ACCOUNTS: True}
        )
    ).one()
    assert stamped == member.id
    db_session.rollback()


def test_a_member_never_reaches_the_owners_room_or_piece_conversation(app_client: TestClient, render_root: Path) -> None:
    add_member(app_client)
    assert create(app_client, "owner-bench").status_code == 202
    folder = storage.composition_version_dir(render_root, "wohnen", 1)
    folder.mkdir(parents=True)
    sign_in(app_client, MEMBER_EMAIL, MEMBER_PASSWORD)
    assert app_client.delete("/compositions/wohnen/versions/1").status_code == 404
    assert app_client.get("/compositions/wohnen/versions/1/renders").status_code == 404
    assert app_client.get("/apartments/wohnen").status_code == 404
    assert folder.is_dir()
    refused = app_client.post("/chat/threads", json={"title": "x", "package_id": "owner-bench"})
    assert refused.status_code == 422


def test_a_member_never_duplicates_the_owners_room(app_client: TestClient, db_session: Session) -> None:
    clean_house_file(app_client.app.state.engine)
    house_file.upsert_room(db_session, "Wohnen", SQUARE, 2500)
    db_session.commit()
    add_member(app_client)
    sign_in(app_client, MEMBER_EMAIL, MEMBER_PASSWORD)
    assert app_client.post("/rooms/Wohnen/duplicate", json={"name": "Mine"}).status_code == 404
    assert [room.name for room in db_session.scalars(select(Room))] == ["Wohnen"]
    db_session.rollback()
    clean_house_file(app_client.app.state.engine)


def test_a_member_never_changes_the_owners_review_items(app_client: TestClient) -> None:
    from app.db.models import ReviewItem

    add_member(app_client)
    assert create(app_client, "owner-bench").status_code == 202
    item = {"aspect": "proportion", "expected": "600 mm", "expected_source": "spec", "observed": "500 mm",
            "image": 1, "severity": "minor"}
    with Session(app_client.app.state.engine) as session:
        review = house_file.record_review(session, "owner-bench", 1, ["still.png"], [item])
        session.commit()
        review_id = review.id
        item_id = session.scalars(select(ReviewItem.id).where(ReviewItem.review_id == review_id)).one()
    sign_in(app_client, MEMBER_EMAIL, MEMBER_PASSWORD)
    refused = app_client.patch(f"/reviews/{review_id}/items/{item_id}", json={"status": "dismissed"})
    assert refused.status_code == 404
    with Session(app_client.app.state.engine) as session:
        assert session.get(ReviewItem, item_id).status == "open"
