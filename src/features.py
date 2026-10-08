"""Leakage-safe customer snapshots and product features for Phase 8."""

import argparse
import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from .config import DATA_PROCESSED, PARAMS, ROOT

FEATURE_DICTIONARY = {
    "recency_days": (
        "RFM",
        "Days from the last prior delivered purchase to T",
        "customer_orders",
        "float",
        "purchase_ts < T",
        "Not applicable",
    ),
    "frequency": (
        "RFM",
        "Distinct delivered orders purchased before T",
        "customer_orders",
        "int",
        "purchase_ts < T",
        "Not applicable",
    ),
    "monetary_total": (
        "RFM",
        "Sum of item prices for prior delivered orders; freight excluded",
        "order_items",
        "float",
        "purchase_ts < T",
        "Not applicable",
    ),
    "monetary_avg": (
        "RFM",
        "Mean item-price revenue per prior delivered order",
        "order_items",
        "float",
        "purchase_ts < T",
        "Not applicable",
    ),
    "avg_order_value": (
        "Behavior",
        "Mean item-price revenue per prior delivered order; freight excluded",
        "order_items",
        "float",
        "purchase_ts < T",
        "Not applicable",
    ),
    "avg_items_per_order": (
        "Behavior",
        "Mean item-line quantity per prior delivered order",
        "order_items",
        "float",
        "purchase_ts < T",
        "Not applicable",
    ),
    "avg_price": (
        "Behavior",
        "Mean item price per unit in prior delivered orders",
        "order_items",
        "float",
        "purchase_ts < T",
        "Not applicable",
    ),
    "avg_freight": (
        "Behavior",
        "Mean freight per prior delivered order",
        "order_items",
        "float",
        "purchase_ts < T",
        "Not applicable",
    ),
    "freight_share": (
        "Behavior",
        "Prior freight divided by item revenue plus freight",
        "order_items",
        "float",
        "purchase_ts < T",
        "NaN if total spend is zero",
    ),
    "tenure_days": (
        "Behavior",
        "Days between first prior delivered purchase and T",
        "customer_orders",
        "float",
        "purchase_ts < T",
        "Not applicable",
    ),
    "avg_days_between_orders": (
        "Behavior",
        "Mean gap between successive prior delivered orders",
        "customer_orders",
        "float",
        "purchase_ts < T",
        "NaN for one order",
    ),
    "has_multiple_orders": (
        "Behavior",
        "Whether at least two delivered orders were purchased before T",
        "customer_orders",
        "bool",
        "purchase_ts < T",
        "Not applicable",
    ),
    "n_distinct_categories": (
        "Category",
        "Distinct non-null categories purchased before T",
        "order_items",
        "int",
        "purchase_ts < T",
        "Zero when category is unknown",
    ),
    "top_category": (
        "Category",
        "Category with greatest prior item-price spend",
        "order_items",
        "string",
        "purchase_ts < T",
        "NaN when categories are unknown",
    ),
    "top3_spend_share": (
        "Category",
        "Spend share from the three highest-spend categories",
        "order_items",
        "float",
        "purchase_ts < T",
        "NaN when category or spend is unavailable",
    ),
    "preferred_payment_type": (
        "Payment",
        "Most frequent payment type on prior delivered orders",
        "payments",
        "string",
        "purchase_ts < T",
        "NaN when unavailable",
    ),
    "avg_installments": (
        "Payment",
        "Mean maximum installment count on prior delivered orders",
        "payments",
        "float",
        "purchase_ts < T",
        "NaN when unavailable",
    ),
    "share_credit_card": (
        "Payment",
        "Share of prior orders whose main payment is credit card",
        "payments",
        "float",
        "purchase_ts < T",
        "NaN when payment is unavailable",
    ),
    "n_reviews_known": (
        "Experience",
        "Reviews created before T",
        "reviews",
        "int",
        "creation_ts < T",
        "Zero when no review is known",
    ),
    "avg_review_score": (
        "Experience",
        "Mean score of reviews created before T",
        "reviews",
        "float",
        "creation_ts < T",
        "NaN when no review is known",
    ),
    "last_review_score": (
        "Experience",
        "Latest score among reviews created before T",
        "reviews",
        "float",
        "creation_ts < T",
        "NaN when no review is known",
    ),
    "min_review_score": (
        "Experience",
        "Minimum score among reviews created before T",
        "reviews",
        "float",
        "creation_ts < T",
        "NaN when no review is known",
    ),
    "has_review": (
        "Experience",
        "Whether a review was created before T",
        "reviews",
        "bool",
        "creation_ts < T",
        "Not applicable",
    ),
    "avg_review_text_length": (
        "Experience",
        "Mean character count of known review text created before T",
        "reviews",
        "float",
        "creation_ts < T",
        "NaN when text is absent",
    ),
    "late_delivery_share": (
        "Experience",
        "Late share among orders delivered and observable before T",
        "orders",
        "float",
        "delivered_customer_ts < T",
        "NaN when no delivery outcome is known",
    ),
    "last_order_late": (
        "Experience",
        "Late flag for latest purchase only if delivered before T",
        "orders",
        "float",
        "delivered_customer_ts < T",
        "NaN if delivery is not yet observable",
    ),
    "avg_delivery_days": (
        "Experience",
        "Mean purchase-to-delivery days for deliveries completed before T",
        "orders",
        "float",
        "delivered_customer_ts < T",
        "NaN when no delivery is observable",
    ),
    "avg_delay_vs_estimate": (
        "Experience",
        "Mean actual minus estimated delivery days for deliveries completed before T",
        "orders",
        "float",
        "delivered_customer_ts < T",
        "NaN when estimate or delivery is absent",
    ),
    "state": (
        "Geography",
        "State of the customer's latest prior order",
        "customers",
        "string",
        "purchase_ts < T",
        "NaN when unavailable",
    ),
    "region": (
        "Geography",
        "Brazil macro-region for the latest prior order state",
        "customers",
        "string",
        "purchase_ts < T",
        "NaN for unknown state",
    ),
    "city_orders_proxy": (
        "Geography",
        "Prior delivered order count in the latest order's city",
        "customers",
        "int",
        "purchase_ts < T",
        "NaN when city is unknown",
    ),
    "last_order_distance_km": (
        "Geography",
        "Haversine distance for latest prior order customer and first seller",
        "order_geo",
        "float",
        "purchase_ts < T",
        "NaN when coordinates are missing",
    ),
    "last_order_same_state": (
        "Geography",
        "Whether latest prior order customer and first seller states match",
        "order_geo",
        "bool",
        "purchase_ts < T",
        "NaN when either state is unknown",
    ),
    "last_purchase_month": (
        "Time",
        "Calendar month of latest prior purchase",
        "customer_orders",
        "int",
        "purchase_ts < T",
        "Not applicable",
    ),
    "last_purchase_quarter": (
        "Time",
        "Calendar quarter of latest prior purchase",
        "customer_orders",
        "int",
        "purchase_ts < T",
        "Not applicable",
    ),
    "last_purchase_dow": (
        "Time",
        "Day of week of latest prior purchase, Monday=0",
        "customer_orders",
        "int",
        "purchase_ts < T",
        "Not applicable",
    ),
    "last_purchase_hour": (
        "Time",
        "Hour of latest prior purchase",
        "customer_orders",
        "int",
        "purchase_ts < T",
        "Not applicable",
    ),
    "last_purchase_in_black_friday_window": (
        "Time",
        "Whether latest prior purchase was Nov 20-30",
        "customer_orders",
        "bool",
        "purchase_ts < T",
        "Not applicable",
    ),
}

