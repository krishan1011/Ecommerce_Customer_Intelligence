"""Pandera schemas and validation command for Phase 5 parquet tables."""

import argparse
from pathlib import Path

import pandas as pd
import pandera.pandas as pa

from .config import ANALYSIS_END, ANALYSIS_START, DATA_PROCESSED

TABLE_FILES = {
    "orders_enriched": "orders_enriched.parquet",
    "customer_orders": "customer_orders.parquet",
    "interactions": "interactions.parquet",
    "products_enriched": "products_enriched.parquet",
    "reviews_clean": "reviews_clean.parquet",
}
CLEAN_TABLE_FILES = {
    "orders_clean": "orders_clean.parquet",
    "customers_clean": "customers_clean.parquet",
    "interactions_clean": "interactions_clean.parquet",
    "products_clean": "products_clean.parquet",
    "reviews_clean": "reviews_clean.parquet",
}


def _window_checks():
    lower = pd.Timestamp(ANALYSIS_START)
    upper = pd.Timestamp(ANALYSIS_END) + pd.Timedelta(days=1)
    return pa.Check(lambda series: series.ge(lower) & series.lt(upper))


def _category(nullable=False, checks=None):
    return pa.Column(pa.Category, nullable=nullable, checks=checks)


def _string(nullable=False):
    return pa.Column(pa.String, nullable=nullable)


def _timestamp(nullable=False, in_window=False):
    checks = [_window_checks()] if in_window else None
    return pa.Column(pa.DateTime, nullable=nullable, checks=checks)


def _integer(nullable=False, checks=None):
    dtype_check = pa.Check(lambda series: pd.api.types.is_integer_dtype(series.dtype))
    column_checks = [dtype_check] + ([checks] if checks is not None else [])
    return pa.Column(nullable=nullable, checks=column_checks)


def _float(nullable=False, checks=None):
    dtype_check = pa.Check(lambda series: pd.api.types.is_float_dtype(series.dtype))
    column_checks = [dtype_check] + ([checks] if checks is not None else [])
    return pa.Column(nullable=nullable, checks=column_checks)


def _boolean(nullable=False):
    return pa.Column(
        nullable=nullable,
        checks=pa.Check(lambda series: pd.api.types.is_bool_dtype(series.dtype)),
    )


def _grain_check(columns):
    return pa.Check(
        lambda frame: not frame.duplicated(subset=columns).any(),
        error=f"duplicate rows at declared grain {columns}",
    )


