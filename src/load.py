"""Load the Olist CSV files into the raw and core schemas."""

import csv
import time
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pandas as pd
from sqlalchemy import text
from sqlalchemy.exc import InterfaceError, OperationalError

from .config import DATA_RAW, DOCS_DIR, LOAD_PARAMS
from .db import get_engine

RAW_FILES = {
    "olist_customers": "olist_customers_dataset.csv",
    "olist_orders": "olist_orders_dataset.csv",
    "olist_order_items": "olist_order_items_dataset.csv",
    "olist_order_payments": "olist_order_payments_dataset.csv",
    "olist_order_reviews": "olist_order_reviews_dataset.csv",
    "olist_products": "olist_products_dataset.csv",
    "olist_sellers": "olist_sellers_dataset.csv",
    "olist_geolocation": "olist_geolocation_dataset.csv",
    "product_category_name_translation": "product_category_name_translation.csv",
}

CORE_TABLES = (
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
    "load_reconciliation",
)

CORE_TRUNCATE_ORDER = (
    "dim_customer_unique",
    "reviews",
    "payments",
    "order_items",
    "orders",
    "geolocation",
    "products",
    "sellers",
    "customers",
    "category_translation",
)

CORE_SOURCE_TABLES = {
    "olist_customers": "customers",
    "olist_orders": "orders",
    "olist_order_items": "order_items",
    "olist_order_payments": "payments",
    "olist_order_reviews": "reviews",
    "olist_products": "products",
    "olist_sellers": "sellers",
    "olist_geolocation": "geolocation",
    "product_category_name_translation": "category_translation",
}

ACCENT_SOURCE = "áàãâäéèêëíìîïóòõôöúùûüçñ"
ACCENT_TARGET = "aaaaaeeeeiiiiooooouuuucn"
ACCENT_TRANSLATION = str.maketrans(dict(zip(ACCENT_SOURCE, ACCENT_TARGET)))
CENT = Decimal("0.01")


def null_if_empty(value):
    """Return None for null, empty, or whitespace-only values."""
    if value is None or pd.isna(value):
        return None
    value = str(value).strip()
    return value or None


def normalize_text(value):
    """Normalize location text to lowercase ASCII, matching in-memory and SQL loads."""
    value = null_if_empty(value)
    if value is None:
        return None
    return value.lower().translate(ACCENT_TRANSLATION)


def aggregate_geolocation(frame: pd.DataFrame) -> pd.DataFrame:
    """Aggregate source geolocation samples to one normalized record per zip prefix."""
    required = {
        "geolocation_zip_code_prefix",
        "geolocation_lat",
        "geolocation_lng",
        "geolocation_city",
        "geolocation_state",
    }
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Geolocation input is missing columns: {sorted(missing)}")

    data = frame[list(required)].copy()
    data["zip_prefix"] = pd.to_numeric(data["geolocation_zip_code_prefix"], errors="coerce")
    data["lat"] = pd.to_numeric(data["geolocation_lat"], errors="coerce")
    data["lng"] = pd.to_numeric(data["geolocation_lng"], errors="coerce")
    data["city"] = data["geolocation_city"].map(normalize_text)
    data["state"] = data["geolocation_state"].map(normalize_text)
    data = data.dropna(subset=["zip_prefix"])

    def mode(values):
        values = values.dropna()
        if values.empty:
            return None
        frequencies = values.value_counts()
        return sorted(frequencies[frequencies == frequencies.max()].index)[0]

    result = (
        data.groupby("zip_prefix", as_index=False)
        .agg(lat=("lat", "mean"), lng=("lng", "mean"), city=("city", mode), state=("state", mode))
        .sort_values("zip_prefix", kind="stable")
        .reset_index(drop=True)
    )
    result["zip_prefix"] = result["zip_prefix"].astype("int64")
    return result[["zip_prefix", "lat", "lng", "city", "state"]]


def dedupe_reviews(frame: pd.DataFrame) -> pd.DataFrame:
    """Keep the latest answer timestamp per review/order pair, deterministically."""
    required = {"review_id", "order_id", "review_answer_timestamp"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Review input is missing columns: {sorted(missing)}")

    data = frame.copy()
    data["_answer_ts"] = pd.to_datetime(data["review_answer_timestamp"], errors="coerce", utc=True)
    if "review_creation_date" in data:
        data["_creation_ts"] = pd.to_datetime(
            data["review_creation_date"], errors="coerce", utc=True
        )
    else:
        data["_creation_ts"] = pd.NaT
    for column in ("review_comment_message", "review_comment_title", "review_score"):
        if column not in data:
            data[column] = ""
        data[column] = data[column].fillna("").astype(str)

    data = data.sort_values(
        [
            "_answer_ts",
            "_creation_ts",
            "review_comment_message",
            "review_comment_title",
            "review_score",
        ],
        ascending=[False, False, True, True, True],
        na_position="last",
        kind="stable",
    )
    data = data.drop_duplicates(["review_id", "order_id"], keep="first")
    return data.drop(columns=["_answer_ts", "_creation_ts"])


def count_csv_rows(path: Path) -> int:
    """Count CSV data records independently of PostgreSQL COPY."""
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream)
        next(reader, None)
        return sum(1 for _ in reader)