FEATURE_METADATA = {
    "customer_unique_id": (
        "Grain",
        "Stable customer identity; one row per customer and snapshot",
        "customers",
        "string",
        "Never use customer_id; unique ID is the entity key",
        "Required, never imputed",
    ),
    "snapshot": (
        "Grain",
        "Observation cutoff T for this customer row",
        "params.yaml",
        "datetime",
        "Configured split snapshot; history requires timestamps < T",
        "Required",
    ),
    "label_repeat": (
        "Label",
        "1 if a delivered repeat purchase occurs in [T, T+H)",
        "orders",
        "int",
        "Purchase timestamps checked against the half-open label horizon",
        "Required binary label",
    ),
    "split": (
        "Split",
        "Configured chronological train, val, or test membership",
        "params.yaml",
        "string",
        "Purged snapshot order and horizon assertions",
        "Required",
    ),
}

REGIONS = {
    **dict.fromkeys(["ac", "ap", "am", "pa", "ro", "rr", "to"], "North"),
    **dict.fromkeys(["al", "ba", "ce", "ma", "pb", "pe", "pi", "rn", "se"], "Northeast"),
    **dict.fromkeys(["df", "go", "mt", "ms"], "Midwest"),
    **dict.fromkeys(["es", "mg", "rj", "sp"], "Southeast"),
    **dict.fromkeys(["pr", "rs", "sc"], "South"),
}

ORDER_FEATURE_COLUMNS = [
    "customer_unique_id",
    "snapshot",
    "label_repeat",
    *FEATURE_DICTIONARY,
]


def haversine_km(lat1, lng1, lat2, lng2):
    """Return great-circle distance in km; inputs may be scalars or pandas arrays."""
    lat1, lng1, lat2, lng2 = np.broadcast_arrays(
        np.asarray(lat1, dtype=float),
        np.asarray(lng1, dtype=float),
        np.asarray(lat2, dtype=float),
        np.asarray(lng2, dtype=float),
    )
    lat1, lng1, lat2, lng2 = np.radians(lat1), np.radians(lng1), np.radians(lat2), np.radians(lng2)
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    value = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlng / 2) ** 2
    return 6371.0088 * 2 * np.arcsin(np.sqrt(np.clip(value, 0, 1)))


