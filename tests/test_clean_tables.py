import pandas as pd
import pytest

from src.config import ANALYSIS_END, ANALYSIS_START, DATA_PROCESSED
from src.validation import CLEAN_TABLE_FILES, validate_clean_tables


@pytest.fixture(scope="module")
def clean_tables():
    directory = DATA_PROCESSED / "clean"
    if not all((directory / filename).is_file() for filename in CLEAN_TABLE_FILES.values()):
        pytest.skip("Phase 6 clean parquet files are not present under data/processed/clean")
    validate_clean_tables(directory)
    return {
        name: pd.read_parquet(directory / filename) for name, filename in CLEAN_TABLE_FILES.items()
    }


def test_clean_table_grains_prices_customers_flags_and_window(clean_tables):
    orders = clean_tables["orders_clean"]
    customers = clean_tables["customers_clean"]
    interactions = clean_tables["interactions_clean"]
    products = clean_tables["products_clean"]
    reviews = clean_tables["reviews_clean"]

    assert not orders.duplicated(["order_id", "order_item_id"]).any()
    assert not customers.duplicated(["customer_unique_id", "order_id"]).any()
    assert not interactions.duplicated(["customer_unique_id", "product_id", "order_id"]).any()
    assert not products["product_id"].duplicated().any()
    assert not reviews["order_id"].duplicated().any()
    for frame in (orders, customers, interactions, reviews):
        assert frame["customer_unique_id"].notna().all()
    assert orders["price"].ge(0).all()
    flag_columns = [
        "price_nonpositive",
        "freight_exceeds_price",
        "delivered_before_purchase",
        "approved_before_purchase",
        "estimated_before_purchase",
        "missing_delivery_ts_on_delivered",
    ]
    assert all(column in orders for column in flag_columns)
    assert orders[flag_columns].dtypes.map(pd.api.types.is_bool_dtype).all()
    assert int(orders["missing_delivery_ts_on_delivered"].sum()) > 0

    start = pd.Timestamp(ANALYSIS_START)
    end = pd.Timestamp(ANALYSIS_END) + pd.Timedelta(days=1)
    assert orders["purchase_ts"].ge(start).all() and orders["purchase_ts"].lt(end).all()
    assert customers["purchase_ts"].ge(start).all() and customers["purchase_ts"].lt(end).all()
    assert interactions["purchase_ts"].ge(start).all() and interactions["purchase_ts"].lt(end).all()
    assert reviews["order_purchase_ts"].ge(start).all()
    assert reviews["order_purchase_ts"].lt(end).all()
