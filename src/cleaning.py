"""Cleaning transforms and parquet pipeline for Phase 6."""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from .config import DATA_PROCESSED
from .extract import _normalize_dtypes
from .validation import validate_clean_tables

PRODUCT_DIMENSIONS = (
    "weight_g",
    "length_cm",
    "height_cm",
    "width_cm",
    "name_length",
    "description_length",
    "photos_qty",
)
INPUT_FILES = {
    "orders": "orders_enriched.parquet",
    "customers": "customer_orders.parquet",
    "interactions": "interactions.parquet",
    "products": "products_enriched.parquet",
    "reviews": "reviews_clean.parquet",
}
OUTPUT_FILES = {name: f"{name}_clean.parquet" for name in INPUT_FILES}


def impute_product_dims(frame: pd.DataFrame) -> pd.DataFrame:
    """Flag missing dimensions, impute category medians, then global medians."""
    result = frame.copy()
    if "category_en" not in result:
        result["category_en"] = pd.Series(pd.NA, index=result.index, dtype="string")
    for column in PRODUCT_DIMENSIONS:
        if column not in result:
            result[column] = np.nan
        result[f"{column}_missing"] = result[column].isna().astype("boolean")
        numeric = pd.to_numeric(result[column], errors="coerce")
        category_medians = numeric.groupby(result["category_en"], observed=True).transform("median")
        global_median = numeric.median()
        result[column] = numeric.fillna(category_medians.fillna(global_median))
    if {"length_cm", "height_cm", "width_cm"}.issubset(result.columns):
        result["volume_cm3"] = result["length_cm"] * result["height_cm"] * result["width_cm"]
    return result


