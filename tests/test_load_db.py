import pytest
from sqlalchemy import text

from src.config import DATA_RAW
from src.db import get_engine
from src.load import RAW_FILES, load_data

pytestmark = pytest.mark.db


def test_load_is_idempotent_and_reconciles_source_data():
    missing = [filename for filename in RAW_FILES.values() if not (DATA_RAW / filename).is_file()]
    if missing:
        pytest.skip(f"Olist CSV files missing under {DATA_RAW}: {', '.join(missing)}")

    first = load_data()
    second = load_data()
    data_tables = [
        "category_translation",
        "customers",
        "sellers",
        "products",
        "geolocation",
        "orders",
        "order_items",
        "payments",
        "reviews",
        "dim_customer_unique",
    ]
    assert {table: first["core_rows"][table] for table in data_tables} == {
        table: second["core_rows"][table] for table in data_tables
    }

    engine = get_engine()
    with engine.connect() as conn:
        reconciled = conn.execute(
            text(
                "SELECT table_name, csv_rows, raw_rows FROM core.load_reconciliation "
                "WHERE run_ts = :run_ts AND table_name LIKE 'raw.%'"
            ),
            {"run_ts": second["run_ts"]},
        ).all()
        assert len(reconciled) == len(RAW_FILES)
        assert all(row.csv_rows == row.raw_rows for row in reconciled)

        orphan_queries = {
            "orders_customers": """
                SELECT COUNT(*) FROM core.orders o LEFT JOIN core.customers c
                ON c.customer_id = o.customer_id WHERE c.customer_id IS NULL
            """,
            "items_orders": """
                SELECT COUNT(*) FROM core.order_items i LEFT JOIN core.orders o
                ON o.order_id = i.order_id WHERE o.order_id IS NULL
            """,
            "items_products": """
                SELECT COUNT(*) FROM core.order_items i LEFT JOIN core.products p
                ON p.product_id = i.product_id
                WHERE i.product_id IS NOT NULL AND p.product_id IS NULL
            """,
            "items_sellers": """
                SELECT COUNT(*) FROM core.order_items i LEFT JOIN core.sellers s
                ON s.seller_id = i.seller_id
                WHERE i.seller_id IS NOT NULL AND s.seller_id IS NULL
            """,
            "payments_orders": """
                SELECT COUNT(*) FROM core.payments p LEFT JOIN core.orders o
                ON o.order_id = p.order_id WHERE o.order_id IS NULL
            """,
            "reviews_orders": """
                SELECT COUNT(*) FROM core.reviews r LEFT JOIN core.orders o
                ON o.order_id = r.order_id WHERE o.order_id IS NULL
            """,
        }
        assert {
            name: conn.execute(text(query)).scalar_one() for name, query in orphan_queries.items()
        } == {name: 0 for name in orphan_queries}

        duplicate_reviews = conn.execute(
            text(
                "SELECT COUNT(*) FROM (SELECT review_id, order_id FROM core.reviews "
                "GROUP BY review_id, order_id HAVING COUNT(*) > 1) duplicates"
            )
        ).scalar_one()
        missing_product_category = conn.execute(
            text(
                "SELECT COUNT(*) FROM core.products "
                "WHERE category_pt IS NOT NULL AND category_en IS NULL"
            )
        ).scalar_one()
        assert duplicate_reviews == 0
        assert missing_product_category == 0

    assert first["sanity"]["sql"] == first["sanity"]["pandas"]
    assert second["sanity"]["sql"] == second["sanity"]["pandas"]
