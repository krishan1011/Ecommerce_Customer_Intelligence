"""Pandera schemas and validation command for Phase 5 parquet tables."""

import argparse
import json
from pathlib import Path

import pandas as pd
import pandera.pandas as pa

from .config import (
    ANALYSIS_END,
    ANALYSIS_START,
    DATA_PROCESSED,
    DOCS_DIR,
    ROOT,
    VALIDATION_PARAMS,
)

METRICS_PATH = ROOT / "metrics" / "validation.json"
REPORT_PATH = DOCS_DIR / "validation_report.md"

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
    nonnegative = pa.Check.ge(VALIDATION_PARAMS["nonnegative_minimum"])
    probability = pa.Check.in_range(
        VALIDATION_PARAMS["probability_min"], VALIDATION_PARAMS["probability_max"]
    )
    rating = pa.Check.in_range(
        VALIDATION_PARAMS["review_score_min"], VALIDATION_PARAMS["review_score_max"]
    )
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
                "item_count_in_order": _integer(
                    checks=pa.Check.ge(VALIDATION_PARAMS["minimum_count"])
                ),
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
                "n_items": _integer(checks=pa.Check.ge(VALIDATION_PARAMS["minimum_count"])),
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
                "quantity": _integer(checks=pa.Check.ge(VALIDATION_PARAMS["minimum_count"])),
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
    """Validate a modeling frame against its schema, collecting every hard failure."""
    return get_schemas()[table_name].validate(frame, lazy=True)


def get_clean_schemas() -> dict[str, pa.DataFrameSchema]:
    """Schemas for Phase 6 outputs; extra source and quality columns are retained."""
    nonnegative = pa.Check.ge(VALIDATION_PARAMS["nonnegative_minimum"])
    rating = pa.Check.in_range(
        VALIDATION_PARAMS["review_score_min"], VALIDATION_PARAMS["review_score_max"]
    )
    return {
        "clean_orders": pa.DataFrameSchema(
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
            name="clean_orders",
        ),
        "clean_customers": pa.DataFrameSchema(
            {
                "customer_unique_id": _string(),
                "order_id": _string(),
                "purchase_ts": _timestamp(in_window=True),
                "item_revenue": _float(checks=nonnegative),
            },
            checks=[_grain_check(["customer_unique_id", "order_id"])],
            strict=False,
            name="clean_customers",
        ),
        "clean_interactions": pa.DataFrameSchema(
            {
                "customer_unique_id": _string(),
                "product_id": _string(),
                "order_id": _string(),
                "purchase_ts": _timestamp(in_window=True),
                "price": _float(checks=nonnegative),
            },
            checks=[_grain_check(["customer_unique_id", "product_id", "order_id"])],
            strict=False,
            name="clean_interactions",
        ),
        "clean_products": pa.DataFrameSchema(
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
            name="clean_products",
        ),
        "clean_reviews": pa.DataFrameSchema(
            {
                "review_id": _string(),
                "order_id": _string(),
                "customer_unique_id": _string(),
                "review_score": _integer(checks=rating),
                "order_purchase_ts": _timestamp(in_window=True),
            },
            checks=[_grain_check(["order_id"])],
            strict=False,
            name="clean_reviews",
        ),
    }


class TableValidationError(ValueError):
    """Raised when a table violates one or more hard schema checks."""


def _schema_for(table_name: str) -> pa.DataFrameSchema:
    if table_name in TABLE_FILES:
        return get_schemas()[table_name]
    clean_schemas = get_clean_schemas()
    if table_name in clean_schemas:
        return clean_schemas[table_name]
    raise KeyError(f"Unknown validation table: {table_name}")


def _hard_failure_details(error: pa.errors.SchemaErrors) -> list[str]:
    failures = error.failure_cases
    details = []
    for row in failures.to_dict("records"):
        parts = [
            f"{key}={row[key]}"
            for key in ("column", "check", "index", "failure_case")
            if key in row and row[key] is not None
        ]
        details.append(", ".join(parts) or str(row))
    return details


def _soft_warnings(frame: pd.DataFrame, expected_rows: int | None = None) -> list[str]:
    warnings = []
    null_limit = VALIDATION_PARAMS["soft_null_rate_limit"]
    for column in frame.columns:
        rate = float(frame[column].isna().mean()) if len(frame) else 0.0
        if rate > null_limit:
            warnings.append(f"{column}: null rate {rate:.2%} exceeds configured {null_limit:.2%}")
    tolerance = VALIDATION_PARAMS["row_count_tolerance_pct"]
    if expected_rows:
        deviation = abs(len(frame) - expected_rows) / expected_rows * 100
        if deviation > tolerance:
            warnings.append(
                f"row count {len(frame):,} differs {deviation:.2f}% from manifest "
                f"count {expected_rows:,} (tolerance {tolerance:.2f}%)"
            )
    min_category_count = VALIDATION_PARAMS["unusual_category_min_count"]
    category_columns = [
        column
        for column in frame.columns
        if "category" in column.lower()
        or column in {"customer_state", "seller_state", "state", "payment_type_main"}
    ]
    for column in category_columns:
        counts = frame[column].value_counts(dropna=True)
        rare_count = int(counts.lt(min_category_count).sum())
        if rare_count:
            warnings.append(
                f"{column}: {rare_count} category value(s) occur fewer than "
                f"{min_category_count} rows"
            )
    return warnings


