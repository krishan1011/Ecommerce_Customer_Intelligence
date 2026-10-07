"""Small-sample and large-sample descriptive inference for Phase 6."""

import numpy as np
import pandas as pd
from scipy import stats


def _result(test: str, statistic: float, p_value: float, effect_size: float, n: int) -> dict:
    return {
        "test": test,
        "statistic": float(statistic),
        "p_value": float(p_value),
        "effect_size": float(effect_size),
        "n": int(n),
        "interpretation": (
            "Statistical evidence is present; assess the effect size and practical value."
            if p_value < 0.05
            else "No clear statistical evidence at the 5% level."
        ),
    }


def mann_whitney_effect(first: pd.Series, second: pd.Series, label: str = "Mann-Whitney U") -> dict:
    """Compare two numeric groups; effect is rank-biserial, oriented first minus second."""
    first_values = pd.to_numeric(first, errors="coerce").dropna().to_numpy()
    second_values = pd.to_numeric(second, errors="coerce").dropna().to_numpy()
    if not len(first_values) or not len(second_values):
        raise ValueError("Both groups need at least one numeric observation")
    result = stats.mannwhitneyu(first_values, second_values, alternative="two-sided")
    rank_biserial = 2 * result.statistic / (len(first_values) * len(second_values)) - 1
    return _result(
        label,
        result.statistic,
        result.pvalue,
        rank_biserial,
        len(first_values) + len(second_values),
    )


def category_repeat_test(category: pd.Series, repeat: pd.Series, min_count: int = 50) -> dict:
    """Test category association with repeat purchasing; rare categories join the other group."""
    frame = pd.DataFrame({"category": category, "repeat": repeat}).dropna()
    if frame.empty:
        raise ValueError("Category and repeat data must contain observations")
    frame["category"] = frame["category"].astype("string")
    counts = frame["category"].value_counts()
    common = counts[counts >= min_count].index
    frame["category"] = frame["category"].where(frame["category"].isin(common), "other")
    contingency = pd.crosstab(frame["category"], frame["repeat"])
    statistic, p_value, _, _ = stats.chi2_contingency(contingency)
    n = int(contingency.to_numpy().sum())
    denominator = min(contingency.shape) - 1
    cramers_v = np.sqrt(statistic / (n * denominator)) if denominator > 0 and n else 0.0
    result = _result("Chi-square category vs repeat", statistic, p_value, cramers_v, n)
    result["category_levels"] = int(contingency.shape[0])
    return result


def lateness_repeat_test(late: pd.Series, repeat: pd.Series) -> dict:
    """Test first-order lateness association with repeat purchase; effect is odds ratio."""
    frame = pd.DataFrame({"late": late, "repeat": repeat}).dropna()
    table = pd.crosstab(frame["late"].astype(bool), frame["repeat"].astype(bool)).reindex(
        index=[False, True], columns=[False, True], fill_value=0
    )
    odds_ratio, p_value = stats.fisher_exact(table.to_numpy())
    result = _result(
        "Fisher exact: first-order lateness vs repeat",
        odds_ratio,
        p_value,
        odds_ratio,
        int(table.to_numpy().sum()),
    )
    result["interpretation"] = (
        "The odds ratio compares repeat odds for late vs on-time first orders; "
        + result["interpretation"]
    )
    return result


def delay_score_spearman(delay_days: pd.Series, score: pd.Series) -> dict:
    """Measure monotonic association of delivery delay days and review score."""
    frame = (
        pd.DataFrame({"delay": delay_days, "score": score})
        .apply(pd.to_numeric, errors="coerce")
        .dropna()
    )
    if len(frame) < 2:
        raise ValueError("Spearman test requires at least two complete observations")
    statistic, p_value = stats.spearmanr(frame["delay"], frame["score"])
    return _result(
        "Spearman: delivery delay vs review score",
        statistic,
        p_value,
        statistic,
        len(frame),
    )