def _count(conn, table: str) -> int:
    return conn.execute(text(f"SELECT COUNT(*) FROM core.{table}")).scalar_one()


def _sql_location(column: str) -> str:
    return (
        f"translate(lower(NULLIF(BTRIM({column}), '')), " f"'{ACCENT_SOURCE}', '{ACCENT_TARGET}')"
    )


def _record_reconciliation(conn, run_ts, table_name, csv_rows, raw_rows, core_rows, dropped, note):
    conn.execute(
        text(
            "INSERT INTO core.load_reconciliation "
            "(run_ts, table_name, csv_rows, raw_rows, core_rows, dropped_rows, note) "
            "VALUES (:run_ts, :table_name, :csv_rows, :raw_rows, :core_rows, :dropped_rows, :note)"
        ),
        {
            "run_ts": run_ts,
            "table_name": table_name,
            "csv_rows": csv_rows,
            "raw_rows": raw_rows,
            "core_rows": core_rows,
            "dropped_rows": dropped,
            "note": note,
        },
    )


def _load_core(conn, run_ts, csv_counts, raw_counts):
    dropped = {}

    conn.execute(
        text(
            "INSERT INTO core.category_translation (category_pt, category_en) "
            "SELECT NULLIF(BTRIM(product_category_name), ''), "
            "NULLIF(BTRIM(product_category_name_english), '') "
            "FROM raw.product_category_name_translation "
            "WHERE NULLIF(BTRIM(product_category_name), '') IS NOT NULL"
        )
    )

    conn.execute(
        text(
            "INSERT INTO core.customers "
            "(customer_id, customer_unique_id, zip_prefix, city, state) "
            f"SELECT NULLIF(BTRIM(customer_id), ''), NULLIF(BTRIM(customer_unique_id), ''), "
            f"NULLIF(BTRIM(customer_zip_code_prefix), '')::INTEGER, "
            f"{_sql_location('customer_city')}, {_sql_location('customer_state')} "
            f"FROM raw.olist_customers WHERE NULLIF(BTRIM(customer_id), '') IS NOT NULL"
        )
    )

    conn.execute(
        text(
            f"INSERT INTO core.sellers (seller_id, zip_prefix, city, state) "
            f"SELECT NULLIF(BTRIM(seller_id), ''), "
            f"NULLIF(BTRIM(seller_zip_code_prefix), '')::INTEGER, "
            f"{_sql_location('seller_city')}, {_sql_location('seller_state')} "
            f"FROM raw.olist_sellers WHERE NULLIF(BTRIM(seller_id), '') IS NOT NULL"
        )
    )

    missing_translation = conn.execute(
        text(
            "SELECT COUNT(DISTINCT NULLIF(BTRIM(p.product_category_name), '')) "
            "FROM raw.olist_products p "
            "LEFT JOIN core.category_translation t "
            "ON t.category_pt = NULLIF(BTRIM(p.product_category_name), '') "
            "WHERE NULLIF(BTRIM(p.product_category_name), '') IS NOT NULL AND t.category_pt IS NULL"
        )
    ).scalar_one()
    missing_category = conn.execute(
        text(
            "SELECT COUNT(*) FROM raw.olist_products "
            "WHERE NULLIF(BTRIM(product_category_name), '') IS NULL"
        )
    ).scalar_one()
    conn.execute(
        text(
            "INSERT INTO core.products (product_id, category_pt, category_en, name_length, "
            "description_length, photos_qty, weight_g, length_cm, height_cm, width_cm) "
            "SELECT NULLIF(BTRIM(p.product_id), ''), "
            "NULLIF(BTRIM(p.product_category_name), ''), "
            "CASE WHEN NULLIF(BTRIM(p.product_category_name), '') IS NULL THEN NULL "
            "ELSE COALESCE(t.category_en, NULLIF(BTRIM(p.product_category_name), '')) END, "
            "NULLIF(BTRIM(p.product_name_lenght), '')::INTEGER, "
            "NULLIF(BTRIM(p.product_description_lenght), '')::INTEGER, "
            "NULLIF(BTRIM(p.product_photos_qty), '')::INTEGER, "
            "NULLIF(BTRIM(p.product_weight_g), '')::NUMERIC(10,2), "
            "NULLIF(BTRIM(p.product_length_cm), '')::NUMERIC(10,2), "
            "NULLIF(BTRIM(p.product_height_cm), '')::NUMERIC(10,2), "
            "NULLIF(BTRIM(p.product_width_cm), '')::NUMERIC(10,2) "
            "FROM raw.olist_products p LEFT JOIN core.category_translation t "
            "ON t.category_pt = NULLIF(BTRIM(p.product_category_name), '') "
            "WHERE NULLIF(BTRIM(p.product_id), '') IS NOT NULL"
        )
    )

    zip_value = "NULLIF(BTRIM(geolocation_zip_code_prefix), '')::INTEGER"
    lat_value = "NULLIF(BTRIM(geolocation_lat), '')::NUMERIC"
    lng_value = "NULLIF(BTRIM(geolocation_lng), '')::NUMERIC"
    city_value = _sql_location("geolocation_city")
    state_value = _sql_location("geolocation_state")
    conn.execute(
        text(
            "WITH normalized AS ("
            f"SELECT {zip_value} AS zip_prefix, {lat_value} AS lat, {lng_value} AS lng, "
            f"{city_value} AS city, {state_value} AS state "
            "FROM raw.olist_geolocation "
            "WHERE NULLIF(BTRIM(geolocation_zip_code_prefix), '') IS NOT NULL"
            "), coordinates AS ("
            "SELECT zip_prefix, AVG(lat) AS lat, AVG(lng) AS lng "
            "FROM normalized GROUP BY zip_prefix"
            "), city_modes AS ("
            "SELECT zip_prefix, city, ROW_NUMBER() OVER ("
            "PARTITION BY zip_prefix ORDER BY COUNT(*) DESC, city ASC) AS rank "
            "FROM normalized WHERE city IS NOT NULL GROUP BY zip_prefix, city"
            "), state_modes AS ("
            "SELECT zip_prefix, state, ROW_NUMBER() OVER ("
            "PARTITION BY zip_prefix ORDER BY COUNT(*) DESC, state ASC) AS rank "
            "FROM normalized WHERE state IS NOT NULL GROUP BY zip_prefix, state"
            ") INSERT INTO core.geolocation (zip_prefix, lat, lng, city, state) "
            "SELECT c.zip_prefix, c.lat, c.lng, cm.city, sm.state FROM coordinates c "
            "LEFT JOIN city_modes cm ON cm.zip_prefix = c.zip_prefix AND cm.rank = 1 "
            "LEFT JOIN state_modes sm ON sm.zip_prefix = c.zip_prefix AND sm.rank = 1"
        )
    )

    order_orphans = conn.execute(
        text(
            "SELECT COUNT(*) FROM raw.olist_orders o LEFT JOIN core.customers c "
            "ON c.customer_id = NULLIF(BTRIM(o.customer_id), '') "
            "WHERE NULLIF(BTRIM(o.order_id), '') IS NULL OR c.customer_id IS NULL"
        )
    ).scalar_one()
    dropped["orphan.orders.customer"] = order_orphans
    conn.execute(
        text(
            "INSERT INTO core.orders (order_id, customer_id, order_status, purchase_ts, "
            "approved_ts, delivered_carrier_ts, delivered_customer_ts, estimated_delivery_ts) "
            "SELECT NULLIF(BTRIM(o.order_id), ''), c.customer_id, "
            "NULLIF(BTRIM(o.order_status), ''), "
            "NULLIF(BTRIM(o.order_purchase_timestamp), '')::TIMESTAMP, "
            "NULLIF(BTRIM(o.order_approved_at), '')::TIMESTAMP, "
            "NULLIF(BTRIM(o.order_delivered_carrier_date), '')::TIMESTAMP, "
            "NULLIF(BTRIM(o.order_delivered_customer_date), '')::TIMESTAMP, "
            "NULLIF(BTRIM(o.order_estimated_delivery_date), '')::TIMESTAMP "
            "FROM raw.olist_orders o JOIN core.customers c "
            "ON c.customer_id = NULLIF(BTRIM(o.customer_id), '') "
            "WHERE NULLIF(BTRIM(o.order_id), '') IS NOT NULL"
        )
    )

    item_order_orphans = conn.execute(
        text(
            "SELECT COUNT(*) FROM raw.olist_order_items i LEFT JOIN core.orders o "
            "ON o.order_id = NULLIF(BTRIM(i.order_id), '') "
            "WHERE NULLIF(BTRIM(i.order_id), '') IS NULL OR o.order_id IS NULL"
        )
    ).scalar_one()
    item_product_orphans = conn.execute(
        text(
            "SELECT COUNT(*) FROM raw.olist_order_items i LEFT JOIN core.products p "
            "ON p.product_id = NULLIF(BTRIM(i.product_id), '') "
            "WHERE NULLIF(BTRIM(i.product_id), '') IS NOT NULL AND p.product_id IS NULL"
        )
    ).scalar_one()
    item_seller_orphans = conn.execute(
        text(
            "SELECT COUNT(*) FROM raw.olist_order_items i LEFT JOIN core.sellers s "
            "ON s.seller_id = NULLIF(BTRIM(i.seller_id), '') "
            "WHERE NULLIF(BTRIM(i.seller_id), '') IS NOT NULL AND s.seller_id IS NULL"
        )
    ).scalar_one()
    dropped["orphan.order_items.orders"] = item_order_orphans
    dropped["orphan.order_items.products"] = 0
    dropped["orphan.order_items.sellers"] = item_seller_orphans
    if item_product_orphans:
        conn.execute(
            text("INSERT INTO core.products (product_id) VALUES ('unknown') ON CONFLICT DO NOTHING")
        )

    conn.execute(
        text(
            "INSERT INTO core.order_items (order_id, order_item_id, product_id, seller_id, "
            "shipping_limit_ts, price, freight_value) "
            "SELECT o.order_id, NULLIF(BTRIM(i.order_item_id), '')::INTEGER, "
            "CASE WHEN NULLIF(BTRIM(i.product_id), '') IS NOT NULL AND p.product_id IS NULL "
            "THEN 'unknown' ELSE NULLIF(BTRIM(i.product_id), '') END, "
            "s.seller_id, NULLIF(BTRIM(i.shipping_limit_date), '')::TIMESTAMP, "
            "NULLIF(BTRIM(i.price), '')::NUMERIC(12,2), "
            "COALESCE(NULLIF(BTRIM(i.freight_value), '')::NUMERIC(12,2), 0) "
            "FROM raw.olist_order_items i JOIN core.orders o "
            "ON o.order_id = NULLIF(BTRIM(i.order_id), '') "
            "LEFT JOIN core.products p ON p.product_id = NULLIF(BTRIM(i.product_id), '') "
            "LEFT JOIN core.sellers s ON s.seller_id = NULLIF(BTRIM(i.seller_id), '') "
            "WHERE (NULLIF(BTRIM(i.seller_id), '') IS NULL OR s.seller_id IS NOT NULL) "
            "AND NULLIF(BTRIM(i.order_item_id), '') IS NOT NULL"
        )
    )

    payment_orphans = conn.execute(
        text(
            "SELECT COUNT(*) FROM raw.olist_order_payments p LEFT JOIN core.orders o "
            "ON o.order_id = NULLIF(BTRIM(p.order_id), '') "
            "WHERE NULLIF(BTRIM(p.order_id), '') IS NULL OR o.order_id IS NULL"
        )
    ).scalar_one()
    dropped["orphan.payments.orders"] = payment_orphans
    conn.execute(
        text(
            "INSERT INTO core.payments "
            "(order_id, payment_sequential, payment_type, installments, payment_value) "
            "SELECT o.order_id, NULLIF(BTRIM(p.payment_sequential), '')::INTEGER, "
            "NULLIF(BTRIM(p.payment_type), ''), "
            "NULLIF(BTRIM(p.payment_installments), '')::SMALLINT, "
            "NULLIF(BTRIM(p.payment_value), '')::NUMERIC(12,2) "
            "FROM raw.olist_order_payments p JOIN core.orders o "
            "ON o.order_id = NULLIF(BTRIM(p.order_id), '') "
            "WHERE NULLIF(BTRIM(p.payment_sequential), '') IS NOT NULL"
        )
    )
    not_defined_payments = conn.execute(
        text(
            "SELECT COUNT(*) FROM raw.olist_order_payments "
            "WHERE BTRIM(payment_type) = 'not_defined'"
        )
    ).scalar_one()
    zero_installments = conn.execute(
        text(
            "SELECT COUNT(*) FROM raw.olist_order_payments "
            "WHERE NULLIF(BTRIM(payment_installments), '')::SMALLINT = 0"
        )
    ).scalar_one()

    conn.execute(
        text(
            "CREATE TEMP TABLE phase3_review_ranked ON COMMIT DROP AS "
            "SELECT r.*, ROW_NUMBER() OVER (PARTITION BY review_id, order_id "
            "ORDER BY NULLIF(BTRIM(review_answer_timestamp), '')::TIMESTAMP DESC NULLS LAST, "
            "NULLIF(BTRIM(review_creation_date), '')::TIMESTAMP DESC NULLS LAST, "
            "COALESCE(review_comment_message, '') ASC, COALESCE(review_comment_title, '') ASC, "
            "COALESCE(review_score, '') ASC) AS review_rank "
            "FROM raw.olist_order_reviews r"
        )
    )
    review_duplicates = conn.execute(
        text("SELECT COUNT(*) FROM phase3_review_ranked WHERE review_rank > 1")
    ).scalar_one()
    review_orphans = conn.execute(
        text(
            "SELECT COUNT(*) FROM phase3_review_ranked r LEFT JOIN core.orders o "
            "ON o.order_id = NULLIF(BTRIM(r.order_id), '') "
            "WHERE r.review_rank = 1 "
            "AND (NULLIF(BTRIM(r.order_id), '') IS NULL OR o.order_id IS NULL)"
        )
    ).scalar_one()
    dropped["orphan.reviews.orders"] = review_orphans
    dropped["reviews.deduplication"] = review_duplicates
    conn.execute(
        text(
            "INSERT INTO core.reviews "
            "(review_id, order_id, review_score, title, message, creation_ts, answer_ts) "
            "SELECT NULLIF(BTRIM(r.review_id), ''), o.order_id, "
            "NULLIF(BTRIM(r.review_score), '')::SMALLINT, "
            "NULLIF(r.review_comment_title, ''), NULLIF(r.review_comment_message, ''), "
            "NULLIF(BTRIM(r.review_creation_date), '')::TIMESTAMP, "
            "NULLIF(BTRIM(r.review_answer_timestamp), '')::TIMESTAMP "
            "FROM phase3_review_ranked r JOIN core.orders o "
            "ON o.order_id = NULLIF(BTRIM(r.order_id), '') "
            "WHERE r.review_rank = 1 AND NULLIF(BTRIM(r.review_id), '') IS NOT NULL"
        )
    )

    conn.execute(
        text(
            "WITH order_stats AS ("
            "SELECT c.customer_unique_id, MIN(o.purchase_ts) AS first_order_ts, "
            "MAX(o.purchase_ts) AS last_order_ts FROM core.customers c "
            "LEFT JOIN core.orders o ON o.customer_id = c.customer_id "
            "GROUP BY c.customer_unique_id"
            "), latest_location AS ("
            "SELECT DISTINCT ON (c.customer_unique_id) c.customer_unique_id, c.state, c.city "
            "FROM core.customers c JOIN core.orders o ON o.customer_id = c.customer_id "
            "ORDER BY c.customer_unique_id, o.purchase_ts DESC, o.order_id DESC"
            ") INSERT INTO core.dim_customer_unique "
            "(customer_unique_id, first_order_ts, last_order_ts, state, city) "
            "SELECT s.customer_unique_id, s.first_order_ts, s.last_order_ts, "
            "l.state, l.city FROM order_stats s LEFT JOIN latest_location l "
            "ON l.customer_unique_id = s.customer_unique_id"
        )
    )

    source_notes = {
        "olist_customers": (
            "Customer grain is customer_id; persistent identity is customer_unique_id."
        ),
        "olist_orders": f"Dropped {order_orphans} rows without a valid customer/order key.",
        "olist_order_items": (
            f"Dropped {item_order_orphans} invalid-order and "
            f"{item_seller_orphans} invalid-seller rows; "
            f"remapped {item_product_orphans} missing product references to unknown."
        ),
        "olist_order_payments": (
            f"Dropped {payment_orphans} rows without a valid order; preserved "
            f"not_defined={not_defined_payments} and installments=0={zero_installments}."
        ),
        "olist_order_reviews": (
            f"Dropped {review_duplicates} duplicate review rows and "
            f"{review_orphans} orphan-order rows; "
            "kept latest review_answer_timestamp."
        ),
        "olist_products": (
            f"Applied Portuguese fallback for {missing_translation} "
            "untranslated product categories; "
            f"preserved {missing_category} products without a category."
        ),
        "olist_sellers": "Typed source seller rows.",
        "olist_geolocation": (
            "Aggregated samples by zip prefix; mean coordinates and normalized city/state modes."
        ),
        "product_category_name_translation": "Typed source translations.",
    }

    for raw_table, core_table in CORE_SOURCE_TABLES.items():
        raw_rows = raw_counts[raw_table]
        core_rows = _count(conn, core_table)
        dropped_rows = max(raw_rows - core_rows, 0)
        if raw_table == "olist_order_reviews":
            dropped_rows = review_duplicates + review_orphans
        elif raw_table == "olist_orders":
            dropped_rows = order_orphans
        elif raw_table == "olist_order_payments":
            dropped_rows = payment_orphans
        _record_reconciliation(
            conn,
            run_ts,
            f"raw.{raw_table}",
            csv_counts[raw_table],
            raw_rows,
            core_rows,
            dropped_rows,
            source_notes[raw_table],
        )

    for table_name, count in dropped.items():
        note = "Orphan rows dropped before inserting core rows."
        if table_name == "orphan.order_items.products":
            note = (
                f"{item_product_orphans} orphan product references remapped "
                "to core.products.unknown."
            )
        elif table_name == "reviews.deduplication":
            note = "Duplicate (review_id, order_id) rows removed; latest answer timestamp retained."
        _record_reconciliation(conn, run_ts, table_name, None, None, None, count, note)

    _record_reconciliation(
        conn,
        run_ts,
        "core.dim_customer_unique",
        None,
        None,
        _count(conn, "dim_customer_unique"),
        0,
        "One row per customer_unique_id; dates span all order statuses; "
        "location from most recent order.",
    )

    for table in CORE_TABLES:
        conn.execute(text(f"ANALYZE core.{table}"))


