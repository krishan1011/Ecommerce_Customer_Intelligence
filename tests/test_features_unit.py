import numpy as np
import pandas as pd

from src.features import build_snapshot, haversine_km


def _fixture_frames():
    records = [
        ("a1", "a", "2020-01-01", "2020-01-02", "2020-01-03", "sp", "credit_card", 2),
        ("a2", "a", "2020-01-05", "2020-01-06", "2020-01-04", "sp", "credit_card", 3),
        ("a3", "a", "2020-01-10", "2020-01-11", "2020-01-12", "sp", "credit_card", 1),
        ("b1", "b", "2020-01-01", "2020-01-02", "2020-01-03", "rj", "boleto", 1),
        ("b2", "b", "2020-01-20", "2020-01-21", "2020-01-22", "rj", "boleto", 1),
        ("c1", "c", "2020-01-01", "2020-01-02", "2020-01-03", "mg", "credit_card", 1),
        ("c2", "c", "2020-01-21", "2020-01-22", "2020-01-23", "mg", "credit_card", 1),
        ("d1", "d", "2020-01-05", "2020-01-06", "2020-01-07", "pr", "boleto", 1),
    ]
    orders = pd.DataFrame(
        [
            {
                "order_id": order_id,
                "customer_unique_id": customer,
                "purchase_ts": purchase,
                "delivered_customer_ts": delivered,
                "estimated_delivery_ts": estimate,
                "is_delivered": True,
                "freight_value": 5.0,
                "customer_state": state,
                "payment_type_main": payment,
                "max_installments": installments,
            }
            for (
                order_id,
                customer,
                purchase,
                delivered,
                estimate,
                state,
                payment,
                installments,
            ) in records
        ]
    )
    item_prices = {
        "a1": 20.0,
        "a2": 80.0,
        "a3": 90.0,
        "b1": 30.0,
        "b2": 50.0,
        "c1": 40.0,
        "c2": 60.0,
        "d1": 10.0,
    }
    items = pd.DataFrame(
        [
            {
                "order_id": order_id,
                "product_id": f"p_{order_id}",
                "category_en": "cat_a" if order_id in {"a1", "b1", "c1"} else "cat_b",
                "price": price,
                "quantity": 1,
            }
            for order_id, price in item_prices.items()
        ]
    )
    reviews = pd.DataFrame(
        columns=["customer_unique_id", "creation_ts", "review_score", "review_text"]
    )
    geo = pd.DataFrame(
        [
            {
                "order_id": order_id,
                "customer_city": f"city_{customer}",
                "customer_lat": 0.0,
                "customer_lng": 0.0,
                "seller_lat": 0.0,
                "seller_lng": 1.0,
                "same_state": True,
            }
            for order_id, customer, *_ in records
        ]
    )
    return orders, items, reviews, geo


def test_snapshot_hand_calculated_rfm_behavior_category_and_boundary_label():
    orders, items, reviews, geo = _fixture_frames()
    features = build_snapshot(orders, items, reviews, geo, "2020-01-10", 10)
    by_customer = features.set_index("customer_unique_id")

    assert by_customer.loc["a", "recency_days"] == 5
    assert by_customer.loc["a", "frequency"] == 2
    assert by_customer.loc["a", "monetary_total"] == 100
    assert by_customer.loc["a", "monetary_avg"] == 50
    assert by_customer.loc["a", "tenure_days"] == 9
    assert by_customer.loc["a", "avg_days_between_orders"] == 4
    assert by_customer.loc["a", "top_category"] == "cat_b"
    assert by_customer.loc["a", "label_repeat"] == 1  # order at T belongs to the label window
    assert by_customer.loc["b", "label_repeat"] == 0  # order at T + H is excluded
    assert by_customer.loc["c", "label_repeat"] == 0  # order after T + H is excluded
    assert by_customer.loc["d", "frequency"] == 1
    assert np.isnan(by_customer.loc["d", "avg_days_between_orders"])


def test_haversine_one_degree_at_equator():
    assert np.isclose(haversine_km(0, 0, 0, 1), 111.195, atol=0.01)
