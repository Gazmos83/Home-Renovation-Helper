"""pricing corpus: price list, snapshots, pricings, remnants, store, chunks, guideline notes

Revision ID: 0007_pricing_corpus
Revises: 0005_reviews
Create Date: 2026-10-06 01:01:52.324274

"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0007_pricing_corpus'
down_revision: str | None = '0005_reviews'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('chunks',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=1024), nullable=False),
    sa.Column('source_site', sa.String(length=32), nullable=False),
    sa.Column('url', sa.Text(), nullable=False),
    sa.Column('category', sa.String(length=128), nullable=False),
    sa.Column('title', sa.String(length=300), nullable=True),
    sa.Column('section', sa.String(length=200), nullable=True),
    sa.Column('published_on', sa.Date(), nullable=True),
    sa.Column('scraped_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('chunk_index', sa.Integer(), nullable=False),
    sa.Column('content_hash', sa.String(length=64), nullable=True),
    sa.Column('search_vector', postgresql.TSVECTOR(), sa.Computed("to_tsvector('german', content)", persisted=True), nullable=False),
    sa.CheckConstraint("btrim(source_site) <> ''", name='ck_chunks_source_site_not_blank'),
    sa.CheckConstraint("btrim(url) <> ''", name='ck_chunks_url_not_blank'),
    sa.CheckConstraint('chunk_index >= 0', name='ck_chunks_chunk_index_non_negative'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('url', 'chunk_index', name='uq_chunks_url_chunk_index')
    )
    op.create_index('ix_chunks_category', 'chunks', ['category'], unique=False)
    op.create_index('ix_chunks_embedding_hnsw', 'chunks', ['embedding'], unique=False, postgresql_using='hnsw', postgresql_ops={'embedding': 'vector_cosine_ops'})
    op.create_index('ix_chunks_search_vector', 'chunks', ['search_vector'], unique=False, postgresql_using='gin')
    op.create_index('ix_chunks_source_site', 'chunks', ['source_site'], unique=False)
    op.create_table('guideline_notes',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('value', sa.Float(), nullable=True),
    sa.Column('unit', sa.String(length=24), nullable=True),
    sa.Column('citation', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("btrim(body) <> ''", name='ck_guideline_notes_body_not_blank'),
    sa.CheckConstraint("btrim(citation) <> ''", name='ck_guideline_notes_citation_not_blank'),
    sa.CheckConstraint("btrim(title) <> ''", name='ck_guideline_notes_title_not_blank'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('remnant_sheets',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('material_key', sa.String(length=128), nullable=False),
    sa.Column('length_mm', sa.Integer(), nullable=False),
    sa.Column('width_mm', sa.Integer(), nullable=False),
    sa.Column('grain_axis', sa.String(length=16), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('added_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("btrim(material_key) <> ''", name='ck_remnant_sheets_key_not_blank'),
    sa.CheckConstraint("grain_axis IN ('length', 'width')", name='ck_remnant_sheets_grain_axis'),
    sa.CheckConstraint('length_mm > 0 AND width_mm > 0', name='ck_remnant_sheets_size_positive'),
    sa.CheckConstraint('quantity > 0', name='ck_remnant_sheets_quantity_positive'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_remnant_sheets_material_key', 'remnant_sheets', ['material_key'], unique=False)
    op.create_table('stores',
    sa.Column('store_key', sa.String(length=128), nullable=False),
    sa.Column('source_site', sa.String(length=32), nullable=False),
    sa.Column('name', sa.String(length=256), nullable=False),
    sa.Column('address', sa.Text(), nullable=True),
    sa.Column('phone', sa.String(length=64), nullable=True),
    sa.Column('market_id', sa.String(length=64), nullable=True),
    sa.Column('url', sa.Text(), nullable=False),
    sa.Column('captured_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("btrim(store_key) <> ''", name='ck_stores_key_not_blank'),
    sa.CheckConstraint("btrim(url) <> ''", name='ck_stores_url_not_blank'),
    sa.PrimaryKeyConstraint('store_key')
    )
    op.create_table('cut_list_pricings',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('package_id', sa.String(length=64), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('store_key', sa.String(length=128), nullable=False),
    sa.Column('computed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('materials_cents', sa.Integer(), nullable=False),
    sa.Column('cut_service_cents', sa.Integer(), nullable=False),
    sa.Column('banding_cents', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('hardware_cents', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('delivery_cents', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('total_cents', sa.Integer(), nullable=False),
    sa.Column('complete', sa.Boolean(), nullable=False),
    sa.Column('custom_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('undetermined_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('review_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('unpriced_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('result', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('cut_charge_mode', sa.String(length=16), nullable=True),
    sa.CheckConstraint("cut_charge_mode IS NULL OR cut_charge_mode IN ('shared', 'per_cut')", name='ck_cut_list_pricings_charge_mode'),
    sa.CheckConstraint('custom_count >= 0 AND undetermined_count >= 0 AND review_count >= 0 AND unpriced_count >= 0', name='ck_cut_list_pricings_counts_non_negative'),
    sa.CheckConstraint('materials_cents >= 0 AND cut_service_cents >= 0 AND banding_cents >= 0 AND hardware_cents >= 0 AND delivery_cents >= 0 AND total_cents >= 0', name='ck_cut_list_pricings_money_non_negative'),
    sa.ForeignKeyConstraint(['store_key'], ['stores.store_key'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_cut_list_pricings_package', 'cut_list_pricings', ['package_id', 'version'], unique=False)
    op.create_table('product_snapshots',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('retailer', sa.String(length=32), nullable=False),
    sa.Column('url', sa.Text(), nullable=False),
    sa.Column('product_name', sa.Text(), nullable=False),
    sa.Column('price', sa.Numeric(precision=12, scale=2), nullable=True),
    sa.Column('currency', sa.String(length=3), nullable=True),
    sa.Column('availability', sa.Text(), nullable=True),
    sa.Column('specification', sa.Text(), nullable=False),
    sa.Column('store_name', sa.String(length=256), nullable=True),
    sa.Column('captured_on', sa.Date(), nullable=False),
    sa.Column('recorded_by_id', sa.Uuid(), nullable=True),
    sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("btrim(product_name) <> ''", name='ck_product_snapshots_name_not_blank'),
    sa.CheckConstraint("btrim(retailer) <> ''", name='ck_product_snapshots_retailer_not_blank'),
    sa.CheckConstraint("btrim(specification) <> ''", name='ck_product_snapshots_specification_not_blank'),
    sa.CheckConstraint("btrim(url) <> ''", name='ck_product_snapshots_url_not_blank'),
    sa.CheckConstraint('price IS NULL OR price >= 0', name='ck_product_snapshots_price_non_negative'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_product_snapshots_url_captured_on', 'product_snapshots', ['url', 'captured_on'], unique=False)
    op.create_table('store_cut_restrictions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('store_key', sa.String(length=128), nullable=False),
    sa.Column('restriction', sa.String(length=48), nullable=False),
    sa.Column('numeric_value', sa.Float(), nullable=True),
    sa.Column('text_value', sa.Text(), nullable=True),
    sa.Column('recorded_by', sa.String(length=128), nullable=False),
    sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('note', sa.Text(), nullable=True),
    sa.CheckConstraint("btrim(recorded_by) <> ''", name='ck_store_restriction_has_an_author'),
    sa.CheckConstraint('numeric_value IS NOT NULL OR text_value IS NOT NULL', name='ck_store_restriction_has_a_value'),
    sa.ForeignKeyConstraint(['store_key'], ['stores.store_key'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('store_key', 'restriction', name='uq_store_cut_restriction')
    )
    op.create_table('store_services',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('store_key', sa.String(length=128), nullable=False),
    sa.Column('service', sa.String(length=64), nullable=False),
    sa.Column('availability', sa.String(length=16), nullable=False),
    sa.Column('price_cents', sa.Integer(), nullable=True),
    sa.Column('url', sa.Text(), nullable=False),
    sa.Column('captured_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('price_cents IS NULL OR price_cents >= 0', name='ck_store_service_price_non_negative'),
    sa.ForeignKeyConstraint(['store_key'], ['stores.store_key'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('store_key', 'service', name='uq_store_service')
    )
    op.create_table('supplier_prices',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('key', sa.String(length=128), nullable=False),
    sa.Column('label', sa.String(length=256), nullable=False),
    sa.Column('category', sa.String(length=16), nullable=False),
    sa.Column('unit', sa.String(length=16), nullable=False),
    sa.Column('source_site', sa.String(length=32), nullable=False),
    sa.Column('sheet_length_mm', sa.Integer(), nullable=True),
    sa.Column('sheet_width_mm', sa.Integer(), nullable=True),
    sa.Column('thickness_mm', sa.Integer(), nullable=True),
    sa.Column('bundle_length_mm', sa.Integer(), nullable=True),
    sa.Column('base_cents', sa.Integer(), nullable=True),
    sa.Column('provenance', sa.String(length=16), nullable=False),
    sa.Column('source_url', sa.Text(), nullable=True),
    sa.Column('captured_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('snapshot_id', sa.Uuid(), nullable=True),
    sa.Column('override_cents', sa.Integer(), nullable=True),
    sa.Column('override_note', sa.Text(), nullable=True),
    sa.Column('override_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('unconfirmed', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("btrim(key) <> ''", name='ck_supplier_prices_key_not_blank'),
    sa.CheckConstraint("btrim(label) <> ''", name='ck_supplier_prices_label_not_blank'),
    sa.CheckConstraint("category <> 'panel' OR (sheet_width_mm IS NOT NULL AND sheet_length_mm IS NOT NULL AND thickness_mm IS NOT NULL)", name='ck_supplier_prices_panel_has_sheet'),
    sa.CheckConstraint("category IN ('panel', 'hardware', 'finish', 'edge_band', 'cut_service', 'delivery')", name='ck_supplier_prices_category_known'),
    sa.CheckConstraint("provenance IN ('captured', 'manual', 'snapshot')", name='ck_supplier_prices_provenance_known'),
    sa.CheckConstraint("unit IN ('per_m2', 'per_piece', 'per_metre', 'per_cut')", name='ck_supplier_prices_unit_known'),
    sa.CheckConstraint('base_cents IS NULL OR base_cents >= 0', name='ck_supplier_prices_base_non_negative'),
    sa.CheckConstraint('bundle_length_mm IS NULL OR bundle_length_mm > 0', name='ck_supplier_prices_bundle_length_positive'),
    sa.CheckConstraint('override_cents IS NULL OR override_cents >= 0', name='ck_supplier_prices_override_non_negative'),
    sa.ForeignKeyConstraint(['snapshot_id'], ['product_snapshots.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('key')
    )
    op.create_index('ix_supplier_prices_category', 'supplier_prices', ['category'], unique=False)
    op.create_table('cut_list_pricing_entries',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('pricing_id', sa.Uuid(), nullable=False),
    sa.Column('entry_id', sa.Uuid(), nullable=False),
    sa.Column('cents_used', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['entry_id'], ['supplier_prices.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['pricing_id'], ['cut_list_pricings.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('pricing_id', 'entry_id', name='uq_cut_list_pricing_entry')
    )
    op.create_index('ix_cut_list_pricing_entries_pricing_id', 'cut_list_pricing_entries', ['pricing_id'], unique=False)

    op.bulk_insert(_supplier_prices_table(), _seed_rows())


# The dated planning evidence (review of 2026-09-15) the predecessor seeded as
# `unconfirmed` rows: toom's delivery bands, its per-service cutting prices and
# the reserved Personal_Supply entry that workshop-supplied parts resolve to.
_REVIEW_AT = datetime(2026, 9, 15, tzinfo=UTC)
_REVIEW_NOTE = "Historical review (2026-09-15), not yet confirmed against the maintained price list."
_CUT_SERVICE_URL = "https://toom.de/service/services-im-markt/zuschnittservice/"
_CUT_SERVICES = [
    ("gerader_zuschnitt", "Straight cut (gerader Zuschnitt)", 0),
    ("topfband_bohrung", "Hinge boring (Topfband-Bohrung)", 299),
    ("spuelenlochstanzung", "Sink hole punch (Spülenlochstanzung)", 499),
    ("kapp_und_gehrungsschnitt", "Mitre/crosscut (Kapp- und Gehrungsschnitt)", 799),
    ("spuelen_und_herdausschnitt", "Sink/hob cut-out (Spülen- und Herdausschnitt)", 1299),
    ("professionelle_eckverbindung", "Professional corner joint (professionelle Eckverbindung)", 2499),
]
_DELIVERY = [
    ("delivery:10km", "Delivery up to 10 km", 5499),
    ("delivery:20km", "Delivery up to 20 km", 5999),
    ("delivery:30km", "Delivery up to 30 km", 6499),
    ("delivery:surcharge", "Additional pallet or m² surcharge", 1499),
]


def _supplier_prices_table() -> sa.Table:
    return sa.Table(
        "supplier_prices",
        sa.MetaData(),
        sa.Column("id", sa.Uuid()),
        sa.Column("key", sa.String(128)),
        sa.Column("label", sa.String(256)),
        sa.Column("category", sa.String(16)),
        sa.Column("unit", sa.String(16)),
        sa.Column("source_site", sa.String(32)),
        sa.Column("base_cents", sa.Integer()),
        sa.Column("provenance", sa.String(16)),
        sa.Column("source_url", sa.Text()),
        sa.Column("captured_at", sa.DateTime(timezone=True)),
        sa.Column("override_note", sa.Text()),
        sa.Column("unconfirmed", sa.Boolean()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )


def _seed_rows() -> list[dict[str, object]]:
    def row(key: str, label: str, category: str, unit: str, cents: int, url: str | None, note: str | None, unconfirmed: bool):
        return {
            "id": uuid4(), "key": key, "label": label, "category": category, "unit": unit,
            "source_site": "toom", "base_cents": cents, "provenance": "manual", "source_url": url,
            "captured_at": _REVIEW_AT, "override_note": note, "unconfirmed": unconfirmed,
            "created_at": _REVIEW_AT, "updated_at": _REVIEW_AT,
        }

    rows = [row(k, label, "delivery", "per_piece", cents, None, _REVIEW_NOTE, True) for k, label, cents in _DELIVERY]
    rows += [
        row(f"cut_service:{k}", label, "cut_service", "per_cut", cents, _CUT_SERVICE_URL, _REVIEW_NOTE, True)
        for k, label, cents in _CUT_SERVICES
    ]
    rows.append(row("Personal_Supply", "Supplied by the workshop", "hardware", "per_piece", 0, None, None, False))
    return rows


def downgrade() -> None:
    op.drop_index('ix_cut_list_pricing_entries_pricing_id', table_name='cut_list_pricing_entries')
    op.drop_table('cut_list_pricing_entries')
    op.drop_index('ix_supplier_prices_category', table_name='supplier_prices')
    op.drop_table('supplier_prices')
    op.drop_table('store_services')
    op.drop_table('store_cut_restrictions')
    op.drop_index('ix_product_snapshots_url_captured_on', table_name='product_snapshots')
    op.drop_table('product_snapshots')
    op.drop_index('ix_cut_list_pricings_package', table_name='cut_list_pricings')
    op.drop_table('cut_list_pricings')
    op.drop_table('stores')
    op.drop_index('ix_remnant_sheets_material_key', table_name='remnant_sheets')
    op.drop_table('remnant_sheets')
    op.drop_table('guideline_notes')
    op.drop_index('ix_chunks_source_site', table_name='chunks')
    op.drop_index('ix_chunks_search_vector', table_name='chunks', postgresql_using='gin')
    op.drop_index('ix_chunks_embedding_hnsw', table_name='chunks', postgresql_using='hnsw', postgresql_ops={'embedding': 'vector_cosine_ops'})
    op.drop_index('ix_chunks_category', table_name='chunks')
    op.drop_table('chunks')