def _decimal_money(value) -> Decimal:
    value = null_if_empty(value)
    if value is None:
        return Decimal("0.00")
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def _pandas_summary():
    customers = pd.read_csv(
        DATA_RAW / RAW_FILES["olist_customers"],
        dtype=str,
        keep_default_na=False,
        encoding="utf-8-sig",
    )
    orders = pd.read_csv(
        DATA_RAW / RAW_FILES["olist_orders"], dtype=str, keep_default_na=False, encoding="utf-8-sig"
    )
    items = pd.read_csv(
        DATA_RAW / RAW_FILES["olist_order_items"],
        dtype=str,
        keep_default_na=False,
        encoding="utf-8-sig",
    )
    sellers = pd.read_csv(
        DATA_RAW / RAW_FILES["olist_sellers"],
        dtype=str,
        keep_default_na=False,
        encoding="utf-8-sig",
    )

    customers["customer_id"] = customers["customer_id"].map(null_if_empty)
    customers["customer_unique_id"] = customers["customer_unique_id"].map(null_if_empty)
    customers = customers[customers["customer_id"].notna()]
    orders["order_id"] = orders["order_id"].map(null_if_empty)
    orders["customer_id"] = orders["customer_id"].map(null_if_empty)
    orders = orders[
        orders["order_id"].notna() & orders["customer_id"].isin(set(customers["customer_id"]))
    ]
    joined_orders = orders.merge(
        customers[["customer_id", "customer_unique_id"]], on="customer_id", how="inner"
    )
    delivered = orders[orders["order_status"] == "delivered"]
    delivered_ids = set(delivered["order_id"])
    valid_sellers = set(sellers["seller_id"].map(null_if_empty).dropna())
    items["order_id"] = items["order_id"].map(null_if_empty)
    items["seller_id"] = items["seller_id"].map(null_if_empty)
    delivered_items = items[
        items["order_id"].isin(delivered_ids)
        & (items["seller_id"].isna() | items["seller_id"].isin(valid_sellers))
    ]

    return {
        "delivered_orders": int(len(delivered)),
        "unique_customers_all_orders": int(joined_orders["customer_unique_id"].nunique()),
        "unique_customers_delivered": int(
            joined_orders[joined_orders["order_status"] == "delivered"][
                "customer_unique_id"
            ].nunique()
        ),
        "revenue": sum(
            (_decimal_money(value) for value in delivered_items["price"]), Decimal("0.00")
        ),
        "freight": sum(
            (_decimal_money(value) for value in delivered_items["freight_value"]), Decimal("0.00")
        ),
    }