def assert_no_leakage(
    events: pd.DataFrame,
    T,
    H: int | None = None,
    timestamp_columns: tuple[str, ...] = ("purchase_ts",),
    *,
    labels: bool = False,
) -> None:
    """Assert feature timestamps precede T or label timestamps lie in [T, T+H)."""
    snapshot = pd.Timestamp(T)
    for column in timestamp_columns:
        if column not in events:
            continue
        timestamps = pd.to_datetime(events[column], errors="coerce").dropna()
        if labels:
            if H is None:
                raise ValueError("H is required when validating label events")
            upper = snapshot + pd.Timedelta(days=int(H))
            invalid = timestamps.lt(snapshot) | timestamps.ge(upper)
        else:
            invalid = timestamps.ge(snapshot)
        if invalid.any():
            raise ValueError(
                f"Leakage detected: {column} has {int(invalid.sum())} timestamp(s) "
                f"outside the allowed {'label' if labels else 'feature'} window for T={snapshot}"
            )


def _copy_with_datetimes(frame: pd.DataFrame, columns: tuple[str, ...]) -> pd.DataFrame:
    result = frame.copy()
    for column in columns:
        if column in result:
            result[column] = pd.to_datetime(result[column], errors="coerce")
    return result


def _order_level(orders: pd.DataFrame) -> pd.DataFrame:
    if "order_id" not in orders:
        raise ValueError("orders must include order_id")
    data = _copy_with_datetimes(
        orders,
        ("purchase_ts", "delivered_customer_ts", "estimated_delivery_ts"),
    )
    if "is_delivered" in data:
        data = data.loc[data["is_delivered"].fillna(False).astype(bool)]
    elif "order_status" in data:
        data = data.loc[data["order_status"].isin(PARAMS["common"]["valid_statuses"])]
    if "purchase_ts" not in data or "customer_unique_id" not in data:
        raise ValueError("orders must include purchase_ts and customer_unique_id")
    for column in ("delivered_customer_ts", "estimated_delivery_ts"):
        if column not in data:
            data[column] = pd.NaT
    if "freight_value" in data:
        data["freight_value"] = data.groupby("order_id")["freight_value"].transform("sum")
    data = data.sort_values(["order_id"] + (["order_item_id"] if "order_item_id" in data else []))
    return data.drop_duplicates("order_id", keep="first").reset_index(drop=True)


def _item_facts(items: pd.DataFrame, orders: pd.DataFrame) -> pd.DataFrame:
    source = items.copy()
    if source.empty and {"order_id", "price"}.issubset(orders.columns):
        source = orders.copy()
    if "price" not in source:
        if "item_revenue" in source:
            source["price"] = source["item_revenue"]
        else:
            source["price"] = np.nan
    source["price"] = pd.to_numeric(source["price"], errors="coerce")
    if "quantity" not in source:
        source["quantity"] = 1
    source["quantity"] = pd.to_numeric(source["quantity"], errors="coerce").fillna(1)
    # Interactions.price is the summed price for a product/order; raw item prices
    # have one row per order item. In either case, price is merchandise spend.
    if "order_id" not in source:
        raise ValueError("items must include order_id")
    item_cols = ["order_id", "price", "quantity"]
    for column in ("product_id", "category_en"):
        if column in source:
            item_cols.append(column)
    return source[item_cols].copy()


