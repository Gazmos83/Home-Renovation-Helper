"""The hardware catalog: loading, refusals and key lookup (hardware-catalog spec)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app import main
from app.blender.hardware_catalog import (
    HardwareCatalogError,
    default_catalog,
    load_catalog,
    parse_catalog,
)
from app.config import Settings

PIN = {"key": "shelf-pin", "shape": "shelf_pin", "size": {"diameter_mm": 5, "length_mm": 16}, "finish": "nickel"}


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "hardware.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_the_shipped_catalog_resolves_every_default_rule_key() -> None:
    """Scenario: Catalog loads."""
    catalog = default_catalog()
    for key in (
        "hinge-concealed-110", "hinge-flap", "flap-stay", "push-latch", "shelf-pin", "drawer-runner-450",
        "confirmat-7x50", "rail-oval-30x15", "rail-support-oval", "handle-bar-160-black", "handle-knob-brass",
    ):
        assert catalog.entry_for(key) is not None, key
    assert catalog.entry_for("drawer-runner-450").name == "drawer-runner-*"


def test_an_exact_key_wins_over_a_pattern_and_the_longer_pattern_wins() -> None:
    catalog = parse_catalog([
        {"pattern": "hinge-*", **{k: v for k, v in PIN.items() if k != "key"}},
        {"pattern": "hinge-blum-*", **{k: v for k, v in PIN.items() if k != "key"}},
        {"key": "hinge-blum-110", **{k: v for k, v in PIN.items() if k != "key"}},
    ])
    assert catalog.entry_for("hinge-blum-110").name == "hinge-blum-110"
    assert catalog.entry_for("hinge-blum-155").name == "hinge-blum-*"
    assert catalog.entry_for("hinge-other").name == "hinge-*"
    assert catalog.entry_for("bracket-white") is None


def test_an_unknown_shape_stops_loading_naming_the_file_entry_and_shape(tmp_path: Path) -> None:
    """Scenario: Unknown shape stops startup."""
    path = _write(tmp_path, "entries:\n  - {key: lift, shape: gas_strut, size: {}, finish: steel}\n")
    with pytest.raises(HardwareCatalogError, match=r"hardware\.yaml: entry 'lift'.*gas_strut"):
        load_catalog(path)


def test_a_size_field_the_shape_does_not_take_is_refused() -> None:
    """Scenario: Wrong size field."""
    with pytest.raises(HardwareCatalogError, match=r"entry 'shelf-pin': size\.cup_diameter_mm"):
        parse_catalog([{**PIN, "size": {"diameter_mm": 5, "length_mm": 16, "cup_diameter_mm": 35}}])


def test_an_entry_listed_twice_is_refused() -> None:
    with pytest.raises(HardwareCatalogError, match="'shelf-pin' is listed twice"):
        parse_catalog([PIN, PIN])


def test_an_entry_needs_exactly_one_of_key_and_pattern() -> None:
    with pytest.raises(HardwareCatalogError, match="exactly one of key and pattern"):
        parse_catalog([{**PIN, "pattern": "shelf-*"}])


def test_a_file_without_entries_is_refused(tmp_path: Path) -> None:
    with pytest.raises(HardwareCatalogError, match="needs an 'entries' list"):
        load_catalog(_write(tmp_path, "items: []\n"))


def test_frozen_entries_round_trip_through_the_parser() -> None:
    catalog = default_catalog()
    assert parse_catalog(catalog.frozen()).frozen() == catalog.frozen()


def test_a_broken_catalog_stops_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken():
        raise HardwareCatalogError("hardware.yaml: entry 'lift': shape: unknown (got 'gas_strut')")

    monkeypatch.setattr(main, "default_catalog", broken)
    settings = Settings(
        database_url="postgresql+psycopg://unused@localhost/unused", openrouter_api_key="sk-or-test",
        cors_origins="http://localhost:5173", owner_email="owner@example.com",
        owner_password="an-initial-owner-password", gateway_probe_enabled=False, _env_file=None,
    )
    with pytest.raises(HardwareCatalogError, match="hardware.yaml"):
        main.create_app(settings)