def _sql_summary(conn):
    delivered_orders = conn.execute(
        text("SELECT COUNT(*) FROM core.orders WHERE order_status = 'delivered'")
    ).scalar_one()
    unique_all, unique_delivered = conn.execute(
        text(
            "SELECT COUNT(DISTINCT c.customer_unique_id), "
            "COUNT(DISTINCT c.customer_unique_id) FILTER (WHERE o.order_status = 'delivered') "
            "FROM core.orders o JOIN core.customers c ON c.customer_id = o.customer_id"
        )
    ).one()
    revenue, freight = conn.execute(
        text(
            "SELECT COALESCE(SUM(i.price), 0)::NUMERIC(18,2), "
            "COALESCE(SUM(i.freight_value), 0)::NUMERIC(18,2) "
            "FROM core.order_items i JOIN core.orders o ON o.order_id = i.order_id "
            "WHERE o.order_status = 'delivered'"
        )
    ).one()
    return {
        "delivered_orders": int(delivered_orders),
        "unique_customers_all_orders": int(unique_all),
        "unique_customers_delivered": int(unique_delivered),
        "revenue": Decimal(revenue).quantize(CENT),
        "freight": Decimal(freight).quantize(CENT),
    }


def _latest_reconciliation(conn):
    return conn.execute(
        text(
            "SELECT run_ts, table_name, csv_rows, raw_rows, core_rows, dropped_rows, note "
            "FROM core.load_reconciliation WHERE run_ts = (SELECT MAX(run_ts) "
            "FROM core.load_reconciliation) ORDER BY table_name"
        )
    ).all()


