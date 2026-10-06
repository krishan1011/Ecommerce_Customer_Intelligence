import pandas as pd
import pandera.pandas as pa
import pytest

from src.validation import get_schemas, validate_frame


def _strings(values):
    return pd.Series(values, dtype="string")


def _categories(values):
    return pd.Series(pd.Categorical(values))


def _valid_frames():
    timestamp = pd.Timestamp("2017-02-01 12:00:00")
    order = pd.DataFrame(
        {
            "order_id": _strings(["o1"]),
            "order_item_id": pd.Series([1], dtype="int32"),
            "customer_unique_id": _strings(["c1"]),
            "customer_state": _categories(["SP"]),
            "product_id": _strings(["p1"]),
            "seller_id": _strings(["s1"]),
            "seller_state": _categories(["SP"]),
            "category_en": _categories(["books"]),
            "price": [12.5],
            "freight_value": [2.5],
            "order_status": _categories(["delivered"]),
            "purchase_ts": [timestamp],
            "approved_ts": [timestamp],
            "delivered_carrier_ts": [timestamp],
            "delivered_customer_ts": [timestamp],
            "estimated_delivery_ts": [timestamp],
            "shipping_limit_ts": [timestamp],
            "is_delivered": pd.Series([True], dtype="boolean"),
            "is_late": pd.Series([False], dtype="boolean"),
            "delivery_days": [1.0],
            "estimated_days": [2.0],
            "item_count_in_order": pd.Series([1], dtype="int32"),
            "payment_type_main": _categories(["credit_card"]),
            "max_installments": pd.Series([1], dtype="Int32"),
        }
    )
    customer_order = pd.DataFrame(
        {
            "customer_unique_id": _strings(["c1"]),
            "order_id": _strings(["o1"]),
            "purchase_ts": [timestamp],
            "order_value": [15.0],
            "item_revenue": [12.5],
            "freight": [2.5],
            "n_items": pd.Series([1], dtype="int32"),
            "n_categories": pd.Series([1], dtype="int32"),
            "state": _categories(["SP"]),
            "is_late": pd.Series([False], dtype="boolean"),
            "review_score": pd.Series([5], dtype="Int8"),
            "review_ts": [timestamp],
        }
    )
    interaction = pd.DataFrame(
        {
            "customer_unique_id": _strings(["c1"]),
            "product_id": _strings(["p1"]),
            "category_en": _categories(["books"]),
            "order_id": _strings(["o1"]),
            "purchase_ts": [timestamp],
            "price": [12.5],
            "quantity": pd.Series([1], dtype="int32"),
        }
    )
    product = pd.DataFrame(
        {
            "product_id": _strings(["p1"]),
            "category_en": _categories(["books"]),
            "price_mean": [12.5],
            "price_min": [12.5],
            "price_max": [12.5],
            "name_length": pd.Series([10], dtype="Int32"),
            "description_length": pd.Series([100], dtype="Int32"),
            "photos_qty": pd.Series([1], dtype="Int32"),
            "weight_g": pd.Series([500.0], dtype="float32"),
            "volume_cm3": pd.Series([1000.0], dtype="float32"),
            "n_orders": pd.Series([1], dtype="int32"),
            "units_sold": pd.Series([1], dtype="int32"),
            "first_sale_ts": [timestamp],
            "last_sale_ts": [timestamp],
            "review_count": pd.Series([1], dtype="int32"),
            "review_avg": [5.0],
            "share_low_score": [0.0],
        }
    )
    review = pd.DataFrame(
        {
            "review_id": _strings(["r1"]),
            "order_id": _strings(["o1"]),
            "customer_unique_id": _strings(["c1"]),
            "review_score": pd.Series([5], dtype="int8"),
            "title": _strings(["Ótimo"]),
            "message": _strings(["Muito bom"]),
            "review_text": _strings(["Ótimo Muito bom"]),
            "has_text": pd.Series([True], dtype="boolean"),
            "creation_ts": [timestamp],
            "answer_ts": [timestamp],
            "order_purchase_ts": [timestamp],
            "delivered_customer_ts": [timestamp],
            "is_late": pd.Series([False], dtype="boolean"),
            "n_products": pd.Series([1], dtype="int32"),
            "n_sellers": pd.Series([1], dtype="int32"),
            "primary_product_id": _strings(["p1"]),
            "category_en": _categories(["books"]),
            "single_product_order": pd.Series([True], dtype="boolean"),
        }
    )
    return {
        "orders_enriched": order,
        "customer_orders": customer_order,
        "interactions": interaction,
        "products_enriched": product,
        "reviews_clean": review,
    }


def test_schemas_accept_valid_modeling_frames():
    schemas = get_schemas()
    for name, frame in _valid_frames().items():
        assert schemas[name].validate(frame).equals(frame)


def test_schemas_reject_duplicate_grain_null_customer_bad_rating_and_negative_price():
    frames = _valid_frames()

    duplicate = pd.concat([frames["orders_enriched"]] * 2, ignore_index=True)
    with pytest.raises(pa.errors.SchemaError):
        validate_frame("orders_enriched", duplicate)

    null_customer = frames["interactions"].copy()
    null_customer.loc[0, "customer_unique_id"] = pd.NA
    with pytest.raises(pa.errors.SchemaError):
        validate_frame("interactions", null_customer)

    bad_score = frames["reviews_clean"].copy()
    bad_score.loc[0, "review_score"] = 6
    with pytest.raises(pa.errors.SchemaError):
        validate_frame("reviews_clean", bad_score)

    negative_price = frames["orders_enriched"].copy()
    negative_price.loc[0, "price"] = -0.01
    with pytest.raises(pa.errors.SchemaError):
        validate_frame("orders_enriched", negative_price)