def _ordered_features_fast(history: pd.DataFrame, item_history: pd.DataFrame) -> pd.DataFrame:
    """Vectorized customer-level summaries for production-sized snapshots."""
    customer = "customer_unique_id"
    snapshot = history["_snapshot"].iloc[0]
    summary = history.groupby(customer, sort=True, dropna=False).agg(
        frequency=("order_id", "nunique"),
        first_purchase=("purchase_ts", "min"),
        last_purchase=("purchase_ts", "max"),
    )
    summary["recency_days"] = (snapshot - summary["last_purchase"]).dt.total_seconds() / 86400
    summary["tenure_days"] = (snapshot - summary["first_purchase"]).dt.total_seconds() / 86400
    summary["has_multiple_orders"] = summary["frequency"].gt(1)
    sorted_history = history.sort_values([customer, "purchase_ts", "order_id"])
    gaps = sorted_history.groupby(customer, sort=False)["purchase_ts"].diff().dt.total_seconds()
    summary["avg_days_between_orders"] = (
        (gaps / 86400).groupby(sorted_history[customer], sort=False).mean()
    )
    if "freight_value" in history:
        summary["freight_total"] = history.groupby(customer)["freight_value"].sum()
    else:
        summary["freight_total"] = np.nan

    if len(item_history):
        item_summary = item_history.groupby(customer, sort=False).agg(
            monetary_total=("price", "sum"), quantity_total=("quantity", "sum")
        )
        order_units = item_history.groupby([customer, "order_id"], sort=False)["quantity"].sum()
        item_summary["avg_items_per_order"] = order_units.groupby(level=0, sort=False).mean()
        summary = summary.join(item_summary, how="left")
        summary["monetary_avg"] = summary["monetary_total"] / summary["frequency"]
        summary["avg_order_value"] = summary["monetary_avg"]
        summary["avg_price"] = summary["monetary_total"] / summary["quantity_total"]
    else:
        for column in (
            "monetary_total",
            "quantity_total",
            "avg_items_per_order",
            "monetary_avg",
            "avg_order_value",
            "avg_price",
        ):
            summary[column] = np.nan
    summary["avg_freight"] = summary["freight_total"] / summary["frequency"]
    total_spend = summary["monetary_total"] + summary["freight_total"]
    summary["freight_share"] = summary["freight_total"] / total_spend.where(total_spend.ne(0))

    if "category_en" in item_history and len(item_history):
        categories = (
            item_history.dropna(subset=["category_en"])
            .groupby([customer, "category_en"], observed=True, sort=False)["price"]
            .sum()
            .rename("spend")
            .reset_index()
            .sort_values(
                [customer, "spend", "category_en"],
                ascending=[True, False, True],
                kind="stable",
            )
        )
        category_summary = categories.groupby(customer, sort=False).agg(
            top_category=("category_en", "first"),
            n_distinct_categories=("category_en", "nunique"),
        )
        top3_spend = (
            categories.groupby(customer, sort=False).head(3).groupby(customer)["spend"].sum()
        )
        category_total = categories.groupby(customer, sort=False)["spend"].sum()
        category_summary["top3_spend_share"] = top3_spend / category_total
        summary = summary.join(category_summary, how="left")
    else:
        summary["top_category"] = pd.NA
        summary["n_distinct_categories"] = 0
        summary["top3_spend_share"] = np.nan
    summary["n_distinct_categories"] = summary["n_distinct_categories"].fillna(0).astype("int64")

    latest = sorted_history.drop_duplicates(customer, keep="last").set_index(customer)
    state = latest.get("customer_state", latest.get("state", pd.Series(index=latest.index)))
    summary["state"] = state
    summary["region"] = state.astype("string").str.lower().map(REGIONS)
    if "customer_city" in history:
        city_order_count = history.groupby("customer_city", dropna=True)["order_id"].nunique()
        summary["city_orders_proxy"] = latest["customer_city"].map(city_order_count)
    else:
        summary["city_orders_proxy"] = np.nan
    coord_columns = ["customer_lat", "customer_lng", "seller_lat", "seller_lng"]
    if all(column in latest for column in coord_columns):
        valid = latest[coord_columns].notna().all(axis=1)
        summary["last_order_distance_km"] = np.nan
        summary.loc[valid, "last_order_distance_km"] = haversine_km(
            latest.loc[valid, "customer_lat"],
            latest.loc[valid, "customer_lng"],
            latest.loc[valid, "seller_lat"],
            latest.loc[valid, "seller_lng"],
        )
    else:
        summary["last_order_distance_km"] = np.nan
    summary["last_order_same_state"] = latest.get(
        "same_state", pd.Series(index=latest.index, dtype=object)
    ).astype("boolean")
    last_ts = summary["last_purchase"]
    summary["last_purchase_month"] = last_ts.dt.month.astype("int64")
    summary["last_purchase_quarter"] = last_ts.dt.quarter.astype("int64")
    summary["last_purchase_dow"] = last_ts.dt.dayofweek.astype("int64")
    summary["last_purchase_hour"] = last_ts.dt.hour.astype("int64")
    summary["last_purchase_in_black_friday_window"] = last_ts.dt.month.eq(
        11
    ) & last_ts.dt.day.between(20, 30)

    if "payment_type_main" in history:
        payment_rows = history.loc[
            history["payment_type_main"].notna(), [customer, "payment_type_main"]
        ].copy()
        payment_modes = (
            payment_rows.groupby([customer, "payment_type_main"], observed=True)
            .size()
            .rename("n")
            .reset_index()
            .sort_values(
                [customer, "n", "payment_type_main"],
                ascending=[True, False, True],
                kind="stable",
            )
            .drop_duplicates(customer)
        )
        summary["preferred_payment_type"] = payment_modes.set_index(customer)["payment_type_main"]
        payment_rows["_credit"] = (
            payment_rows["payment_type_main"].astype("string").eq("credit_card")
        )
        summary["share_credit_card"] = payment_rows.groupby(customer)["_credit"].mean()
    else:
        summary["preferred_payment_type"] = pd.NA
        summary["share_credit_card"] = np.nan
    if "max_installments" in history:
        summary["avg_installments"] = history.groupby(customer)["max_installments"].mean()
    else:
        summary["avg_installments"] = np.nan

    delivery = history.loc[
        history["delivered_customer_ts"].notna() & history["delivered_customer_ts"].lt(snapshot)
    ].copy()
    assert_no_leakage(delivery, snapshot, timestamp_columns=("delivered_customer_ts",))
    if len(delivery):
        delivery["_delivery_days"] = (
            delivery["delivered_customer_ts"] - delivery["purchase_ts"]
        ).dt.total_seconds() / 86400
        delivery["_delay"] = (
            delivery["delivered_customer_ts"] - delivery["estimated_delivery_ts"]
        ).dt.total_seconds() / 86400
        delivery["_late"] = (
            delivery["delivered_customer_ts"]
            .gt(delivery["estimated_delivery_ts"])
            .where(delivery["estimated_delivery_ts"].notna())
        )
        summary = summary.join(
            delivery.groupby(customer).agg(
                late_delivery_share=("_late", "mean"),
                avg_delivery_days=("_delivery_days", "mean"),
                avg_delay_vs_estimate=("_delay", "mean"),
            ),
            how="left",
        )
    else:
        summary["late_delivery_share"] = np.nan
        summary["avg_delivery_days"] = np.nan
        summary["avg_delay_vs_estimate"] = np.nan
    latest_delivery_known = latest["delivered_customer_ts"].notna() & latest[
        "delivered_customer_ts"
    ].lt(snapshot)
    summary["last_order_late"] = (
        latest["delivered_customer_ts"]
        .gt(latest["estimated_delivery_ts"])
        .where(latest["estimated_delivery_ts"].notna() & latest_delivery_known)
    )
    summary["frequency"] = summary["frequency"].astype("int64")
    return summary.reset_index().rename(columns={customer: "customer_unique_id"})