def sanity_report(write_report: bool = True):
    """Compare PostgreSQL totals with independent pandas calculations from source CSVs."""
    engine = get_engine()
    with engine.connect() as conn:
        core_counts = {table: _count(conn, table) for table in CORE_TABLES}
        sql_values = _sql_summary(conn)
        reconciliation = _latest_reconciliation(conn)

    pandas_values = _pandas_summary()
    matching = sql_values == pandas_values
    anchors = {
        "customers": (99_441, core_counts["customers"]),
        "orders": (99_441, core_counts["orders"]),
        "order_items": (112_650, core_counts["order_items"]),
        "payments": (103_886, core_counts["payments"]),
        "products": (32_951, core_counts["products"]),
        "sellers": (3_095, core_counts["sellers"]),
        "translations": (71, core_counts["category_translation"]),
        "delivered_orders": (96_478, sql_values["delivered_orders"]),
        "unique_customers_all_orders": (96_096, sql_values["unique_customers_all_orders"]),
        "unique_customers_delivered": (93_358, sql_values["unique_customers_delivered"]),
        "raw_reviews": (99_224, count_csv_rows(DATA_RAW / RAW_FILES["olist_order_reviews"])),
    }
    anchor_sources = {
        "customers": "olist_customers",
        "orders": "olist_orders",
        "order_items": "olist_order_items",
        "payments": "olist_order_payments",
        "products": "olist_products",
        "sellers": "olist_sellers",
        "translations": "product_category_name_translation",
        "raw_reviews": "olist_order_reviews",
    }
    anchor_lines = []
    reconciliation_notes = {row.table_name: row.note for row in reconciliation}
    for name, (expected, actual) in anchors.items():
        if expected == actual:
            anchor_lines.append(f"- {name}: {actual:,} (matches Phase 1 anchor).")
        else:
            source = anchor_sources.get(name)
            cause = reconciliation_notes.get(f"raw.{source}") if source else None
            if name == "delivered_orders":
                cause = reconciliation_notes.get("raw.olist_orders")
            elif name.startswith("unique_customers_"):
                cause = (
                    "Computed after valid customer/order relationships using customer_unique_id."
                )
            anchor_lines.append(
                f"- {name}: expected {expected:,}; observed {actual:,}. Cause/note: "
                f"{cause or 'no transformation note explains the difference; investigate.'}"
            )

    def money(value):
        return f"{value:,.2f}"

    lines = [
        "# Phase 3 load sanity report",
        "",
        f"SQL and pandas metrics: **{'MATCH' if matching else 'MISMATCH'}**.",
        "",
        "## Core row counts",
        "",
        "| Core table | Rows |",
        "|---|---:|",
    ]
    lines.extend(f"| `{table}` | {count:,} |" for table, count in core_counts.items())
    lines.extend(
        [
            "",
            "## SQL and independent pandas metrics",
            "",
            "| Metric | PostgreSQL | pandas from CSVs |",
            "|---|---:|---:|",
            f"| Delivered orders | {sql_values['delivered_orders']:,} | "
            f"{pandas_values['delivered_orders']:,} |",
            "| Distinct customer_unique_id, all orders | "
            f"{sql_values['unique_customers_all_orders']:,} | "
            f"{pandas_values['unique_customers_all_orders']:,} |",
            "| Distinct customer_unique_id, delivered orders | "
            f"{sql_values['unique_customers_delivered']:,} | "
            f"{pandas_values['unique_customers_delivered']:,} |",
            "| Delivered merchandise revenue (BRL) | "
            f"{money(sql_values['revenue'])} | {money(pandas_values['revenue'])} |",
            "| Delivered freight (BRL, separate) | "
            f"{money(sql_values['freight'])} | {money(pandas_values['freight'])} |",
            "",
            "Revenue is `SUM(order_items.price)` for delivered orders; freight is excluded.",
            "",
            "## Phase 1 anchors",
            "",
            *anchor_lines,
            "",
            "## Latest reconciliation",
            "",
            "| Run UTC | Table | CSV | Raw | Core | Dropped | Note |",
            "|---|---|---:|---:|---:|---:|---|",
        ]
    )
    for row in reconciliation:
        cells = [
            row.run_ts.isoformat(),
            row.table_name,
            "" if row.csv_rows is None else f"{row.csv_rows:,}",
            "" if row.raw_rows is None else f"{row.raw_rows:,}",
            "" if row.core_rows is None else f"{row.core_rows:,}",
            "" if row.dropped_rows is None else f"{row.dropped_rows:,}",
            (row.note or "").replace("|", "\\|").replace("\n", " "),
        ]
        lines.append("| " + " | ".join(cells) + " |")
    report = "\n".join(lines) + "\n"
    print(report, end="")
    if write_report:
        DOCS_DIR.mkdir(parents=True, exist_ok=True)
        (DOCS_DIR / "load_report.md").write_text(report, encoding="utf-8")
    if not matching:
        raise RuntimeError(
            f"SQL and pandas sanity totals differ: SQL={sql_values}, pandas={pandas_values}"
        )
    return {"sql": sql_values, "pandas": pandas_values, "core_rows": core_counts}


