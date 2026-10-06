import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_five_model_views_exist_and_have_comments():
    sql = (ROOT / "sql" / "05_modeling_tables.sql").read_text(encoding="utf-8")
    expected = {
        "model_orders_enriched",
        "model_customer_orders",
        "model_interactions",
        "model_products_enriched",
        "model_reviews_clean",
    }
    defined = set(re.findall(r"CREATE\s+OR\s+REPLACE\s+VIEW\s+analytics\.(\w+)", sql, re.I))
    assert defined == expected
    for name in expected:
        assert re.search(rf"COMMENT\s+ON\s+VIEW\s+analytics\.{name}\s+IS", sql, re.I)


def test_model_views_use_dynamic_window_and_person_key():
    sql = (ROOT / "sql" / "05_modeling_tables.sql").read_text(encoding="utf-8")
    assert re.search(r"'\d{4}-\d{2}-\d{2}'", sql) is None
    assert "customer_unique_id" in sql
    assert re.search(r"\bcustomer_id\b", sql) is not None  # source join key is permitted

    uncommented = re.sub(r"--[^\n]*", "", sql)
    select_lists = re.findall(r"\bSELECT\b(.*?)\bFROM\b", uncommented, flags=re.I | re.S)
    assert select_lists
    assert all(
        re.search(r"\bcustomer_id\b", select_list, re.I) is None for select_list in select_lists
    )


def test_reviews_keep_portuguese_text_and_document_attribution():
    sql = (ROOT / "sql" / "05_modeling_tables.sql").read_text(encoding="utf-8")
    assert "single_product_order" in sql
    assert "Portuguese source text is preserved" in sql
    assert "BTRIM(r.message)" in sql