def build_snapshot(
    orders: pd.DataFrame,
    items: pd.DataFrame,
    reviews: pd.DataFrame,
    geo: pd.DataFrame,
    T,
    H: int,
) -> pd.DataFrame:
    """Build one row per previously observed customer using only pre-T features."""
    snapshot = pd.Timestamp(T)
    horizon = int(H)
    if horizon <= 0:
        raise ValueError("H must be a positive number of days")
    order_level = _order_level(orders)
    geo_data = geo.drop_duplicates("order_id").copy() if "order_id" in geo else pd.DataFrame()
    if len(geo_data):
        geo_columns = ["order_id"] + [
            column
            for column in (
                "customer_city",
                "customer_lat",
                "customer_lng",
                "seller_lat",
                "seller_lng",
                "same_state",
            )
            if column in geo_data and column not in order_level.columns
        ]
        order_level = order_level.merge(
            geo_data[geo_columns], on="order_id", how="left", validate="one_to_one"
        )
    source_items = _item_facts(items, orders)
    delivered_ids = set(order_level["order_id"])
    source_items = source_items.loc[source_items["order_id"].isin(delivered_ids)].copy()
    source_items = source_items.merge(
        order_level[["order_id", "customer_unique_id", "purchase_ts"]],
        on="order_id",
        how="inner",
        validate="many_to_one",
    )
    historical = order_level.loc[order_level["purchase_ts"].lt(snapshot)].copy()
    future = order_level.loc[
        order_level["purchase_ts"].ge(snapshot)
        & order_level["purchase_ts"].lt(snapshot + pd.Timedelta(days=horizon))
    ].copy()
    assert_no_leakage(historical, snapshot, timestamp_columns=("purchase_ts",))
    assert_no_leakage(future, snapshot, horizon, timestamp_columns=("purchase_ts",), labels=True)
    if historical.empty:
        return pd.DataFrame(columns=ORDER_FEATURE_COLUMNS)

    historical["_snapshot"] = snapshot
    item_history = source_items.loc[source_items["purchase_ts"].lt(snapshot)].copy()
    item_history = item_history.loc[item_history["order_id"].isin(historical["order_id"])]
    assert_no_leakage(item_history, snapshot, timestamp_columns=("purchase_ts",))
    feature_frame = _ordered_features_fast(historical, item_history).set_index("customer_unique_id")
    review_data = reviews.copy()
    if "creation_ts" not in review_data and "review_creation_ts" in review_data:
        review_data = review_data.rename(columns={"review_creation_ts": "creation_ts"})
    if "creation_ts" not in review_data:
        review_data["creation_ts"] = pd.NaT
    if "review_score" not in review_data:
        review_data["review_score"] = np.nan
    if "review_text" not in review_data:
        review_data["review_text"] = pd.NA
    review_data = _copy_with_datetimes(review_data, ("creation_ts",))
    known_reviews = review_data.loc[
        review_data["creation_ts"].notna() & review_data["creation_ts"].lt(snapshot)
    ].copy()
    assert_no_leakage(known_reviews, snapshot, timestamp_columns=("creation_ts",))
    if "customer_unique_id" in known_reviews and len(known_reviews):
        known_reviews["review_score"] = pd.to_numeric(
            known_reviews["review_score"], errors="coerce"
        )
        known_reviews["review_text_length"] = (
            known_reviews["review_text"].astype("string").str.len()
        )
        review_summary = known_reviews.groupby("customer_unique_id", sort=False).agg(
            n_reviews_known=("review_score", "size"),
            avg_review_score=("review_score", "mean"),
            min_review_score=("review_score", "min"),
            avg_review_text_length=("review_text_length", "mean"),
        )
        last_reviews = (
            known_reviews.sort_values("creation_ts")
            .drop_duplicates("customer_unique_id", keep="last")
            .set_index("customer_unique_id")["review_score"]
            .rename("last_review_score")
        )
        feature_frame = feature_frame.join(review_summary.join(last_reviews), how="left")
    for column in (
        "n_reviews_known",
        "avg_review_score",
        "last_review_score",
        "min_review_score",
        "avg_review_text_length",
    ):
        if column not in feature_frame:
            feature_frame[column] = np.nan
    feature_frame["n_reviews_known"] = feature_frame["n_reviews_known"].fillna(0).astype("int64")
    feature_frame["has_review"] = feature_frame["n_reviews_known"].gt(0)
    feature_frame["snapshot"] = snapshot
    feature_frame["label_repeat"] = feature_frame.index.isin(
        set(future["customer_unique_id"])
    ).astype("int8")
    return feature_frame.reset_index().reindex(columns=ORDER_FEATURE_COLUMNS)


