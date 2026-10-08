import pandas as pd
import pytest

from src.features import assert_no_leakage, build_snapshot
from tests.test_features_unit import _fixture_frames


def _build(frames):
    return (
        build_snapshot(*frames, T="2020-01-10", H=10)
        .sort_values("customer_unique_id")
        .reset_index(drop=True)
    )


def test_future_event_perturbations_do_not_change_pre_snapshot_features():
    base = list(_fixture_frames())
    base[0] = base[0].loc[~base[0]["order_id"].isin(["a3", "b2", "c2"])].copy()
    base[1] = base[1].loc[~base[1]["order_id"].isin(["a3", "b2", "c2"])].copy()
    base[0].loc[base[0]["order_id"].eq("a2"), "delivered_customer_ts"] = "2020-01-12"
    base_result = _build(base)

    changed = list(_fixture_frames())
    changed[0] = pd.concat(
        [
            changed[0],
            pd.DataFrame(
                [
                    {
                        "order_id": "future",
                        "customer_unique_id": "a",
                        "purchase_ts": "2020-01-30",
                        "delivered_customer_ts": "2020-02-20",
                        "estimated_delivery_ts": "2020-02-01",
                        "is_delivered": True,
                        "freight_value": 1000.0,
                        "customer_state": "am",
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    changed[1] = pd.concat(
        [
            changed[1],
            pd.DataFrame(
                [
                    {
                        "order_id": "future",
                        "product_id": "new",
                        "category_en": "future",
                        "price": 9999.0,
                        "quantity": 3,
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    changed[1].loc[changed[1]["order_id"].eq("a3"), "price"] = 12345.0
    changed[2] = pd.concat(
        [
            changed[2],
            pd.DataFrame(
                [
                    {
                        "order_id": "a2",
                        "customer_unique_id": "a",
                        "creation_ts": "2020-01-11",
                        "review_score": 1,
                        "review_text": "future review",
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    changed[0].loc[changed[0]["order_id"].eq("a2"), "delivered_customer_ts"] = "2020-01-18"
    changed[0].loc[changed[0]["order_id"].eq("future"), "freight_value"] = 1.0
    changed_result = _build(changed)
    feature_columns = [column for column in base_result if column not in {"label_repeat"}]
    pd.testing.assert_frame_equal(base_result[feature_columns], changed_result[feature_columns])


def test_delivery_after_snapshot_is_not_observable():
    frames = list(_fixture_frames())
    frames[0] = frames[0].loc[frames[0]["customer_unique_id"].eq("a")].copy()
    frames[0].loc[frames[0]["order_id"].eq("a2"), "delivered_customer_ts"] = "2020-01-12"
    frames[0].loc[frames[0]["order_id"].eq("a2"), "estimated_delivery_ts"] = "2020-01-11"
    frames[1] = frames[1].loc[frames[1]["order_id"].isin(["a1", "a2"])].copy()
    frame = _build(frames).set_index("customer_unique_id")
    assert pd.isna(frame.loc["a", "last_order_late"])
    assert frame.loc["a", "avg_delivery_days"] == 1
    assert frame.loc["a", "late_delivery_share"] == 0


def test_review_created_after_snapshot_is_ignored():
    frames = list(_fixture_frames())
    baseline = _build(frames).set_index("customer_unique_id")
    frames[2] = pd.DataFrame(
        [
            {
                "order_id": "a2",
                "customer_unique_id": "a",
                "creation_ts": "2020-01-11",
                "review_score": 1,
                "review_text": "late",
            }
        ]
    )
    changed = _build(frames).set_index("customer_unique_id")
    assert changed.loc["a", "n_reviews_known"] == baseline.loc["a", "n_reviews_known"]
    assert pd.isna(changed.loc["a", "avg_review_score"])
    assert pd.isna(baseline.loc["a", "avg_review_score"])


def test_label_only_changes_for_orders_in_half_open_horizon():
    frames = list(_fixture_frames())
    frames[0] = frames[0].loc[frames[0]["customer_unique_id"].eq("d")].copy()
    frames[1] = frames[1].loc[frames[1]["order_id"].eq("d1")].copy()
    assert _build(frames).iloc[0]["label_repeat"] == 0
    order = frames[0].iloc[0].copy()
    order["order_id"] = "d_at_T"
    order["purchase_ts"] = "2020-01-10"
    frames[0] = pd.concat([frames[0], order.to_frame().T], ignore_index=True)
    item = frames[1].iloc[0].copy()
    item["order_id"] = "d_at_T"
    frames[1] = pd.concat([frames[1], item.to_frame().T], ignore_index=True)
    assert _build(frames).iloc[0]["label_repeat"] == 1


def test_assert_no_leakage_rejects_feature_event_at_snapshot():
    events = pd.DataFrame({"purchase_ts": ["2020-01-10"]})
    with pytest.raises(ValueError, match="Leakage detected"):
        assert_no_leakage(events, "2020-01-10")
