"""pricing: German thousands separators are read whole, never cut to their last group."""

from __future__ import annotations

import pytest

from app.ingestion.live_listing_parser import _price_fields
from app.pricing import product_page


def test_a_listing_price_over_a_thousand_euros_is_read_whole() -> None:
    assert _price_fields("1.249,00 €") == ("1.249,00", None)
    assert _price_fields("2.049,50 € / m²1.249,00 € / Pack") == ("1.249,00", "2.049,50 € / m²")
    assert _price_fields("7,99 €") == ("7,99", None)


@pytest.mark.parametrize(
    ("text", "mm"), [("2.800 mm", 2800), ("2800 mm", 2800), ("207 cm", 2070), ("2,8 m", 2800), ("19 mm", 19)]
)
def test_a_sheet_length_with_a_thousands_dot_is_read_whole(text: str, mm: int) -> None:
    found = product_page._NUMBER_UNIT.search(f"Länge: {text}")
    assert found is not None
    assert product_page._mm(found.group(1), found.group(2)) == mm
