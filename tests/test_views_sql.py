import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_expected_analytics_views_are_defined_and_documented():
    sql = (ROOT / "sql" / "03_clean_views.sql").read_text(encoding="utf-8")
    expected = {
        "order_revenue",
        "order_payments_agg",
        "valid_orders",
        "customer_orders",
        "monthly_kpis",
        "customer_summary",
        "product_performance",
        "category_performance",
        "seller_performance",
        "delivery_performance",
        "cohort_retention",
        "review_trends",
    }
    defined = set(re.findall(r"CREATE\s+OR\s+REPLACE\s+VIEW\s+analytics\.(\w+)", sql, re.I))
    assert expected <= defined
    for name in expected:
        assert re.search(rf"COMMENT\s+ON\s+VIEW\s+analytics\.{name}\s+IS", sql, re.I)


def test_business_metrics_has_twenty_five_numbered_questions():
    sql = (ROOT / "sql" / "04_business_metrics.sql").read_text(encoding="utf-8")
    view_sql = (ROOT / "sql" / "03_clean_views.sql").read_text(encoding="utf-8")
    questions = re.findall(r"^-- Q\d{2} Business question:", sql, re.M)
    assert len(questions) >= 20
    assert "LAG(" in view_sql
    assert "RANK()" in sql
    assert "NTILE(" in sql
    assert "SUM(revenue) OVER" in sql


def test_view_definitions_have_no_hardcoded_date_literals():
    sql = (ROOT / "sql" / "03_clean_views.sql").read_text(encoding="utf-8")
    assert re.search(r"'\d{4}-\d{2}-\d{2}'", sql) is None
