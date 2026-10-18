"""installation-reading: rule-matched reading lists and rights-checked local reading."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.engineering.ingest import ingest_version
from app.engineering.reading import (
    NO_SOURCE,
    NOT_RECORDED,
    NOTICE,
    ReadingRefused,
    ReadingRulesError,
    _Rule,
    load_reading_rules,
    read_blocks,
    reading_list,
    wall_hung_items,
)
from app.engineering.registry import decide_rights, register_source
from app.engineering.schemas import Collection, EvidenceBlock, RightsIn, Scope, SourceIn

# --- rule table -------------------------------------------------------------------------


def test_the_shipped_rules_load() -> None:
    rules = load_reading_rules()
    assert set(rules) == {"wall_shelf", "wall_module"}
    assert "shelf" in rules["wall_shelf"].applicable_furniture
    assert Collection.KITCHEN_ANCHOR in rules["wall_module"].collections


@pytest.mark.parametrize(
    ("body", "named"),
    [
        ("wall_shelf: {applicable_furniture: [shelf]}\nwall_module: {collections: [x]}\n", "unknown collection 'x'"),
        ("wall_shelf: {applicable_furniture: [shelf]}\nwall_module: {}\nceiling: {}\n", "unknown item kind(s) ceiling"),
        ("wall_shelf: {applicable_furniture: [shelf]}\n", "missing item kind wall_module"),
        ("wall_shelf: {applicable_furniture: [shelf], colour: red}\nwall_module: {}\n", "wall_shelf"),
    ],
)
def test_a_malformed_rule_file_is_refused_naming_it(tmp_path, body: str, named: str) -> None:
    path = tmp_path / "reading_rules.yaml"
    path.write_text(body, encoding="utf-8")
    with pytest.raises(ReadingRulesError) as caught:
        load_reading_rules(path)
    assert "reading_rules.yaml" in str(caught.value)
    assert named in str(caught.value)


# --- wall-hung items --------------------------------------------------------------------


def _spec(*, shelves=(), modules=()) -> dict:
    return {"wall_shelves": list(shelves), "modules": list(modules)}


SHELF = {"id": "hall-board", "name": "Hall board"}


def test_only_wall_shelves_and_wall_mounted_modules_are_wall_hung() -> None:
    spec = _spec(
        shelves=[SHELF],
        modules=[
            {"id": "upper", "name": "Upper", "z": 1400, "mounting": "wall"},
            {"id": "raised", "name": "Raised", "z": 1400},
            {"id": "base", "name": "Base", "z": 0, "mounting": "floor"},
        ],
    )
    assert [(item["id"], item["kind"]) for item in wall_hung_items(spec)] == [
        ("hall-board", "wall_shelf"),
        ("upper", "wall_module"),
    ]


# --- reading list -----------------------------------------------------------------------


def _tag() -> str:
    return f"t-{uuid4().hex[:10]}"


def _rules(shelf_tag: str, module_tag: str) -> dict:
    return {
        "wall_shelf": _Rule(applicable_furniture=[shelf_tag]),
        "wall_module": _Rule(applicable_furniture=[module_tag]),
    }


def _source(session, *, title: str, furniture: list[str], **metadata):
    return register_source(
        session,
        SourceIn(
            key=f"reading-{uuid4().hex}",
            collections=[Collection.STANDARDS],
            metadata={"title": title, "applicable_furniture": furniture, **metadata},
        ),
    )


def test_a_wall_shelf_lists_its_sources_verified_first(db_session) -> None:
    tag = _tag()
    plain = _source(db_session, title="A plain source", furniture=[tag], edition="2022-07",
                    source_url="https://example.org/a")
    checked = _source(db_session, title="Z checked source", furniture=[tag])
    checked.verification_status = "verified"
    db_session.flush()

    result = reading_list(db_session, _spec(shelves=[SHELF]), _rules(tag, _tag()))

    assert result["notice"] == NOTICE
    assert [entry["version_id"] for entry in result["entries"]] == [str(checked.id), str(plain.id)]
    entry = result["entries"][1]
    assert entry["edition"] == "2022-07"
    assert entry["source_url"] == "https://example.org/a"
    assert entry["items"] == ["hall-board"]
    assert entry["matched_by"] == {"hall-board": f"furniture: {tag}"}
    assert result["gaps"] == []


def test_null_citation_fields_read_not_recorded_and_no_local_path(db_session) -> None:
    tag = _tag()
    version = _source(db_session, title="Bare source", furniture=[tag])
    version.local_path = "guidelines/private/bare.pdf"
    db_session.flush()

    (entry,) = reading_list(db_session, _spec(shelves=[SHELF]), _rules(tag, _tag()))["entries"]

    assert entry["publisher"] == entry["edition"] == entry["page_section"] == NOT_RECORDED
    assert "bare.pdf" not in str(entry)


def test_a_raised_module_without_mounting_gets_no_reading(db_session) -> None:
    tag = _tag()
    _source(db_session, title="Cabinet source", furniture=[tag])
    spec = _spec(modules=[{"id": "raised", "name": "Raised", "z": 1400}])

    result = reading_list(db_session, spec, _rules(_tag(), tag))

    assert result["items"] == [] and result["entries"] == [] and result["gaps"] == []


def test_a_superseded_edition_is_not_listed(db_session) -> None:
    tag = _tag()
    old = _source(db_session, title="Old edition", furniture=[tag], edition="2019")
    new = _source(db_session, title="New edition", furniture=[tag], edition="2022")
    old.superseded_by = new.id
    db_session.flush()
    spec = _spec(modules=[{"id": "upper", "name": "Upper", "mounting": "wall"}])

    result = reading_list(db_session, spec, _rules(_tag(), tag))

    assert [entry["version_id"] for entry in result["entries"]] == [str(new.id)]


def test_a_source_for_two_items_is_listed_once_naming_both(db_session) -> None:
    tag = _tag()
    _source(db_session, title="Shared source", furniture=[tag])
    spec = _spec(shelves=[SHELF], modules=[{"id": "upper", "name": "Upper", "mounting": "wall"}])

    (entry,) = reading_list(db_session, spec, _rules(tag, tag))["entries"]

    assert entry["items"] == ["hall-board", "upper"]


def test_an_item_no_source_covers_is_named_as_a_gap(db_session) -> None:
    spec = _spec(modules=[{"id": "upper", "name": "Upper", "mounting": "wall"}])

    result = reading_list(db_session, spec, _rules(_tag(), _tag()))

    assert result["gaps"] == [{"item": "upper", "name": "Upper", "reason": NO_SOURCE}]
    assert result["notice"] == NOTICE


# --- local reading ----------------------------------------------------------------------


def _published(session, root, *, grants: set[Scope] | None = None, blocks: int = 1):
    version = _source(session, title="Readable source", furniture=[_tag()], source_url="https://example.org/r")
    scopes = grants if grants is not None else {Scope.EXTRACT, Scope.EMBED, Scope.RETRIEVE, Scope.RETAIN}
    decide_rights(
        session,
        version.id,
        RightsIn(
            action="approve",
            reviewer="fixture author",
            evidence="Original synthetic test text permits stated operations",
            grants={scope: {} for scope in scopes | {Scope.EXTRACT, Scope.EMBED, Scope.RETAIN}},
        ),
    )
    reviewed = [
        EvidenceBlock(block_id=f"p-{n}", kind="paragraph", content=f"Synthetic paragraph {n}", pages=[n],
                      section="Fixing", verification_status="verified", reviewed_by="fixture author")
        for n in range(1, blocks + 1)
    ]
    run = ingest_version(session, SimpleNamespace(guideline_root=root), version.id, reviewed_blocks=reviewed)
    assert run.state == "published", run.reason
    if grants is not None and Scope.RETRIEVE not in grants:
        decide_rights(
            session,
            version.id,
            RightsIn(
                action="approve",
                reviewer="fixture author",
                evidence="Original synthetic test text; retention only",
                grants={Scope.RETAIN: {}},
            ),
        )
    return version


def test_local_use_rights_show_blocks_with_page_references(db_session, tmp_path, fake_embedder) -> None:
    version = _published(db_session, tmp_path, blocks=2)

    result = read_blocks(db_session, version.id, {version.id})

    assert result["readable"] is True
    assert [(block["text"], block["pages"], block["section"]) for block in result["blocks"]] == [
        ("Synthetic paragraph 1", [1], "Fixing"),
        ("Synthetic paragraph 2", [2], "Fixing"),
    ]


def test_blocks_are_paged(db_session, tmp_path, fake_embedder) -> None:
    version = _published(db_session, tmp_path, blocks=21)

    first = read_blocks(db_session, version.id, {version.id})
    second = read_blocks(db_session, version.id, {version.id}, page=2)

    assert len(first["blocks"]) == 20 and first["more"] is True
    assert [block["block_id"] for block in second["blocks"]] == ["p-21"] and second["more"] is False


def test_revoked_rights_return_the_link_and_reason_only(db_session, tmp_path, fake_embedder) -> None:
    version = _published(db_session, tmp_path)
    decide_rights(
        db_session,
        version.id,
        RightsIn(action="revoke", reviewer="fixture author", evidence="Withdrawn after listing"),
    )

    result = read_blocks(db_session, version.id, {version.id})

    assert result["readable"] is False
    assert result["reason"] == "rights revoked"
    assert result["blocks"] == []
    assert result["source_url"] == "https://example.org/r"


def test_retention_without_local_retrieval_cannot_be_read(db_session, tmp_path, fake_embedder) -> None:
    version = _published(db_session, tmp_path, grants=set())

    result = read_blocks(db_session, version.id, {version.id})

    assert result["readable"] is False
    assert result["reason"] == "rights do not permit local reading"


def test_pending_rights_and_no_blocks_say_so(db_session) -> None:
    version = _source(db_session, title="Link only", furniture=[_tag()])

    result = read_blocks(db_session, version.id, {version.id})

    assert result["reason"] == "rights pending" and result["blocks"] == []


def test_a_source_not_on_the_list_is_refused(db_session, tmp_path, fake_embedder) -> None:
    version = _published(db_session, tmp_path)

    with pytest.raises(ReadingRefused):
        read_blocks(db_session, version.id, set())