def validate_purged_splits(params: dict) -> dict[str, list[pd.Timestamp]]:
    """Validate date ordering, non-empty splits, purge gaps, and end observability."""
    features = params["features"]
    horizon = int(features["horizon_days"])
    splits = {
        name: [pd.Timestamp(value) for value in features["snapshots"][name]]
        for name in ("train", "val", "test")
    }
    for name, dates in splits.items():
        if not dates:
            raise ValueError(f"features.snapshots.{name} must be non-empty")
        if dates != sorted(dates) or len(dates) != len(set(dates)):
            raise ValueError(f"features.snapshots.{name} must be unique and ascending")
    if max(splits["train"]) + pd.Timedelta(days=horizon) > min(splits["val"]):
        raise ValueError("Training label horizon overlaps validation snapshots")
    if max(splits["val"]) + pd.Timedelta(days=horizon) > min(splits["test"]):
        raise ValueError("Validation label horizon overlaps test snapshots")
    end_plus_day = pd.Timestamp(params["common"]["analysis_end"]) + pd.Timedelta(days=1)
    if max(splits["test"]) + pd.Timedelta(days=horizon) > end_plus_day:
        raise ValueError("Test label horizon extends beyond the configured analysis window")
    return splits


def build_all_snapshots(
    params: dict,
    orders: pd.DataFrame,
    items: pd.DataFrame,
    reviews: pd.DataFrame,
    geo: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    """Build and stack customer frames by configured train/val/test split."""
    splits = validate_purged_splits(params)
    horizon = int(params["features"]["horizon_days"])
    outputs = {}
    for split, snapshots in splits.items():
        frames = [build_snapshot(orders, items, reviews, geo, date, horizon) for date in snapshots]
        combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        combined["split"] = split
        outputs[split] = combined
    return outputs


def build_product_features(
    orders: pd.DataFrame,
    items: pd.DataFrame,
    reviews: pd.DataFrame,
    T,
) -> pd.DataFrame:
    """Build one product row from sales/reviews and static metadata known by T."""
    snapshot = pd.Timestamp(T)
    order_level = _order_level(orders)
    eligible_orders = order_level.loc[order_level["purchase_ts"].lt(snapshot)].copy()
    assert_no_leakage(eligible_orders, snapshot, timestamp_columns=("purchase_ts",))
    source_items = items.copy()
    if "price" not in source_items and "item_revenue" in source_items:
        source_items["price"] = source_items["item_revenue"]
    if "quantity" not in source_items:
        source_items["quantity"] = 1
    source_items["price"] = pd.to_numeric(source_items["price"], errors="coerce")
    source_items["quantity"] = pd.to_numeric(source_items["quantity"], errors="coerce").fillna(1)
    source_items = source_items.loc[
        source_items["order_id"].isin(eligible_orders["order_id"])
    ].copy()
    source_items = source_items.drop(columns=["purchase_ts"], errors="ignore")
    source_items = source_items.merge(
        eligible_orders[["order_id", "purchase_ts"]],
        on="order_id",
        how="inner",
        validate="many_to_one",
    )
    assert_no_leakage(source_items, snapshot, timestamp_columns=("purchase_ts",))
    if source_items.empty:
        return pd.DataFrame(columns=["product_id"])
    if "product_id" not in source_items:
        raise ValueError("items must include product_id for product features")
    grouped = source_items.groupby("product_id", observed=True, sort=True)
    rows = []
    for product_id, product_items in grouped:
        amounts = product_items["price"]
        units = product_items["quantity"].sum()
        unit_price = amounts / product_items["quantity"].where(product_items["quantity"].ne(0))
        dates = product_items["purchase_ts"]
        rolling_start = snapshot - pd.Timedelta(days=30)
        recent = product_items.loc[dates.ge(rolling_start) & dates.lt(snapshot), "quantity"].sum()
        row = {
            "product_id": product_id,
            "price_mean": float(unit_price.mean()) if unit_price.notna().any() else np.nan,
            "price_min": float(unit_price.min()) if unit_price.notna().any() else np.nan,
            "price_max": float(unit_price.max()) if unit_price.notna().any() else np.nan,
            "category_en": (
                product_items["category_en"].dropna().iloc[0]
                if "category_en" in product_items and product_items["category_en"].notna().any()
                else pd.NA
            ),
            "units_sold": int(units),
            "days_since_first_sale": float((snapshot - dates.min()).total_seconds() / 86400),
            "sales_velocity_30d": float(recent / 30),
        }
        for column in (
            "photos_qty",
            "description_length",
            "weight_g",
            "volume_cm3",
        ):
            row[column] = product_items[column].iloc[0] if column in product_items else np.nan
            row[f"{column}_missing"] = bool(pd.isna(row[column]))
        rows.append(row)
    result = pd.DataFrame(rows)
    result["product_id"] = result["product_id"].astype("string")

    review_data = reviews.copy()
    if "creation_ts" not in review_data and "review_creation_ts" in review_data:
        review_data = review_data.rename(columns={"review_creation_ts": "creation_ts"})
    if "creation_ts" not in review_data:
        review_data["creation_ts"] = pd.NaT
    if "review_score" not in review_data:
        review_data["review_score"] = np.nan
    review_data = _copy_with_datetimes(review_data, ("creation_ts",))
    if "creation_ts" in review_data:
        known = review_data.loc[
            review_data["creation_ts"].notna() & review_data["creation_ts"].lt(snapshot)
        ].copy()
        assert_no_leakage(known, snapshot, timestamp_columns=("creation_ts",))
        product_key = "primary_product_id" if "primary_product_id" in known else "product_id"
        if product_key in known:
            known = known.loc[known[product_key].notna()]
            scores = pd.to_numeric(known["review_score"], errors="coerce")
            known = known.assign(_score=scores)
            review_stats = known.groupby(product_key, sort=False).agg(
                review_count=("_score", "count"),
                review_avg=("_score", "mean"),
                share_low_score=("_score", lambda values: float(values.le(2).mean())),
            )
            review_stats.index.name = "product_id"
            result = result.merge(
                review_stats.reset_index(), on="product_id", how="left", validate="one_to_one"
            )
    if "review_count" not in result:
        result["review_count"] = 0
        result["review_avg"] = np.nan
        result["share_low_score"] = np.nan
    result["review_count"] = result["review_count"].fillna(0).astype("int64")
    return result.sort_values("product_id").reset_index(drop=True)


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "nogit"


def write_feature_dictionary(path: Path = ROOT / "docs" / "feature_dictionary.md") -> Path:
    """Generate the feature dictionary from the source registry."""
    columns = [
        "name",
        "group",
        "definition",
        "source table",
        "dtype",
        "leakage check",
        "missing-value policy",
    ]
    lines = [
        "# Feature dictionary",
        "",
        "Generated by `python -m src.features dictionary`.",
        "",
        "| " + " | ".join(columns) + " |",
        "|" + "|".join(["---"] * len(columns)) + "|",
    ]
    for name, metadata in FEATURE_DICTIONARY.items():
        values = [name, *metadata]
        lines.append("| " + " | ".join(str(value).replace("|", "\\|") for value in values) + " |")
    for name, metadata in FEATURE_METADATA.items():
        lines.append("| " + " | ".join([name, *metadata]) + " |")
    products = {
        "price_mean": (
            "Product",
            "Mean merchandise price per unit before T",
            "order_items",
            "float",
            "purchase_ts < T",
            "NaN when unavailable",
        ),
        "price_min": (
            "Product",
            "Minimum merchandise price per unit before T",
            "order_items",
            "float",
            "purchase_ts < T",
            "NaN when unavailable",
        ),
        "price_max": (
            "Product",
            "Maximum merchandise price per unit before T",
            "order_items",
            "float",
            "purchase_ts < T",
            "NaN when unavailable",
        ),
        "category_en": (
            "Product",
            "Static product category",
            "products",
            "string",
            "Static metadata",
            "NaN when unavailable",
        ),
        "review_count": (
            "Product",
            "Reviews created before T",
            "reviews",
            "int",
            "creation_ts < T",
            "Zero when no review is known",
        ),
        "review_avg": (
            "Product",
            "Mean score of reviews created before T",
            "reviews",
            "float",
            "creation_ts < T",
            "NaN when no review is known",
        ),
        "share_low_score": (
            "Product",
            "Share of known reviews scored 1-2",
            "reviews",
            "float",
            "creation_ts < T",
            "NaN when no review is known",
        ),
        "units_sold": (
            "Product",
            "Prior delivered item-line quantity",
            "order_items",
            "int",
            "purchase_ts < T",
            "Not applicable",
        ),
        "days_since_first_sale": (
            "Product",
            "Days since first prior sale",
            "order_items",
            "float",
            "purchase_ts < T",
            "Not applicable",
        ),
        "sales_velocity_30d": (
            "Product",
            "Units sold during the 30 days before T divided by 30",
            "order_items",
            "float",
            "purchase_ts in [T-30d,T)",
            "Zero if no recent sales",
        ),
        "photos_qty": (
            "Product",
            "Static product photo count",
            "products",
            "float",
            "Static metadata",
            "NaN retained; missing flag added",
        ),
        "description_length": (
            "Product",
            "Static product description length",
            "products",
            "float",
            "Static metadata",
            "NaN retained; missing flag added",
        ),
        "weight_g": (
            "Product",
            "Static product weight in grams",
            "products",
            "float",
            "Static metadata",
            "NaN retained; missing flag added",
        ),
        "volume_cm3": (
            "Product",
            "Static product volume",
            "products",
            "float",
            "Static metadata",
            "NaN retained; missing flag added",
        ),
    }
    for base in ("photos_qty", "description_length", "weight_g", "volume_cm3"):
        products[f"{base}_missing"] = (
            "Product",
            f"Missingness indicator for {base}",
            "products",
            "bool",
            "Static metadata",
            "Not applicable",
        )
    for name, metadata in products.items():
        lines.append("| " + " | ".join([name, *metadata]) + " |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def build_feature_tables(
    orders: pd.DataFrame,
    items: pd.DataFrame,
    reviews: pd.DataFrame,
    geo: pd.DataFrame,
    product_attributes: pd.DataFrame,
    *,
    params: dict = PARAMS,
    output_dir: Path = DATA_PROCESSED / "features",
) -> dict:
    from .validation import validate_table

    outputs = build_all_snapshots(params, orders, items, reviews, geo)
    splits = validate_purged_splits(params)
    customer_frames = {}
    validation = {}
    for split, frame in outputs.items():
        frame = frame.copy()
        frame["customer_unique_id"] = frame["customer_unique_id"].astype("string")
        frame["label_repeat"] = frame["label_repeat"].astype("int8")
        validation[split] = validate_table(frame, "customer_features")
        customer_frames[split] = frame

    product_items = items.merge(
        product_attributes, on="product_id", how="left", suffixes=("", "_static")
    )
    products = build_product_features(
        orders,
        product_items,
        reviews,
        max(splits["train"]),
    )
    products["product_id"] = products["product_id"].astype("string")
    validation["products"] = validate_table(products, "product_features")
    rates = {
        split: float(frame["label_repeat"].mean()) if len(frame) else 0.0
        for split, frame in customer_frames.items()
    }
    drift_limit = float(params["validation"]["positive_rate_drift_ratio_limit"])
    positive_rates = [rate for rate in rates.values() if rate > 0]
    warnings = []
    if len(positive_rates) > 1 and max(positive_rates) / min(positive_rates) > drift_limit:
        ratio = max(positive_rates) / min(positive_rates)
        warnings.append(f"positive-rate ratio {ratio:.2f} exceeds configured " f"{drift_limit:.2f}")
    output_dir.mkdir(parents=True, exist_ok=True)
    split_summary = {}
    for split, frame in customer_frames.items():
        frame.to_parquet(output_dir / f"customer_features_{split}.parquet", index=False)
        split_summary[split] = {
            "rows": int(len(frame)),
            "positives": int(frame["label_repeat"].sum()),
            "positive_rate": rates[split],
            "snapshots": [date.date().isoformat() for date in splits[split]],
        }
    products.to_parquet(output_dir / "product_features.parquet", index=False)
    train_ids = set(customer_frames["train"]["customer_unique_id"].dropna().astype(str))
    test_ids = set(customer_frames["test"]["customer_unique_id"].dropna().astype(str))
    overlap = len(train_ids & test_ids)
    summary = {
        "horizon_days": int(params["features"]["horizon_days"]),
        "snapshots": {name: values for name, values in params["features"]["snapshots"].items()},
        "splits": split_summary,
        "products": {"rows": int(len(products))},
        "validation": validation,
        "warnings": warnings,
        "test_customers_seen_in_train": overlap,
        "test_customers_new_vs_train": len(test_ids - train_ids),
        "data_version": json.loads(
            (DATA_PROCESSED / "manifest.json").read_text(encoding="utf-8")
        ).get("data_version", "unknown"),
        "git_commit": _git_commit(),
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    write_feature_dictionary()
    metrics = {
        "splits": split_summary,
        "products": {"rows": int(len(products))},
        "validation": validation,
        "warnings": warnings,
    }
    metrics_path = ROOT / "metrics" / "features.json"
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    from .tracking import log_artifact_if_exists, log_metrics_safe, log_params_flat, start_run

    with start_run("churn", "feature_build"):
        log_params_flat(
            {
                "H": params["features"]["horizon_days"],
                "snapshots": params["features"]["snapshots"],
            }
        )
        logged_metrics = {}
        for split, result in split_summary.items():
            logged_metrics[f"rows_{split}"] = result["rows"]
            logged_metrics[f"positive_rate_{split}"] = result["positive_rate"]
        log_metrics_safe(logged_metrics)
        log_artifact_if_exists(manifest_path)
    return summary


def build_from_disk() -> dict:
    """Load Phase 5 raw-fact outputs and build Phase 8 feature files."""
    processed = DATA_PROCESSED
    orders = pd.read_parquet(processed / "orders_enriched.parquet")
    items = pd.read_parquet(processed / "interactions.parquet")
    reviews = pd.read_parquet(processed / "reviews_clean.parquet")
    geo = pd.read_parquet(processed / "order_geo.parquet")
    products = pd.read_parquet(processed / "products_enriched.parquet")
    attributes = products[
        ["product_id", "category_en", "photos_qty", "description_length", "weight_g", "volume_cm3"]
    ].copy()
    # Product static attributes come from core product fields; drop full-window
    # price/review summaries before they can enter this pipeline.
    return build_feature_tables(
        orders,
        items,
        reviews,
        geo,
        attributes,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build leakage-safe feature tables")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("build", help="build feature parquet outputs")
    subparsers.add_parser("dictionary", help="generate the feature dictionary")
    args = parser.parse_args()
    if args.command == "build":
        result = build_from_disk()
        print(json.dumps(result["splits"], indent=2))
    elif args.command == "dictionary":
        print(write_feature_dictionary())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
