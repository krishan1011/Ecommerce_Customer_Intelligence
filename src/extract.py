"""Extract configured analytics modeling views to reproducible parquet files."""

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from .config import DATA_PROCESSED, EXTRACTION_PARAMS, SQL_DIR

TABLES = {
    "orders_enriched": {
        "view": "model_orders_enriched",
        "timestamp": "purchase_ts",
        "order_by": "order_id, order_item_id",
    },
    "customer_orders": {
        "view": "model_customer_orders",
        "timestamp": "purchase_ts",
        "order_by": "customer_unique_id, order_id",
    },
    "interactions": {
        "view": "model_interactions",
        "timestamp": "purchase_ts",
        "order_by": "customer_unique_id, product_id, order_id",
    },
    "products_enriched": {
        "view": "model_products_enriched",
        "timestamp": "last_sale_ts",
        "order_by": "product_id",
    },
    "reviews_clean": {
        "view": "model_reviews_clean",
        "timestamp": "creation_ts",
        "order_by": "review_id, order_id",
    },
}

INTEGER_COLUMNS = {
    "order_item_id",
    "item_count_in_order",
    "max_installments",
    "n_items",
    "n_categories",
    "n_products",
    "n_sellers",
    "quantity",
    "name_length",
    "description_length",
    "photos_qty",
    "n_orders",
    "units_sold",
    "review_count",
    "review_score",
}
FLOAT32_COLUMNS = {"delivery_days", "estimated_days", "weight_g", "volume_cm3"}
FLOAT64_COLUMNS = {
    "price",
    "freight_value",
    "order_value",
    "item_revenue",
    "price_mean",
    "price_min",
    "price_max",
    "review_avg",
    "share_low_score",
}
STRING_COLUMNS = {
    "order_id",
    "customer_unique_id",
    "product_id",
    "seller_id",
    "review_id",
    "customer_state",
    "seller_state",
    "category_en",
    "order_status",
    "payment_type_main",
    "state",
    "title",
    "message",
    "review_text",
}
DATETIME_COLUMNS = {
    "purchase_ts",
    "approved_ts",
    "delivered_carrier_ts",
    "delivered_customer_ts",
    "estimated_delivery_ts",
    "shipping_limit_ts",
    "review_ts",
    "first_sale_ts",
    "last_sale_ts",
    "creation_ts",
    "answer_ts",
    "order_purchase_ts",
}
BOOLEAN_COLUMNS = {"is_delivered", "is_late", "has_text", "single_product_order"}


