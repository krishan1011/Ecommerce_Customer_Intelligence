import re
from pathlib import Path

SCHEMA_SQL = Path(__file__).resolve().parents[1] / "sql" / "01_schema.sql"
SQL = SCHEMA_SQL.read_text(encoding="utf-8")

RAW_HEADERS = {
    "olist_customers": (
        "customer_id customer_unique_id customer_zip_code_prefix customer_city customer_state"
    ),
    "olist_orders": (
        "order_id customer_id order_status order_purchase_timestamp order_approved_at "
        "order_delivered_carrier_date order_delivered_customer_date "
        "order_estimated_delivery_date"
    ),
    "olist_order_items": (
        "order_id order_item_id product_id seller_id shipping_limit_date price freight_value"
    ),
    "olist_order_payments": (
        "order_id payment_sequential payment_type payment_installments payment_value"
    ),
    "olist_order_reviews": (
        "review_id order_id review_score review_comment_title review_comment_message "
        "review_creation_date review_answer_timestamp"
    ),
    "olist_products": (
        "product_id product_category_name product_name_lenght product_description_lenght "
        "product_photos_qty product_weight_g product_length_cm product_height_cm "
        "product_width_cm"
    ),
    "olist_sellers": "seller_id seller_zip_code_prefix seller_city seller_state",
    "olist_geolocation": (
        "geolocation_zip_code_prefix geolocation_lat geolocation_lng geolocation_city "
        "geolocation_state"
    ),
    "product_category_name_translation": ("product_category_name product_category_name_english"),
}

CORE_TABLES = {
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
}


def table_body(schema: str, table: str) -> str:
    match = re.search(
        rf"CREATE\s+TABLE\s+{schema}\.{table}\s*\((.*?)\);", SQL, re.IGNORECASE | re.DOTALL
    )
    assert match, f"Missing CREATE TABLE {schema}.{table}"
    return match.group(1)


def test_raw_tables_match_olist_csv_headers_and_use_text_columns():
    found_tables = set(re.findall(r"CREATE\s+TABLE\s+raw\.(\w+)", SQL, re.IGNORECASE))
    assert found_tables == set(RAW_HEADERS)

    raw_dir = SCHEMA_SQL.parents[1] / "data" / "raw"
    for table_name, expected in RAW_HEADERS.items():
        body = table_body("raw", table_name)
        columns = re.findall(r"^\s*(\w+)\s+([A-Z]+)\s*,?\s*$", body, re.MULTILINE)
        assert [name for name, _ in columns] == expected.split()
        assert all(sql_type.upper() == "TEXT" for _, sql_type in columns)

        csv_path = raw_dir / f"{table_name}_dataset.csv"
        if table_name == "product_category_name_translation":
            csv_path = raw_dir / "product_category_name_translation.csv"
        if csv_path.exists():
            import csv

            with csv_path.open(encoding="utf-8-sig", newline="") as stream:
                assert next(csv.reader(stream)) == expected.split()


def test_core_table_set_and_required_constraints():
    found_tables = set(re.findall(r"CREATE\s+TABLE\s+core\.(\w+)", SQL, re.IGNORECASE))
    assert found_tables == CORE_TABLES

    items = table_body("core", "order_items")
    assert re.search(r"PRIMARY\s+KEY\s*\(\s*order_id\s*,\s*order_item_id\s*\)", items)

    orders = table_body("core", "orders")
    assert "purchase_ts TIMESTAMP NOT NULL" in orders
    assert all(
        f"'{status}'" in orders
        for status in (
            "created",
            "approved",
            "invoiced",
            "processing",
            "shipped",
            "delivered",
            "unavailable",
            "canceled",
        )
    )

    reviews = table_body("core", "reviews")
    assert re.search(r"PRIMARY\s+KEY\s*\(\s*review_id\s*,\s*order_id\s*\)", reviews)
    assert re.search(
        r"review_score\s+SMALLINT\s+NOT NULL\s+CHECK\s*\(\s*review_score\s+BETWEEN\s+1"
        r"\s+AND\s+5\s*\)",
        reviews,
    )

    products = table_body("core", "products")
    assert "REFERENCES core.category_translation" not in products
    for column in (
        "name_length",
        "description_length",
        "photos_qty",
        "weight_g",
        "length_cm",
        "height_cm",
        "width_cm",
    ):
        assert re.search(
            rf"{column}\s+[^\n]+CHECK\s*\(\s*{column}\s+IS NULL OR {column}\s*>=\s*0\s*\)",
            products,
        )

    assert re.search(
        r"CREATE\s+TABLE\s+core\.geolocation\s*\(\s*zip_prefix\s+INT\s+PRIMARY KEY", SQL
    )
    payments = table_body("core", "payments")
    assert "'not_defined'" in payments
    assert re.search(
        r"installments\s+SMALLINT\s+CHECK\s*\(\s*installments\s+IS NULL OR installments"
        r"\s*>=\s*0\s*\)",
        payments,
    )


def test_required_indexes_exist():
    indexes = {
        "idx_orders_customer_id": "core.orders(customer_id)",
        "idx_orders_purchase_ts": "core.orders(purchase_ts)",
        "idx_orders_order_status": "core.orders(order_status)",
        "idx_order_items_product_id": "core.order_items(product_id)",
        "idx_order_items_seller_id": "core.order_items(seller_id)",
        "idx_reviews_order_id": "core.reviews(order_id)",
        "idx_customers_customer_unique_id": "core.customers(customer_unique_id)",
        "idx_payments_order_id": "core.payments(order_id)",
        "idx_products_category_en": "core.products(category_en)",
    }
    for index, target in indexes.items():
        assert re.search(
            rf"CREATE\s+INDEX\s+{index}\s+ON\s+{re.escape(target)}", SQL, re.IGNORECASE
        )


def test_every_core_table_documents_grain_and_primary_key_columns():
    for table in CORE_TABLES:
        assert re.search(rf"COMMENT\s+ON\s+TABLE\s+core\.{table}\s+IS\s+'Grain:", SQL)

    for table, columns in {
        "category_translation": ("category_pt",),
        "customers": ("customer_id",),
        "sellers": ("seller_id",),
        "products": ("product_id",),
        "geolocation": ("zip_prefix",),
        "orders": ("order_id",),
        "order_items": ("order_id", "order_item_id"),
        "payments": ("order_id", "payment_sequential"),
        "reviews": ("review_id", "order_id"),
        "dim_customer_unique": ("customer_unique_id",),
    }.items():
        for column in columns:
            assert re.search(rf"COMMENT\s+ON\s+COLUMN\s+core\.{table}\.{column}\s+IS", SQL)
