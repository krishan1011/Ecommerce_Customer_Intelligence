import pandas as pd
import pytest

from src.cleaning import (
    build_clean_tables,
    dedupe_reviews,
    flag_inconsistencies,
    impute_product_dims,
    normalize_text_geo,
    winsorize_for_model,
)


def test_product_imputation_flags_missing_and_uses_category_then_global_medians():
    frame = pd.DataFrame(
        {
            "category_en": ["a", "a", "b", None],
            "weight_g": [10.0, None, 100.0, None],
            "length_cm": [2.0, None, 4.0, None],
            "height_cm": [3.0, 3.0, 5.0, None],
            "width_cm": [4.0, 4.0, 6.0, None],
        }
    )
    result = impute_product_dims(frame)
    assert result.loc[1, "weight_g_missing"]
    assert result.loc[1, "weight_g"] == 10.0
    assert result.loc[3, "weight_g"] == 55.0
    assert result.loc[1, "volume_cm3"] == 24.0


def test_normalization_removes_accents_and_preserves_review_portuguese():
    frame = pd.DataFrame(
        {
            "customer_city": ["  São Luís  "],
            "customer_state": [" sp "],
            "category_en": [" MÓVEIS "],
            "review_text": ["Ótimo, não gostei."],
        }
    )
    result = normalize_text_geo(frame)
    assert result.loc[0, "customer_city"] == "sao luis"
    assert result.loc[0, "customer_state"] == "SP"
    assert result.loc[0, "category_en"] == "moveis"
    assert result.loc[0, "review_text"] == "Ótimo, não gostei."


def test_flags_each_inconsistency_without_dropping_rows():
    frame = pd.DataFrame(
        {
            "price": [0, 10, 10, 10, 10, 10],
            "freight_value": [1, 11, 1, 1, 1, 1],
            "purchase_ts": pd.to_datetime(["2018-01-02"] * 6),
            "delivered_customer_ts": pd.to_datetime(
                ["2018-01-02", "2018-01-02", "2018-01-01", None, "2018-01-02", "2018-01-02"]
            ),
            "approved_ts": pd.to_datetime(
                ["2018-01-02", "2018-01-02", "2018-01-02", "2018-01-02", "2018-01-01", "2018-01-02"]
            ),
            "estimated_delivery_ts": pd.to_datetime(
                ["2018-01-03", "2018-01-03", "2018-01-03", "2018-01-03", "2018-01-03", "2018-01-01"]
            ),
            "order_status": ["delivered"] * 6,
        }
    )
    flagged, summary = flag_inconsistencies(frame)
    assert len(flagged) == len(frame)
    assert set(summary["issue"]) == {
        "price_nonpositive",
        "freight_exceeds_price",
        "delivered_before_purchase",
        "approved_before_purchase",
        "estimated_before_purchase",
        "missing_delivery_ts_on_delivered",
    }
    assert summary["count"].sum() == 7


def test_winsorization_returns_capped_copy_and_keeps_source_unchanged():
    original = pd.Series([1.0, 2.0, 3.0, 100.0])
    capped = winsorize_for_model(original, 0.0, 0.75)
    assert original.iloc[-1] == 100.0
    assert capped.iloc[-1] == 27.25
    assert not capped.equals(original)


def test_review_dedupe_keeps_latest_review_per_order():
    frame = pd.DataFrame(
        {
            "order_id": ["o1", "o1", "o2"],
            "creation_ts": pd.to_datetime(["2018-01-01", "2018-01-03", "2018-01-02"]),
            "review_score": [1, 5, 3],
        }
    )
    result = dedupe_reviews(frame)
    assert result.set_index("order_id")["review_score"].to_dict() == {"o1": 5, "o2": 3}


def test_build_is_idempotent(tmp_path):
    in_dir = tmp_path / "data" / "processed"
    in_dir.mkdir(parents=True)
    orders = pd.DataFrame(
        {
            "order_id": pd.Series(["o1"], dtype="string"),
            "order_item_id": pd.Series([1], dtype="int32"),
            "customer_unique_id": pd.Series(["c1"], dtype="string"),
            "price": [10.0],
            "freight_value": [2.0],
            "purchase_ts": pd.to_datetime(["2018-01-01"]),
            "order_status": pd.Series(["delivered"], dtype="category"),
            "is_delivered": pd.Series([True], dtype="boolean"),
            "delivered_customer_ts": pd.to_datetime(["2018-01-02"]),
            "approved_ts": pd.to_datetime(["2018-01-01"]),
            "estimated_delivery_ts": pd.to_datetime(["2018-01-03"]),
        }
    )
    customers = pd.DataFrame(
        {
            "customer_unique_id": pd.Series(["c1"], dtype="string"),
            "order_id": pd.Series(["o1"], dtype="string"),
            "purchase_ts": pd.to_datetime(["2018-01-01"]),
            "item_revenue": [10.0],
        }
    )
    interactions = pd.DataFrame(
        {
            "customer_unique_id": pd.Series(["c1"], dtype="string"),
            "product_id": pd.Series(["p1"], dtype="string"),
            "order_id": pd.Series(["o1"], dtype="string"),
            "purchase_ts": pd.to_datetime(["2018-01-01"]),
            "price": [10.0],
        }
    )
    products = pd.DataFrame(
        {
            "product_id": pd.Series(["p1"], dtype="string"),
            "category_en": pd.Series(["books"], dtype="category"),
            "weight_g": pd.Series([1.0], dtype="float32"),
            "volume_cm3": pd.Series([8.0], dtype="float32"),
            "name_length": pd.Series([2], dtype="Int32"),
            "description_length": pd.Series([4], dtype="Int32"),
            "photos_qty": pd.Series([1], dtype="Int32"),
        }
    )
    reviews = pd.DataFrame(
        {
            "review_id": pd.Series(["r1"], dtype="string"),
            "order_id": pd.Series(["o1"], dtype="string"),
            "customer_unique_id": pd.Series(["c1"], dtype="string"),
            "review_score": pd.Series([5], dtype="Int8"),
            "creation_ts": pd.to_datetime(["2018-01-03"]),
            "order_purchase_ts": pd.to_datetime(["2018-01-01"]),
        }
    )
    sources = {
        "orders_enriched": orders,
        "customer_orders": customers,
        "interactions": interactions,
        "products_enriched": products,
        "reviews_clean": reviews,
    }
    for filename, frame in sources.items():
        frame.to_parquet(in_dir / f"{filename}.parquet")
    out_dir = tmp_path / "clean"
    build_clean_tables(in_dir, out_dir)
    first = {path.name: pd.read_parquet(path) for path in sorted(out_dir.glob("*.parquet"))}
    build_clean_tables(in_dir, out_dir)
    for path in out_dir.glob("*.parquet"):
        pd.testing.assert_frame_equal(first[path.name], pd.read_parquet(path))


@pytest.mark.parametrize("lower,upper", [(-0.1, 0.5), (0.5, 0.5), (0.8, 1.1)])
def test_invalid_winsor_quantiles_raise(lower, upper):
    with pytest.raises(ValueError):
        winsorize_for_model(pd.Series([1, 2]), lower, upper)
