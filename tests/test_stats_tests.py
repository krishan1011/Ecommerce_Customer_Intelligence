import numpy as np
import pandas as pd

from src.stats_tests import (
    category_repeat_test,
    delay_score_spearman,
    lateness_repeat_test,
    mann_whitney_effect,
)


def test_mann_whitney_reports_effect_and_detects_synthetic_shift():
    result = mann_whitney_effect(
        pd.Series([8, 9, 10, 11, 12]), pd.Series([1, 2, 3, 4, 5]), "value shift"
    )
    assert set(("test", "statistic", "p_value", "effect_size", "n", "interpretation")) <= set(
        result
    )
    assert result["effect_size"] == 1.0
    assert result["p_value"] < 0.05
    assert result["n"] == 10


def test_mann_whitney_null_case_is_not_significant():
    values = pd.Series([1, 2, 2, 3, 4, 4, 5])
    result = mann_whitney_effect(values, values.copy())
    assert result["p_value"] == 1.0
    assert result["effect_size"] == 0.0


def test_category_chi_square_and_rare_grouping_return_cramers_v():
    categories = pd.Series(["a"] * 100 + ["b"] * 100 + ["rare"] * 4)
    repeat = pd.Series([True] * 80 + [False] * 20 + [True] * 20 + [False] * 80 + [True] * 4)
    result = category_repeat_test(categories, repeat, min_count=10)
    assert result["test"].startswith("Chi-square")
    assert result["effect_size"] > 0
    assert result["category_levels"] == 3
    assert result["n"] == 204


def test_lateness_repeat_and_spearman_return_effect_sizes_and_n():
    late = pd.Series([False] * 10 + [True] * 10)
    repeat = pd.Series([False] * 9 + [True] + [False] * 4 + [True] * 6)
    odds = lateness_repeat_test(late, repeat)
    rho = delay_score_spearman(pd.Series(range(10)), pd.Series(range(10, 0, -1)))
    for result in (odds, rho):
        assert {"test", "statistic", "p_value", "effect_size", "n", "interpretation"} <= set(result)
        assert result["n"] > 0
    assert odds["effect_size"] > 0
    assert np.isclose(rho["effect_size"], -1.0)
