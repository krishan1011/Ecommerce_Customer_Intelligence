import pandas as pd
import pytest
from sqlalchemy import text

from src.config import ANALYSIS_END, ANALYSIS_START, DATA_RAW, VALID_STATUSES
from src.db import get_engine

pytestmark = pytest.mark.db


def _read_csv(name: str) -> pd.DataFrame:
    return pd.read_csv(DATA_RAW / name)


@pytest.fixture(scope="module", autouse=True)
def require_raw_data():
    if not DATA_RAW.exists() or not any(DATA_RAW.glob("*.csv")):
        pytest.skip("Olist data/raw CSV files are required for SQL/pandas reconciliation")


def test_analytics_views_match_pandas_and_preserve_grain():
    orders = _read_csv("olist_orders_dataset.csv")
    items = _read_csv("olist_order_items_dataset.csv")
    customers = _read_csv("olist_customers_dataset.csv")
    products = _read_csv("olist_products_dataset.csv")
    translations = _read_csv("product_category_name_translation.csv")

    orders["order_purchase_timestamp"] = pd.to_datetime(
        orders["order_purchase_timestamp"], errors="coerce"
    )
    start = pd.Timestamp(ANALYSIS_START)
    end = pd.Timestamp(ANALYSIS_END) + pd.Timedelta(days=1)
    valid = orders.loc[
        orders["order_status"].isin(VALID_STATUSES)
        & orders["order_purchase_timestamp"].ge(start)
        & orders["order_purchase_timestamp"].lt(end)
    ].copy()
    valid = valid.merge(
        customers[["customer_id", "customer_unique_id", "customer_state"]],
        on="customer_id",
        how="inner",
    )
    valid_items = items.merge(valid[["order_id"]], on="order_id", how="inner")
    expected_revenue = valid_items["price"].sum()
    customer_order_counts = valid.groupby("customer_unique_id")["order_id"].nunique()
    expected_repeat_rate = customer_order_counts.ge(2).sum() / len(customer_order_counts)
    expected_delivered_customers = valid["customer_unique_id"].nunique()

    delivery = valid[
        ["order_id", "order_delivered_customer_date", "order_estimated_delivery_date"]
    ].copy()
    delivery["actual"] = pd.to_datetime(delivery["order_delivered_customer_date"], errors="coerce")
    delivery["estimated"] = pd.to_datetime(
        delivery["order_estimated_delivery_date"], errors="coerce"
    )
    dated_delivery = delivery.dropna(subset=["actual", "estimated"])
    expected_late_rate = (
        dated_delivery["actual"].gt(dated_delivery["estimated"]).mean()
        if len(dated_delivery)
        else float("nan")
    )

    category_lookup = products[["product_id", "product_category_name"]].merge(
        translations, on="product_category_name", how="left"
    )
    category_lookup["category"] = (
        category_lookup["product_category_name_english"]
        .fillna(category_lookup["product_category_name"])
        .fillna("(uncategorized)")
    )
    category_lines = valid_items.merge(category_lookup[["product_id", "category"]], on="product_id")
    pandas_top_category = (
        category_lines.groupby("category", dropna=False)["price"]
        .sum()
        .sort_values(ascending=False, kind="stable")
        .index[0]
    )
    month_revenue = (
        valid_items.merge(valid[["order_id", "order_purchase_timestamp"]], on="order_id")
        .assign(month=lambda frame: frame["order_purchase_timestamp"].dt.to_period("M").astype(str))
        .groupby("month")["price"]
        .sum()
    )
    check_months = list(month_revenue.sort_index().index[:3])

    engine = get_engine()
    with engine.connect() as conn:
        sql_revenue = conn.execute(
            text("SELECT SUM(item_revenue) FROM analytics.valid_orders")
        ).scalar_one()
        sql_repeat_rate = conn.execute(text("""
                SELECT COUNT(*) FILTER (WHERE order_count >= 2)::NUMERIC / NULLIF(COUNT(*), 0)
                FROM analytics.customer_summary
                """)).scalar_one()
        sql_delivered_customers = conn.execute(
            text("SELECT COUNT(DISTINCT customer_unique_id) FROM analytics.valid_orders")
        ).scalar_one()
        sql_late_rate = conn.execute(text("""
                SELECT AVG(late_flag::INT)::NUMERIC
                FROM analytics.delivery_performance
                WHERE late_flag IS NOT NULL
                """)).scalar_one()
        sql_top_category = conn.execute(text("""
                SELECT category FROM analytics.category_performance
                ORDER BY revenue DESC, category LIMIT 1
                """)).scalar_one()
        sql_months = dict(
            conn.execute(
                text("""
                    SELECT TO_CHAR(month, 'YYYY-MM'), revenue
                    FROM analytics.monthly_kpis
                    WHERE TO_CHAR(month, 'YYYY-MM') = ANY(:months)
                    """),
                {"months": check_months},
            ).all()
        )

        duplicate_counts = conn.execute(text("""
                SELECT
                    (SELECT COUNT(*) - COUNT(DISTINCT order_id) FROM analytics.valid_orders),
                    (SELECT COUNT(*) - COUNT(DISTINCT customer_unique_id)
                     FROM analytics.customer_summary),
                    (SELECT COUNT(*) - COUNT(DISTINCT month) FROM analytics.monthly_kpis),
                    (SELECT SUM(item_revenue) FROM analytics.customer_orders),
                    (SELECT SUM(item_revenue) FROM analytics.valid_orders)
                """)).one()

    assert round(float(sql_revenue), 2) == round(float(expected_revenue), 2)
    assert float(sql_repeat_rate) == pytest.approx(expected_repeat_rate, abs=1e-10)
    assert sql_delivered_customers == expected_delivered_customers
    assert float(sql_late_rate) == pytest.approx(expected_late_rate, abs=1e-10)
    assert sql_top_category == pandas_top_category
    for month in check_months:
        assert round(float(sql_months[month]), 2) == round(float(month_revenue[month]), 2)

    valid_duplicates, customer_duplicates, month_duplicates, customer_revenue, valid_revenue = (
        duplicate_counts
    )
    assert (valid_duplicates, customer_duplicates, month_duplicates) == (0, 0, 0)
    assert float(customer_revenue) == pytest.approx(float(valid_revenue), abs=0.01)
