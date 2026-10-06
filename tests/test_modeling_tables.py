import pandas as pd
import pytest
from sqlalchemy import text

from src.config import ANALYSIS_END, ANALYSIS_START, DATA_PROCESSED
from src.db import get_engine
from src.validation import TABLE_FILES


@pytest.fixture(scope="module")
def parquet_tables():
    missing = [name for name in TABLE_FILES.values() if not (DATA_PROCESSED / name).is_file()]
    if missing:
        pytest.skip("Phase 5 parquet files are not present under data/processed")
    return {
        name: pd.read_parquet(DATA_PROCESSED / filename) for name, filename in TABLE_FILES.items()
    }


def test_model_table_grains_keys_and_window(parquet_tables):
    orders = parquet_tables["orders_enriched"]
    customer_orders = parquet_tables["customer_orders"]
    interactions = parquet_tables["interactions"]
    products = parquet_tables["products_enriched"]
    reviews = parquet_tables["reviews_clean"]

    assert not orders.duplicated(["order_id", "order_item_id"]).any()
    assert not customer_orders.duplicated(["customer_unique_id", "order_id"]).any()
    assert not interactions.duplicated(["customer_unique_id", "product_id", "order_id"]).any()
    assert not products["product_id"].duplicated().any()
    assert not reviews.duplicated(["review_id", "order_id"]).any()

    for frame in (orders, customer_orders, interactions, reviews):
        assert frame["customer_unique_id"].notna().all()

    start = pd.Timestamp(ANALYSIS_START)
    end_exclusive = pd.Timestamp(ANALYSIS_END) + pd.Timedelta(days=1)
    assert orders["purchase_ts"].ge(start).all()
    assert orders["purchase_ts"].lt(end_exclusive).all()
    assert interactions["order_id"].isin(set(customer_orders["order_id"])).all()
    assert len(reviews) == reviews[["review_id", "order_id"]].drop_duplicates().shape[0]

    order_shapes = interactions.groupby("order_id").agg(
        n_products=("product_id", "nunique"), n_categories=("category_en", "nunique")
    )
    expected_single_product = (order_shapes["n_products"] == 1) & (
        order_shapes["n_categories"] == 1
    )
    expected_flags = (
        reviews["order_id"].map(expected_single_product).fillna(False).astype(bool).to_numpy()
    )
    assert (reviews["single_product_order"].astype(bool).to_numpy() == expected_flags).all()


@pytest.mark.db
def test_customer_order_revenue_matches_analytics(parquet_tables):
    parquet_revenue = parquet_tables["customer_orders"]["item_revenue"].sum()
    with get_engine().connect() as conn:
        analytics_revenue = conn.execute(
            text("SELECT SUM(item_revenue) FROM analytics.valid_orders")
        ).scalar_one()
    assert float(parquet_revenue) == pytest.approx(float(analytics_revenue), abs=0.01)