def _load_attempt(engine, run_ts, csv_counts):
    """Run a complete transactional raw COPY and core rebuild attempt."""
    raw_tables = ", ".join(f"raw.{table}" for table in RAW_FILES)
    core_tables = ", ".join(f"core.{table}" for table in CORE_TRUNCATE_ORDER)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE TABLE {raw_tables} RESTART IDENTITY"))
        conn.execute(text(f"TRUNCATE TABLE {core_tables}"))

        dbapi_connection = conn.connection.driver_connection
        with dbapi_connection.cursor() as cursor:
            for table, filename in RAW_FILES.items():
                copy_sql = f"COPY raw.{table} FROM STDIN WITH CSV HEADER ENCODING 'UTF8'"
                csv_path = DATA_RAW / filename
                with csv_path.open("r", encoding="utf-8-sig", newline="") as csv_stream:
                    cursor.copy_expert(copy_sql, csv_stream)

        raw_counts = {
            table: conn.execute(text(f"SELECT COUNT(*) FROM raw.{table}")).scalar_one()
            for table in RAW_FILES
        }
        mismatches = {
            table: (csv_counts[table], raw_counts[table])
            for table in RAW_FILES
            if csv_counts[table] != raw_counts[table]
        }
        if mismatches:
            raise RuntimeError(f"CSV/COPY row-count reconciliation failed: {mismatches}")

        _load_core(conn, run_ts, csv_counts, raw_counts)
    return sanity_report()