def get_schemas() -> dict[str, pa.DataFrameSchema]:
    """Build strict DataFrameSchemas using the current params.yaml window."""
    nonnegative = pa.Check.ge(0)
    probability = pa.Check.in_range(0, 1)
    rating = pa.Check.in_range(1, 5)
    nullable_nonnegative = pa.Check.ge(0)
    return {
        "orders_enriched": pa.DataFrameSchema(
            {
                "order_id": _string(),
                "order_item_id": _integer(checks=nonnegative),
                "customer_unique_id": _string(),
                "customer_state": _category(nullable=True),
                "product_id": _string(nullable=True),
                "seller_id": _string(nullable=True),
                "seller_state": _category(nullable=True),
                "category_en": _category(nullable=True),
                "price": _float(checks=nonnegative),
                "freight_value": _float(checks=nonnegative),
                "order_status": _category(),
                "purchase_ts": _timestamp(in_window=True),
                "approved_ts": _timestamp(nullable=True),
                "delivered_carrier_ts": _timestamp(nullable=True),
                "delivered_customer_ts": _timestamp(nullable=True),
                "estimated_delivery_ts": _timestamp(nullable=True),
                "shipping_limit_ts": _timestamp(nullable=True),
                "is_delivered": _boolean(),
                "is_late": _boolean(nullable=True),
                "delivery_days": _float(nullable=True),
                "estimated_days": _float(nullable=True),
                "item_count_in_order": _integer(checks=pa.Check.ge(1)),
                "payment_type_main": _category(nullable=True),
                "max_installments": _integer(nullable=True, checks=nullable_nonnegative),
            },
            checks=[_grain_check(["order_id", "order_item_id"])],
            strict=True,
            name="orders_enriched",
        ),
        "customer_orders": pa.DataFrameSchema(
            {
                "customer_unique_id": _string(),
                "order_id": _string(),
                "purchase_ts": _timestamp(in_window=True),
                "order_value": _float(checks=nonnegative),
                "item_revenue": _float(checks=nonnegative),
                "freight": _float(checks=nonnegative),
                "n_items": _integer(checks=pa.Check.ge(1)),
                "n_categories": _integer(checks=nonnegative),
                "state": _category(nullable=True),
                "is_late": _boolean(nullable=True),
                "review_score": _integer(nullable=True, checks=rating),
                "review_ts": _timestamp(nullable=True),
            },
            checks=[_grain_check(["customer_unique_id", "order_id"])],
            strict=True,
            name="customer_orders",
        ),
        "interactions": pa.DataFrameSchema(
            {
                "customer_unique_id": _string(),
                "product_id": _string(),
                "category_en": _category(nullable=True),
                "order_id": _string(),
                "purchase_ts": _timestamp(in_window=True),
                "price": _float(checks=nonnegative),
                "quantity": _integer(checks=pa.Check.ge(1)),
            },
            checks=[_grain_check(["customer_unique_id", "product_id", "order_id"])],
            strict=True,
            name="interactions",
        ),
        "products_enriched": pa.DataFrameSchema(
            {
                "product_id": _string(),
                "category_en": _category(nullable=True),
                "price_mean": _float(nullable=True, checks=nullable_nonnegative),
                "price_min": _float(nullable=True, checks=nullable_nonnegative),
                "price_max": _float(nullable=True, checks=nullable_nonnegative),
                "name_length": _integer(nullable=True, checks=nullable_nonnegative),
                "description_length": _integer(nullable=True, checks=nullable_nonnegative),
                "photos_qty": _integer(nullable=True, checks=nullable_nonnegative),
                "weight_g": _float(nullable=True, checks=nullable_nonnegative),
                "volume_cm3": _float(nullable=True, checks=nullable_nonnegative),
                "n_orders": _integer(checks=nullable_nonnegative),
                "units_sold": _integer(checks=nullable_nonnegative),
                "first_sale_ts": _timestamp(nullable=True),
                "last_sale_ts": _timestamp(nullable=True),
                "review_count": _integer(checks=nullable_nonnegative),
                "review_avg": _float(nullable=True, checks=rating),
                "share_low_score": _float(nullable=True, checks=probability),
            },
            checks=[_grain_check(["product_id"])],
            strict=True,
            name="products_enriched",
        ),
        "reviews_clean": pa.DataFrameSchema(
            {
                "review_id": _string(),
                "order_id": _string(),
                "customer_unique_id": _string(),
                "review_score": _integer(checks=rating),
                "title": _string(nullable=True),
                "message": _string(nullable=True),
                "review_text": _string(nullable=True),
                "has_text": _boolean(),
                "creation_ts": _timestamp(nullable=True),
                "answer_ts": _timestamp(nullable=True),
                "order_purchase_ts": _timestamp(in_window=True),
                "delivered_customer_ts": _timestamp(nullable=True),
                "is_late": _boolean(nullable=True),
                "n_products": _integer(checks=nonnegative),
                "n_sellers": _integer(checks=nonnegative),
                "primary_product_id": _string(nullable=True),
                "category_en": _category(nullable=True),
                "single_product_order": _boolean(),
            },
            checks=[_grain_check(["review_id", "order_id"])],
            strict=True,
            name="reviews_clean",
        ),
    }


def validate_frame(table_name: str, frame: pd.DataFrame) -> pd.DataFrame:
    """Validate a DataFrame against its modeling table schema."""
    return get_schemas()[table_name].validate(frame)


