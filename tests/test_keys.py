"""Pytest suite asserting key uniqueness at each raw table's grain.

Skips gracefully if data/raw/ is empty or CSVs are not present.
"""

from pathlib import Path
import pandas as pd
import pytest
from src.config import DATA_RAW

RAW_FILES = list(DATA_RAW.glob("*.csv")) if DATA_RAW.exists() else []
RAW_AVAILABLE = len(RAW_FILES) >= 8

pytestmark = pytest.mark.skipif(
    not RAW_AVAILABLE,
    reason="Raw Olist CSV dataset is not present in data/raw/",
)


def test_customers_key_uniqueness():
    df = pd.read_csv(DATA_RAW / "olist_customers_dataset.csv")
    assert df["customer_id"].is_unique, "customer_id must be unique (1:1 with order)"
    assert len(df) == 99441


def test_orders_key_uniqueness():
    df = pd.read_csv(DATA_RAW / "olist_orders_dataset.csv")
    assert df["order_id"].is_unique, "order_id must be unique"
    assert len(df) == 99441


def test_order_items_key_uniqueness():
    df = pd.read_csv(DATA_RAW / "olist_order_items_dataset.csv")
    assert not df.duplicated(
        subset=["order_id", "order_item_id"]
    ).any(), "(order_id, order_item_id) composite key must be unique"
    assert len(df) == 112650


def test_order_payments_key_uniqueness():
    df = pd.read_csv(DATA_RAW / "olist_order_payments_dataset.csv")
    assert not df.duplicated(
        subset=["order_id", "payment_sequential"]
    ).any(), "(order_id, payment_sequential) composite key must be unique"
    assert len(df) == 103886


def test_order_reviews_key_uniqueness():
    df = pd.read_csv(DATA_RAW / "olist_order_reviews_dataset.csv")
    assert not df.duplicated(
        subset=["review_id", "order_id"]
    ).any(), "(review_id, order_id) composite key must be unique"
    assert len(df) == 99224


def test_products_key_uniqueness():
    df = pd.read_csv(DATA_RAW / "olist_products_dataset.csv")
    assert df["product_id"].is_unique, "product_id must be unique"
    assert len(df) == 32951


def test_sellers_key_uniqueness():
    df = pd.read_csv(DATA_RAW / "olist_sellers_dataset.csv")
    assert df["seller_id"].is_unique, "seller_id must be unique"
    assert len(df) == 3095


def test_category_translation_key_uniqueness():
    df = pd.read_csv(DATA_RAW / "product_category_name_translation.csv")
    assert df["product_category_name"].is_unique, "product_category_name must be unique"
    assert len(df) == 71
