import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from src.db import get_engine

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def create_schema():
    env = os.environ.copy()
    env["ALLOW_SCHEMA_RESET"] = "1"
    result = subprocess.run(
        [sys.executable, "-m", "src.db", "schema", "--yes"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Schemas created:" in result.stdout
    yield


@pytest.mark.db
def test_schema_and_core_primary_keys_exist(create_schema):
    expected_schemas = {"raw", "core", "analytics"}
    expected_tables = {
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
    with get_engine().connect() as conn:
        schemas = set(
            conn.execute(
                text(
                    "SELECT schema_name FROM information_schema.schemata "
                    "WHERE schema_name IN ('raw', 'core', 'analytics')"
                )
            ).scalars()
        )
        primary_keys = set(
            conn.execute(
                text(
                    "SELECT table_name FROM information_schema.table_constraints "
                    "WHERE table_schema = 'core' AND constraint_type = 'PRIMARY KEY'"
                )
            ).scalars()
        )
        core_tables = set(
            conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'core' AND table_type = 'BASE TABLE'"
                )
            ).scalars()
        )

    assert schemas == expected_schemas
    assert core_tables == expected_tables
    assert primary_keys == expected_tables


@pytest.mark.db
def test_expected_core_foreign_keys_exist(create_schema):
    query = text("""
        SELECT tc.table_name, kcu.column_name, ccu.table_name, ccu.column_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
          ON tc.constraint_catalog = kcu.constraint_catalog
         AND tc.constraint_schema = kcu.constraint_schema
         AND tc.constraint_name = kcu.constraint_name
         AND tc.table_name = kcu.table_name
        JOIN information_schema.constraint_column_usage AS ccu
          ON tc.constraint_catalog = ccu.constraint_catalog
         AND tc.constraint_schema = ccu.constraint_schema
         AND tc.constraint_name = ccu.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'core'
        """)
    with get_engine().connect() as conn:
        foreign_keys = set(conn.execute(query).tuples())

    assert {
        ("orders", "customer_id", "customers", "customer_id"),
        ("order_items", "order_id", "orders", "order_id"),
        ("order_items", "product_id", "products", "product_id"),
        ("order_items", "seller_id", "sellers", "seller_id"),
        ("payments", "order_id", "orders", "order_id"),
        ("reviews", "order_id", "orders", "order_id"),
    }.issubset(foreign_keys)


@pytest.mark.db
def test_review_score_check_rejects_six(create_schema):
    with pytest.raises(IntegrityError):
        with get_engine().begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO core.reviews (review_id, order_id, review_score) "
                    "VALUES ('schema-test-review', 'schema-test-order', 6)"
                )
            )


@pytest.mark.db
def test_schema_cli_refuses_reset_without_confirmation():
    env = os.environ.copy()
    env["ALLOW_SCHEMA_RESET"] = ""
    result = subprocess.run(
        [sys.executable, "-m", "src.db", "schema"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "WARNING:" in result.stdout
    assert "Refusing to reset database" in result.stderr
