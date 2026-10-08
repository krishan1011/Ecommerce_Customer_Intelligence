import json

import pandas as pd
import pytest

from src.config import DATA_PROCESSED, ROOT


def test_feature_tables_match_manifest_and_use_pre_snapshot_purchases():
    feature_dir = DATA_PROCESSED / "features"
    manifest_path = feature_dir / "manifest.json"
    paths = [
        feature_dir / f"customer_features_{split}.parquet" for split in ("train", "val", "test")
    ]
    if not manifest_path.is_file() or not all(path.is_file() for path in paths):
        pytest.skip("Phase 8 feature parquet files are not present")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw_orders = pd.read_parquet(DATA_PROCESSED / "orders_enriched.parquet")
    raw_orders = raw_orders.loc[raw_orders["is_delivered"].fillna(False)]
    for split, path in zip(("train", "val", "test"), paths, strict=True):
        frame = pd.read_parquet(path)
        assert not frame.duplicated(["customer_unique_id", "snapshot"]).any()
        split_manifest = manifest["splits"][split]
        assert len(frame) == split_manifest["rows"]
        assert int(frame["label_repeat"].sum()) == split_manifest["positives"]
        assert frame["label_repeat"].mean() == pytest.approx(split_manifest["positive_rate"])
        assert not frame.duplicated(["customer_unique_id", "snapshot"]).any()
        for row in frame.sample(min(20, len(frame)), random_state=7).itertuples():
            snapshot = pd.Timestamp(row.snapshot)
            customer_orders = raw_orders.loc[
                raw_orders["customer_unique_id"].astype(str).eq(str(row.customer_unique_id))
                & raw_orders["purchase_ts"].lt(snapshot)
            ]
            assert not customer_orders.empty
            latest_purchase = customer_orders["purchase_ts"].max()
            expected_recency = (snapshot - latest_purchase).total_seconds() / 86400
            assert row.recency_days == pytest.approx(expected_recency)
            assert customer_orders["purchase_ts"].max() < snapshot

    assert manifest["test_customers_seen_in_train"] + manifest["test_customers_new_vs_train"] > 0
    design = (ROOT / "docs" / "feature_design.md").read_text(encoding="utf-8").lower()
    assert "new customers only" in design