def _transient_database_error(error: Exception) -> bool:
    """Detect connection shutdowns in the exception chain without retrying data errors."""
    pending = [error]
    seen = set()
    markers = (
        "adminshutdown",
        "terminating connection",
        "unexpected eof",
        "server closed the connection",
        "connection reset by peer",
        "ssl syscall",
    )
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        if any(marker in str(current).lower() for marker in markers):
            return True
        if current.__class__.__name__ == "AdminShutdown":
            return True
        for chained in (
            getattr(current, "orig", None),
            getattr(current, "__cause__", None),
            getattr(current, "__context__", None),
        ):
            if chained is not None:
                pending.append(chained)
    return isinstance(error, (OperationalError, InterfaceError))


def load_data():
    """Copy source CSVs and rebuild core tables, retrying transient connection shutdowns."""
    started = time.perf_counter()
    missing = [filename for filename in RAW_FILES.values() if not (DATA_RAW / filename).is_file()]
    if missing:
        raise FileNotFoundError(f"Missing Olist CSV files under {DATA_RAW}: {', '.join(missing)}")

    csv_counts = {
        table: count_csv_rows(DATA_RAW / filename) for table, filename in RAW_FILES.items()
    }
    run_ts = datetime.now(timezone.utc)
    engine = get_engine()
    try:
        for attempt in range(1, LOAD_PARAMS["retry_attempts"] + 1):
            try:
                summary = _load_attempt(engine, run_ts, csv_counts)
                break
            except (OperationalError, InterfaceError) as error:
                if attempt >= LOAD_PARAMS["retry_attempts"] or not _transient_database_error(error):
                    raise
                delay = LOAD_PARAMS["retry_backoff_seconds"] * (2 ** (attempt - 1))
                print(
                    "Transient database connection shutdown; "
                    f"retrying load attempt {attempt + 1} after {delay} second(s)."
                )
                engine.dispose()
                time.sleep(delay)
    except Exception:
        duration = time.perf_counter() - started
        print(f"Load failed after {duration:.2f} seconds.")
        raise

    duration = time.perf_counter() - started
    print(f"Load completed in {duration:.2f} seconds.")
    return {
        "run_ts": run_ts,
        "runtime_seconds": duration,
        "core_rows": summary["core_rows"],
        "sanity": summary,
    }


def main() -> int:
    load_data()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