def validate_table(
    frame: pd.DataFrame,
    name: str,
    expected_rows: int | None = None,
    *,
    raise_on_error: bool = True,
) -> dict:
    """Return hard/soft validation results, raising only for hard schema failures."""
    hard_failures = []
    try:
        _schema_for(name).validate(frame, lazy=True)
    except pa.errors.SchemaErrors as error:
        hard_failures = _hard_failure_details(error)
    soft_warnings = _soft_warnings(frame, expected_rows)
    result = {
        "table": name,
        "rows": int(len(frame)),
        "hard_failures": len(hard_failures),
        "hard_failure_details": hard_failures,
        "soft_warnings": soft_warnings,
        "status": "FAIL" if hard_failures else "WARN" if soft_warnings else "PASS",
    }
    if hard_failures and raise_on_error:
        detail = "\n".join(f"- {failure}" for failure in hard_failures)
        raise TableValidationError(f"{name} has {len(hard_failures)} hard failure(s):\n{detail}")
    return result


def _manifest_row_counts(directory: Path) -> dict[str, int]:
    manifest_path = directory / "manifest.json"
    if not manifest_path.is_file():
        return {}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return {
            filename: int(details["row_count"])
            for filename, details in manifest.get("files", {}).items()
            if "row_count" in details
        }
    except (OSError, ValueError, TypeError):
        return {}


def _write_validation_report(results: list[dict]) -> None:
    METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    metrics = {
        "tables": results,
        "hard_failure_count": sum(row["hard_failures"] for row in results),
        "soft_warning_count": sum(len(row["soft_warnings"]) for row in results),
    }
    METRICS_PATH.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Validation report",
        "",
        "| Table | Rows | Hard failures | Soft warnings | Status |",
        "|---|---:|---:|---:|---|",
    ]
    for row in results:
        lines.append(
            f"| {row['table']} | {row['rows']:,} | {row['hard_failures']} | "
            f"{len(row['soft_warnings'])} | {row['status']} |"
        )
        for warning in row["soft_warnings"]:
            lines.append(f"\n  - Warning: {warning}")
        for failure in row["hard_failure_details"]:
            lines.append(f"\n  - Hard failure: {failure}")
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def validate_clean_tables(directory: Path = DATA_PROCESSED / "clean") -> dict[str, int]:
    """Validate every Phase 6 clean parquet file and return row counts."""
    schemas = get_clean_schemas()
    counts = {}
    names = dict(zip(CLEAN_TABLE_FILES, schemas, strict=True))
    for name, filename in CLEAN_TABLE_FILES.items():
        path = directory / filename
        if not path.is_file():
            raise FileNotFoundError(f"Required clean parquet table is missing: {path}")
        frame = pd.read_parquet(path)
        validate_table(frame, names[name])
        counts[name] = len(frame)
        print(f"{name}: VALID ({len(frame):,} rows)")
    return counts


def validate_all(directory: Path = DATA_PROCESSED) -> list[dict]:
    """Validate Phase 5 and available clean tables, then write JSON and Markdown reports."""
    manifest_counts = _manifest_row_counts(directory)
    results = []
    tables = [(name, filename, name) for name, filename in TABLE_FILES.items()]
    clean_directory = directory / "clean"
    present_clean = [
        (name, filename)
        for name, filename in CLEAN_TABLE_FILES.items()
        if (clean_directory / filename).is_file()
    ]
    if present_clean and len(present_clean) != len(CLEAN_TABLE_FILES):
        missing = sorted(
            set(CLEAN_TABLE_FILES.values()) - {filename for _, filename in present_clean}
        )
        raise FileNotFoundError(f"Incomplete clean parquet set under {clean_directory}: {missing}")
    clean_schema_names = list(get_clean_schemas())
    tables.extend(
        (f"clean/{name}", filename, schema_name)
        for (name, filename), schema_name in zip(
            CLEAN_TABLE_FILES.items(), clean_schema_names, strict=True
        )
        if present_clean
    )
    for table_label, filename, schema_name in tables:
        source_directory = clean_directory if schema_name.startswith("clean_") else directory
        path = source_directory / filename
        if not path.is_file():
            raise FileNotFoundError(f"Required validation table is missing: {path}")
        frame = pd.read_parquet(path)
        result = validate_table(
            frame,
            schema_name,
            expected_rows=manifest_counts.get(filename),
            raise_on_error=False,
        )
        result["table"] = table_label
        results.append(result)
    _write_validation_report(results)
    report = pd.DataFrame(
        [
            {
                "table": row["table"],
                "rows": row["rows"],
                "hard failures": row["hard_failures"],
                "soft warnings": len(row["soft_warnings"]),
                "status": row["status"],
            }
            for row in results
        ]
    )
    print(report.to_string(index=False))
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Phase 5 modeling tables")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("run", help="validate all data/processed parquet tables")
    args = parser.parse_args()
    if args.command == "run":
        results = validate_all()
        return int(any(row["hard_failures"] for row in results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
