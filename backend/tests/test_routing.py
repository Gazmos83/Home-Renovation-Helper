"""llm-gateway: per-agent routing from a configuration file."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.agent.models.routing import SLOTS, Routing, RoutingError, load_routing

COMPLETE = """
agents:
  foreman: openai/gpt-5.6-luna
  intake: deepseek/deepseek-v4.1-flash
  designer: deepseek/deepseek-v4-pro-0813
  builder: deepseek/deepseek-v4-pro-0813
  lighting: openai/gpt-5.6-sol
  reviewer: deepseek/deepseek-v4.1-flash
  researcher: openai/gpt-5.6-luna
"""


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "models.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_the_shipped_routing_file_loads() -> None:
    routing = load_routing()
    assert isinstance(routing, Routing)
    assert {slot for slot, _ in routing.items()} == set(SLOTS)
    assert routing.model_for("reviewer") == "deepseek/deepseek-v4.1-flash"


def test_a_complete_file_lists_each_slot_with_its_slug(tmp_path: Path) -> None:
    routing = load_routing(_write(tmp_path, COMPLETE))
    assert dict(routing.items()) == {
        "foreman": "openai/gpt-5.6-luna",
        "intake": "deepseek/deepseek-v4.1-flash",
        "designer": "deepseek/deepseek-v4-pro-0813",
        "builder": "deepseek/deepseek-v4-pro-0813",
        "lighting": "openai/gpt-5.6-sol",
        "reviewer": "deepseek/deepseek-v4.1-flash",
        "researcher": "openai/gpt-5.6-luna",
    }


def test_a_missing_slot_fails_by_name(tmp_path: Path) -> None:
    without_reviewer = "\n".join(
        line for line in COMPLETE.splitlines() if "reviewer:" not in line
    )
    with pytest.raises(RoutingError) as caught:
        load_routing(_write(tmp_path, without_reviewer))
    assert "reviewer" in str(caught.value)


def test_an_unknown_slug_fails_by_name(tmp_path: Path) -> None:
    text = COMPLETE.replace("researcher: openai/gpt-5.6-luna", "researcher: openai/gpt-9")
    with pytest.raises(RoutingError) as caught:
        load_routing(_write(tmp_path, text))
    assert "openai/gpt-9" in str(caught.value)


def test_a_fallback_key_fails_by_name(tmp_path: Path) -> None:
    text = COMPLETE + "  backup: openai/gpt-5.6-luna\n"
    with pytest.raises(RoutingError) as caught:
        load_routing(_write(tmp_path, text))
    assert "backup" in str(caught.value)


def test_a_duplicate_slot_fails(tmp_path: Path) -> None:
    text = COMPLETE + "  reviewer: anthropic/claude-haiku-4.5\n"
    with pytest.raises(RoutingError) as caught:
        load_routing(_write(tmp_path, text))
    assert "reviewer" in str(caught.value)


def test_the_reviewer_routed_to_a_text_only_model_fails(tmp_path: Path) -> None:
    text = COMPLETE.replace(
        "reviewer: deepseek/deepseek-v4.1-flash", "reviewer: openai/gpt-5.6-luna"
    )
    with pytest.raises(RoutingError) as caught:
        load_routing(_write(tmp_path, text))
    message = str(caught.value)
    assert "reviewer" in message
    assert "openai/gpt-5.6-luna" in message


def test_intake_routed_to_a_text_only_model_fails_naming_it(tmp_path: Path) -> None:
    text = COMPLETE.replace("intake: deepseek/deepseek-v4.1-flash", "intake: openai/gpt-5.6-luna")
    with pytest.raises(RoutingError) as caught:
        load_routing(_write(tmp_path, text))
    message = str(caught.value)
    assert "intake" in message
    assert "openai/gpt-5.6-luna" in message


def test_the_shipped_routing_sends_intake_to_the_image_model() -> None:
    assert load_routing().model_for("intake") == "deepseek/deepseek-v4.1-flash"


def test_an_override_resolves_over_the_file(tmp_path: Path) -> None:
    """The developer panel's per-slot override wins over the file value."""
    routing = load_routing(
        _write(tmp_path, COMPLETE),
        overrides={"designer": "anthropic/claude-haiku-4.5"},
    )
    assert routing.model_for("designer") == "anthropic/claude-haiku-4.5"


def test_distinct_and_image_slugs_for_the_probe() -> None:
    routing = load_routing()
    assert routing.image_slugs() == {"deepseek/deepseek-v4.1-flash"}
    assert "openai/gpt-5.6-luna" in routing.distinct_slugs()
    # Luna is routed to two slots but probed once.
    assert routing.distinct_slugs().count("openai/gpt-5.6-luna") == 1


def test_intake_is_an_image_slot_so_its_slug_gets_the_image_probe() -> None:
    from app.agent.models.routing import IMAGE_SLOTS

    assert {"intake", "reviewer"} == set(IMAGE_SLOTS)
    assert load_routing().model_for("intake") in load_routing().image_slugs()