def _git_commit(root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _read_view(
    engine,
    view_name: str,
    order_by: str,
    chunksize: int = EXTRACTION_PARAMS["read_chunksize"],
) -> pd.DataFrame:
    query = text(f"SELECT * FROM analytics.{view_name} ORDER BY {order_by}")
    with engine.connect() as conn:
        chunks = list(pd.read_sql(query, conn, chunksize=chunksize))
    if not chunks:
        return pd.DataFrame()
    return pd.concat(chunks, ignore_index=True)


def _normalize_dtypes(frame: pd.DataFrame) -> pd.DataFrame:
    for column in frame.columns:
        if column in DATETIME_COLUMNS:
            frame[column] = pd.to_datetime(frame[column], errors="coerce")
        elif column in STRING_COLUMNS:
            frame[column] = frame[column].astype("string")
        elif column in INTEGER_COLUMNS:
            numeric = pd.to_numeric(frame[column], errors="raise", downcast="integer")
            if numeric.isna().any():
                nullable_dtype = "Int8" if column == "review_score" else "Int32"
                numeric = numeric.astype(nullable_dtype)
            frame[column] = numeric
        elif column in FLOAT32_COLUMNS:
            frame[column] = pd.to_numeric(frame[column], errors="raise").astype("float32")
        elif column in FLOAT64_COLUMNS:
            frame[column] = pd.to_numeric(frame[column], errors="raise").astype("float64")
        elif column in BOOLEAN_COLUMNS:
            frame[column] = frame[column].astype("boolean")

    for column in frame.select_dtypes(include=["string"]).columns:
        cardinality = frame[column].nunique(dropna=True)
        threshold = max(
            EXTRACTION_PARAMS["categorical_min_unique"],
            min(
                EXTRACTION_PARAMS["categorical_max_unique"],
                int(len(frame) * EXTRACTION_PARAMS["categorical_row_fraction"]),
            ),
        )
        if cardinality <= threshold:
            frame[column] = frame[column].astype("category")
    return frame


def _timestamp_range(frame: pd.DataFrame, column: str) -> dict[str, str | None]:
    if column not in frame or frame[column].dropna().empty:
        return {"column": column, "min": None, "max": None}
    values = frame[column].dropna()
    return {
        "column": column,
        "min": values.min().isoformat(),
        "max": values.max().isoformat(),
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_tables(output_dir: Path = DATA_PROCESSED) -> dict:
    """Refresh the configured model views, then write parquet and a manifest."""
    from .db import get_engine, run_views

    run_views()
    engine = get_engine()
    model_sql_path = SQL_DIR / "05_modeling_tables.sql"
    if not model_sql_path.is_file():
        raise FileNotFoundError(f"Modeling SQL file not found at {model_sql_path}")
    with engine.begin() as conn:
        conn.exec_driver_sql(model_sql_path.read_text(encoding="utf-8"))
    output_dir.mkdir(parents=True, exist_ok=True)
    extracted_at = datetime.now(timezone.utc).isoformat()
    root = output_dir.resolve().parents[1]
    git_commit = _git_commit(root)

    with engine.connect() as conn:
        config = conn.execute(text("""
                SELECT analysis_start, analysis_end, valid_statuses
                FROM analytics.config WHERE config_id = 1
                """)).mappings().one()
        window = {
            "analysis_start": config["analysis_start"].isoformat(),
            "analysis_end": config["analysis_end"].isoformat(),
            "valid_statuses": list(config["valid_statuses"]),
        }
        view_sql = {
            name: conn.execute(
                text("SELECT pg_get_viewdef(CAST(:view_name AS regclass), true)"),
                {"view_name": f"analytics.{spec['view']}"},
            ).scalar_one()
            for name, spec in TABLES.items()
        }

    manifest_files = {}
    report_rows = []
    for name, spec in TABLES.items():
        frame = _normalize_dtypes(_read_view(engine, spec["view"], spec["order_by"]))
        parquet_path = output_dir / f"{name}.parquet"
        frame.to_parquet(parquet_path, compression="snappy", index=False)
        timestamp_range = _timestamp_range(frame, spec["timestamp"])
        file_hash = _sha256_file(parquet_path)
        manifest_files[parquet_path.name] = {
            "view_name": f"analytics.{spec['view']}",
            "row_count": int(len(frame)),
            "columns": list(frame.columns),
            "dtypes": {column: str(dtype) for column, dtype in frame.dtypes.items()},
            "main_timestamp": timestamp_range,
            "file_size_bytes": parquet_path.stat().st_size,
            "extraction_timestamp_utc": extracted_at,
            "git_commit_hash": git_commit,
            "query_sha256": hashlib.sha256(view_sql[name].encode("utf-8")).hexdigest(),
            "parquet_sha256": file_hash,
            "analysis_window": window,
        }
        report_rows.append(
            {
                "file": parquet_path.name,
                "rows": len(frame),
                "columns": len(frame.columns),
                "size_mb": round(parquet_path.stat().st_size / (1024 * 1024), 2),
                "timestamp_range": f"{timestamp_range['min']} .. {timestamp_range['max']}",
            }
        )

    version_material = "\n".join(
        f"{name}:{spec['parquet_sha256']}" for name, spec in sorted(manifest_files.items())
    )
    manifest = {
        "data_version": hashlib.sha256(version_material.encode("utf-8")).hexdigest()[:12],
        "extraction_timestamp_utc": extracted_at,
        "git_commit_hash": git_commit,
        "analysis_window": window,
        "files": manifest_files,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print("| File | Rows | Columns | Size MiB | Main timestamp range |")
    print("|---|---:|---:|---:|---|")
    for row in report_rows:
        print(
            f"| {row['file']} | {row['rows']:,} | {row['columns']} | "
            f"{row['size_mb']:.2f} | {row['timestamp_range']} |"
        )
    print(f"Data version: {manifest['data_version']}")
    return manifest


def main() -> int:
    extract_tables()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
