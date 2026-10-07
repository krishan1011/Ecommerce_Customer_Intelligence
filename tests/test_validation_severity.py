import pandas as pd
import pytest

from src.validation import TableValidationError, validate_table


def _product_frame():
    return pd.DataFrame(
        {
            "product_id": pd.Series(["p1", "p2"], dtype="string"),
            "weight_g": pd.Series([10.0, 20.0], dtype="float32"),
            "volume_cm3": pd.Series([100.0, 200.0], dtype="float32"),
            "weight_g_missing": pd.Series([False, False], dtype="bool"),
            "length_cm_missing": pd.Series([False, False], dtype="bool"),
            "height_cm_missing": pd.Series([False, False], dtype="bool"),
            "width_cm_missing": pd.Series([False, False], dtype="bool"),
            "name_length_missing": pd.Series([False, False], dtype="bool"),
            "description_length_missing": pd.Series([False, False], dtype="bool"),
            "photos_qty_missing": pd.Series([False, False], dtype="bool"),
        }
    )


def test_hard_violations_raise_and_include_all_lazy_failures():
    frame = _product_frame()
    frame.loc[0, "product_id"] = pd.NA
    frame.loc[1, "weight_g"] = -1

    with pytest.raises(TableValidationError) as error:
        validate_table(frame, "clean_products")

    message = str(error.value)
    assert "product_id" in message
    assert "weight_g" in message
    assert "2 hard failure" in message


def test_soft_null_and_row_count_violations_warn_without_raising():
    frame = _product_frame()
    frame.loc[0, "weight_g"] = float("nan")

    result = validate_table(frame, "clean_products", expected_rows=10, raise_on_error=False)

    assert result["hard_failures"] == 0
    assert result["status"] == "WARN"
    assert any("weight_g: null rate" in warning for warning in result["soft_warnings"])
    assert any("row count" in warning for warning in result["soft_warnings"])