def normalize_text_geo(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize geographic and category labels, preserving review text verbatim."""
    from unidecode import unidecode

    result = frame.copy()
    for column in ("customer_city", "seller_city", "city"):
        if column in result:
            result[column] = (
                result[column]
                .map(
                    lambda value: (
                        unidecode(value).lower().strip() if isinstance(value, str) else value
                    )
                )
                .astype("string")
            )
    for column in ("customer_state", "seller_state", "state"):
        if column in result:
            result[column] = result[column].astype("string").str.strip().str.upper()
    for column in ("category_en", "category_name", "product_category_name"):
        if column in result:
            result[column] = (
                result[column]
                .map(
                    lambda value: (
                        unidecode(value).lower().strip() if isinstance(value, str) else value
                    )
                )
                .astype("string")
            )
    return result


def flag_inconsistencies(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Add boolean quality flags and return issue counts without dropping records."""
    result = frame.copy()
    purchase = pd.to_datetime(
        result.get("purchase_ts", pd.Series(pd.NaT, index=result.index)), errors="coerce"
    )
    checks = {
        "price_nonpositive": (
            pd.to_numeric(result["price"], errors="coerce").le(0)
            if "price" in result
            else pd.Series(False, index=result.index)
        ),
        "freight_exceeds_price": (
            pd.to_numeric(result["freight_value"], errors="coerce").gt(
                pd.to_numeric(result["price"], errors="coerce")
            )
            if {"freight_value", "price"}.issubset(result.columns)
            else pd.Series(False, index=result.index)
        ),
        "delivered_before_purchase": (
            pd.to_datetime(result["delivered_customer_ts"], errors="coerce").lt(purchase)
            if "delivered_customer_ts" in result
            else pd.Series(False, index=result.index)
        ),
        "approved_before_purchase": (
            pd.to_datetime(result["approved_ts"], errors="coerce").lt(purchase)
            if "approved_ts" in result
            else pd.Series(False, index=result.index)
        ),
        "estimated_before_purchase": (
            pd.to_datetime(result["estimated_delivery_ts"], errors="coerce").lt(purchase)
            if "estimated_delivery_ts" in result
            else pd.Series(False, index=result.index)
        ),
    }
    rows = []
    for name, values in checks.items():
        result[name] = values.fillna(False).astype("boolean")
        rows.append({"issue": name, "count": int(result[name].sum())})
    if "order_status" in result and "delivered_customer_ts" in result:
        missing = (
            result["order_status"].astype("string").eq("delivered")
            & result["delivered_customer_ts"].isna()
        )
    elif "is_delivered" in result and "delivered_customer_ts" in result:
        missing = (
            result["is_delivered"].fillna(False).astype(bool)
            & result["delivered_customer_ts"].isna()
        )
    else:
        missing = pd.Series(False, index=result.index)
    result["missing_delivery_ts_on_delivered"] = missing.astype("boolean")
    rows.append({"issue": "missing_delivery_ts_on_delivered", "count": int(missing.sum())})
    return result, pd.DataFrame(rows)


def dedupe_reviews(frame: pd.DataFrame) -> pd.DataFrame:
    """Keep the latest review row for each order, using source timestamps."""
    timestamp = "creation_ts" if "creation_ts" in frame else "review_ts"
    if "order_id" not in frame or timestamp not in frame:
        raise ValueError("Review deduplication requires order_id and creation_ts or review_ts")
    result = frame.copy()
    result[timestamp] = pd.to_datetime(result[timestamp], errors="coerce")
    return (
        result.sort_values([timestamp], na_position="first", kind="stable")
        .drop_duplicates("order_id", keep="last")
        .reset_index(drop=True)
    )


def winsorize_for_model(series: pd.Series, lower: float, upper: float) -> pd.Series:
    """Return a percentile-capped copy; the source series is never mutated."""
    if not 0 <= lower < upper <= 1:
        raise ValueError("lower and upper must satisfy 0 <= lower < upper <= 1")
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.dropna().empty:
        return numeric.copy()
    low_value, high_value = numeric.quantile([lower, upper])
    return numeric.clip(lower=low_value, upper=high_value)


def quality_summary(
    before: dict[str, pd.DataFrame], after: dict[str, pd.DataFrame]
) -> pd.DataFrame:
    """Compare row counts, null rates and duplicate-row counts by table."""
    rows = []
    for table in before:
        old, new = before[table], after[table]
        common_columns = old.columns.intersection(new.columns)
        old_common = old.loc[:, common_columns]
        new_common = new.loc[:, common_columns]
        rows.append(
            {
                "table": table,
                "rows_before": len(old),
                "rows_after": len(new),
                "null_rate_before": (
                    float(old_common.isna().to_numpy().mean()) if old_common.size else 0.0
                ),
                "null_rate_after": (
                    float(new_common.isna().to_numpy().mean()) if new_common.size else 0.0
                ),
                "duplicate_rows_before": int(old.duplicated().sum()),
                "duplicate_rows_after": int(new.duplicated().sum()),
            }
        )
    return pd.DataFrame(rows)


def _clean_one(name: str, frame: pd.DataFrame) -> pd.DataFrame:
    result = normalize_text_geo(frame)
    if name == "products":
        result = impute_product_dims(result)
        if "price_mean" in result:
            result["price_capped"] = winsorize_for_model(result["price_mean"], 0.01, 0.99)
        for column in ("weight_g", "length_cm", "height_cm", "width_cm", "volume_cm3"):
            if column in result:
                result[column] = pd.to_numeric(result[column], errors="coerce").astype("float32")
        for column in ("name_length", "description_length", "photos_qty"):
            if column in result:
                result[column] = pd.to_numeric(result[column], errors="coerce").astype("Int32")
    if name == "orders":
        result, _ = flag_inconsistencies(result)
        result["price_capped"] = winsorize_for_model(result["price"], 0.01, 0.99)
        result["freight_capped"] = winsorize_for_model(result["freight_value"], 0.01, 0.99)
        result = result.loc[pd.to_numeric(result["price"], errors="coerce").ge(0)].copy()
    if name == "customers":
        result = result.rename(columns={"state": "customer_state"})
    if name == "reviews":
        result = dedupe_reviews(result)
    result = _normalize_dtypes(result)
    for column in result.columns:
        if column.endswith("_id") and column != "order_item_id":
            result[column] = result[column].astype("string")
    return result


def build_clean_tables(in_dir: Path = DATA_PROCESSED, out_dir: Path | None = None) -> dict:
    """Clean the five Phase 5 parquet tables and validate written outputs."""
    in_dir = Path(in_dir)
    out_dir = Path(out_dir) if out_dir is not None else DATA_PROCESSED / "clean"
    source_frames = {}
    cleaned = {}
    inconsistency_summary = None
    for name, filename in INPUT_FILES.items():
        source = in_dir / filename
        if not source.is_file():
            raise FileNotFoundError(f"Required Phase 5 parquet file is missing: {source}")
        frame = pd.read_parquet(source)
        if name == "products":
            raw_products = in_dir.parent / "raw" / "olist_products_dataset.csv"
            if raw_products.is_file():
                dimensions = pd.read_csv(raw_products)
                dimensions = dimensions.rename(
                    columns={
                        "product_length_cm": "length_cm",
                        "product_height_cm": "height_cm",
                        "product_width_cm": "width_cm",
                        "product_weight_g": "weight_g",
                        "product_name_lenght": "name_length",
                        "product_description_lenght": "description_length",
                        "product_photos_qty": "photos_qty",
                    }
                )
                dimension_columns = [
                    "product_id",
                    "length_cm",
                    "height_cm",
                    "width_cm",
                    "weight_g",
                    "name_length",
                    "description_length",
                    "photos_qty",
                ]
                frame = frame.drop(
                    columns=[column for column in dimension_columns[1:] if column in frame.columns]
                ).merge(
                    dimensions[dimension_columns],
                    on="product_id",
                    how="left",
                    validate="one_to_one",
                )
        source_frames[name] = frame
        if name == "orders":
            _, inconsistency_summary = flag_inconsistencies(frame)
        cleaned[name] = _clean_one(name, frame)
    summary = quality_summary(source_frames, cleaned)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in cleaned.items():
        frame.to_parquet(out_dir / OUTPUT_FILES[name], compression="snappy", index=False)
    validate_clean_tables(out_dir)
    print(summary.to_string(index=False))
    print("Order inconsistency flags:")
    print(inconsistency_summary.to_string(index=False))
    print(f"Clean parquet tables validated in {out_dir}")
    return {
        "frames": cleaned,
        "quality_summary": summary,
        "inconsistency_summary": inconsistency_summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean Phase 5 parquet tables")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("run", help="build and validate clean parquet tables")
    if parser.parse_args().command == "run":
        build_clean_tables()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
