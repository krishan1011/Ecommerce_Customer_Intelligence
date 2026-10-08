import copy

import pandas as pd
import pytest

from src.config import PARAMS
from src.features import validate_purged_splits


def test_configured_splits_are_nonempty_ascending_and_purged():
    splits = validate_purged_splits(PARAMS)
    horizon = pd.Timedelta(days=PARAMS["features"]["horizon_days"])
    assert max(splits["train"]) + horizon <= min(splits["val"])
    assert max(splits["val"]) + horizon <= min(splits["test"])
    assert max(splits["test"]) + horizon <= pd.Timestamp(
        PARAMS["common"]["analysis_end"]
    ) + pd.Timedelta(days=1)
    assert all(dates and dates == sorted(dates) for dates in splits.values())


def test_invalid_purge_layout_raises():
    params = copy.deepcopy(PARAMS)
    params["features"]["snapshots"]["val"] = ["2017-10-01"]
    with pytest.raises(ValueError, match="overlaps validation"):
        validate_purged_splits(params)