def validate_all(directory: Path = DATA_PROCESSED) -> dict[str, int]:
    """Validate every extracted parquet file; schema failures propagate."""
    schemas = get_schemas()
    counts = {}
    for name, filename in TABLE_FILES.items():
        path = directory / filename
        if not path.is_file():
            raise FileNotFoundError(f"Required modeling table is missing: {path}")
        frame = pd.read_parquet(path)
        schemas[name].validate(frame)
        counts[name] = len(frame)
        print(f"{name}: VALID ({len(frame):,} rows)")
    print("All modeling parquet tables passed Pandera validation.")
    return counts


def get_clean_schemas() -> dict[str, pa.DataFrameSchema]:
    """Schemas for Phase 6 outputs; extra source and quality columns are retained."""
    nonnegative = pa.Check.ge(0)
    return {
        "orders_clean": pa.DataFrameSchema(
            {
                "order_id": _string(),
                "order_item_id": _integer(checks=nonnegative),
                "customer_unique_id": _string(),
                "price": _float(checks=nonnegative),
                "purchase_ts": _timestamp(in_window=True),
                "price_nonpositive": _boolean(),
                "freight_exceeds_price": _boolean(),
                "delivered_before_purchase": _boolean(),
                "approved_before_purchase": _boolean(),
                "estimated_before_purchase": _boolean(),
                "missing_delivery_ts_on_delivered": _boolean(),
            },
            checks=[_grain_check(["order_id", "order_item_id"])],
            strict=False,
            name="orders_clean",
        ),
        "customers_clean": pa.DataFrameSchema(
            {
                "customer_unique_id": _string(),
                "order_id": _string(),
                "purchase_ts": _timestamp(in_window=True),
                "item_revenue": _float(checks=nonnegative),
            },
            checks=[_grain_check(["customer_unique_id", "order_id"])],
            strict=False,
            name="customers_clean",
        ),
        "interactions_clean": pa.DataFrameSchema(
            {
                "customer_unique_id": _string(),
                "product_id": _string(),
                "order_id": _string(),
                "purchase_ts": _timestamp(in_window=True),
                "price": _float(checks=nonnegative),
            },
            checks=[_grain_check(["customer_unique_id", "product_id", "order_id"])],
            strict=False,
            name="interactions_clean",
        ),
        "products_clean": pa.DataFrameSchema(
            {
                "product_id": _string(),
                "weight_g": _float(nullable=True, checks=nonnegative),
                "volume_cm3": _float(nullable=True, checks=nonnegative),
                "name_length_missing": _boolean(),
                "description_length_missing": _boolean(),
                "photos_qty_missing": _boolean(),
                "weight_g_missing": _boolean(),
            },
            checks=[_grain_check(["product_id"])],
            strict=False,
            name="products_clean",
        ),
        "reviews_clean": pa.DataFrameSchema(
            {
                "review_id": _string(),
                "order_id": _string(),
                "customer_unique_id": _string(),
                "review_score": _integer(checks=pa.Check.in_range(1, 5)),
                "order_purchase_ts": _timestamp(in_window=True),
            },
            checks=[_grain_check(["order_id"])],
            strict=False,
            name="reviews_clean",
        ),
    }


def validate_clean_tables(directory: Path = DATA_PROCESSED / "clean") -> dict[str, int]:
    """Validate every Phase 6 clean parquet file and return row counts."""
    schemas = get_clean_schemas()
    counts = {}
    for name, filename in CLEAN_TABLE_FILES.items():
        path = directory / filename
        if not path.is_file():
            raise FileNotFoundError(f"Required clean parquet table is missing: {path}")
        frame = pd.read_parquet(path)
        schemas[name].validate(frame)
        counts[name] = len(frame)
        print(f"{name}: VALID ({len(frame):,} rows)")
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Phase 5 modeling tables")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("run", help="validate all data/processed parquet tables")
    args = parser.parse_args()
    if args.command == "run":
        validate_all()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
