from src.config import PARAMS, RANDOM_STATE, ROOT, VALID_STATUSES


def test_seed_and_params():
    assert RANDOM_STATE == 42
    assert (ROOT / "src").exists()
    assert PARAMS["features"]["horizon_days"] > 0
    assert "delivered" in VALID_STATUSES
