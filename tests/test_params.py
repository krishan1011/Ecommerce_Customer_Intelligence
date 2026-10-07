from src.config import PARAMS


def test_phase_parameters_exist_with_expected_types():
    assert isinstance(PARAMS["common"]["random_state"], int)
    assert isinstance(PARAMS["common"]["analysis_start"], str)
    assert isinstance(PARAMS["common"]["analysis_end"], str)
    assert isinstance(PARAMS["common"]["valid_statuses"], list)
    assert isinstance(PARAMS["features"]["horizon_days"], int)
    assert all(isinstance(value, str) for value in PARAMS["features"]["snapshots"])

    cleaning = PARAMS["cleaning"]
    assert isinstance(cleaning["winsor_lower"], float)
    assert isinstance(cleaning["winsor_upper"], float)

    mlflow = PARAMS["mlflow"]
    assert isinstance(mlflow["tracking_uri"], str)
    assert mlflow["tracking_uri"].startswith("sqlite:///")
    assert all(isinstance(name, str) for name in mlflow["experiments"])

    validation = PARAMS["validation"]
    assert 0 <= validation["soft_null_rate_limit"] <= 1
    assert validation["row_count_tolerance_pct"] >= 0
    assert isinstance(PARAMS["dvc"]["remote_name"], str)


def test_extraction_tuning_parameters_have_expected_types():
    extraction = PARAMS["extraction"]
    assert isinstance(extraction["read_chunksize"], int)
    assert isinstance(extraction["categorical_min_unique"], int)
    assert isinstance(extraction["categorical_max_unique"], int)
    assert isinstance(extraction["categorical_row_fraction"], float)
