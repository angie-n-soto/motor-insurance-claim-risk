"""SHAP explanations for the saved claim model.

Run from the repo root (after python -m src.train):
    python -m src.explain

Writes the global importance and effect plots to reports/figures/ and prints
a sanity-check table. top_reasons() is imported by the API so each
prediction comes with its own explanation.
"""

from functools import lru_cache
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap

from src.clean import CATEGORICAL_FEATURES, NUMERIC_FEATURES, OUT_DIR
from src.train import FIG_DIR, MODEL_PATH, SEED

SAMPLE_SIZE = 5000  # SHAP on all 168k test rows is slow and adds nothing


@lru_cache(maxsize=1)
def load_model(path: Path = MODEL_PATH) -> dict:
    return joblib.load(path)


@lru_cache(maxsize=1)
def _explainer(path: Path = MODEL_PATH) -> shap.TreeExplainer:
    # TreeExplainer computes exact SHAP values from the tree structure, fast
    # enough to run on every API request.
    return shap.TreeExplainer(load_model(path)["pipeline"].named_steps["model"])


def _column_to_feature(prep) -> list[str]:
    """Map each model input column back to the original feature it came from.

    One-hot encoding turns policy_type into 5 columns. Nobody wants to hear
    "policy_type_CC = 0 raised your risk", so we add those columns' SHAP
    values back together. That's valid because SHAP values are additive.
    """
    encoder = prep.named_transformers_["cat"]
    owners = [
        feature
        for feature, cats in zip(CATEGORICAL_FEATURES, encoder.categories_)
        for _ in cats
    ]
    return owners + NUMERIC_FEATURES


def shap_by_feature(X: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    """SHAP values per original feature, in log-odds, plus the base value.

    Log-odds is the model's internal scale. Positive = pushes risk up,
    negative = pushes risk down. The base value plus the sum of a row's
    SHAP values equals that row's prediction in log-odds.
    """
    pipeline = load_model()["pipeline"]
    prep = pipeline.named_steps["prep"]
    values = _explainer().shap_values(prep.transform(X))
    per_column = pd.DataFrame(values, columns=_column_to_feature(prep), index=X.index)
    per_feature = per_column.T.groupby(level=0).sum().T
    return per_feature[CATEGORICAL_FEATURES + NUMERIC_FEATURES], float(_explainer().expected_value)


def top_reasons(row: dict, n: int = 3, exclude: tuple[str, ...] = ("total_exposure",)) -> list[dict]:
    """The n features that moved this prediction most, in either direction.

    total_exposure is excluded by default: the API fixes it at 1.0 (a full
    year) for everyone, so "a full year of cover raises your risk" would top
    every explanation without telling the user anything about their policy.
    """
    X = pd.DataFrame([row])[load_model()["features"]]
    contributions = shap_by_feature(X)[0].iloc[0].drop(list(exclude))
    strongest = contributions.reindex(contributions.abs().sort_values(ascending=False).index)
    return [
        {
            "feature": feature,
            "value": row.get(feature),
            "effect": "raises risk" if shap_value > 0 else "lowers risk",
            "shap_log_odds": round(float(shap_value), 3),
        }
        for feature, shap_value in strongest.head(n).items()
    ]


def plot_importance(shap_df: pd.DataFrame, path: Path) -> pd.Series:
    # Mean |SHAP| = on average, how far this feature moves a prediction,
    # regardless of direction. That's global importance.
    importance = shap_df.abs().mean().sort_values()
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.barh(importance.index, importance.values, color="#3b6ea5")
    ax.set_xlabel("Mean |SHAP value| (log-odds): average impact on a prediction")
    ax.set_title("What drives predicted claim risk (2024 sample)")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return importance.sort_values(ascending=False)


def effect_table(X: pd.DataFrame, shap_df: pd.DataFrame, feature: str) -> pd.Series:
    """Average SHAP per category (or per value bin): the direction of the effect."""
    if feature in NUMERIC_FEATURES:
        groups = pd.qcut(X[feature], 5, duplicates="drop", precision=2)
    else:
        groups = X[feature]
    return shap_df[feature].groupby(groups, observed=True).mean().round(3)


def plot_effects(X: pd.DataFrame, shap_df: pd.DataFrame, features: list[str], path: Path) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(10, 7))
    for ax, feature in zip(axes.flat, features):
        effect = effect_table(X, shap_df, feature)
        labels = [str(i) for i in effect.index]
        colors = ["#c0504d" if v > 0 else "#3b6ea5" for v in effect.values]
        ax.bar(labels, effect.values, color=colors)
        ax.axhline(0, color="#888", linewidth=0.8)
        ax.set_title(feature)
        ax.set_ylabel("Mean SHAP (log-odds)")
        ax.tick_params(axis="x", rotation=30, labelsize=8)
    fig.suptitle("Direction of effect: red raises risk, blue lowers it")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main() -> None:
    features = load_model()["features"]
    test = pd.read_parquet(OUT_DIR / "test.parquet")
    X = test[features].sample(SAMPLE_SIZE, random_state=SEED)

    shap_df, base_value = shap_by_feature(X)

    # Sanity check: SHAP's additivity guarantee. Base value + row's SHAP sum
    # must reproduce the model's own prediction. If not, the mapping is wrong.
    pipeline = load_model()["pipeline"]
    reconstructed = 1 / (1 + np.exp(-(base_value + shap_df.sum(axis=1))))
    max_error = np.abs(reconstructed - pipeline.predict_proba(X)[:, 1]).max()
    print(f"additivity check, max error: {max_error:.2e}")

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    importance = plot_importance(shap_df, FIG_DIR / "shap_importance.png")
    print("\nGlobal importance (mean |SHAP|):")
    print(importance.round(3).to_string())

    key_features = ["prev_year_claim", "total_exposure", "driver_age", "years_licensed"]
    plot_effects(X, shap_df, key_features, FIG_DIR / "shap_effects.png")
    print("\nDirection of effect (mean SHAP by group):")
    for feature in key_features + ["policy_type", "fuel_type"]:
        print(f"\n{feature}:\n{effect_table(X, shap_df, feature).to_string()}")

    example = X.iloc[0].to_dict()
    print(f"\nExample top reasons for one policy: {top_reasons(example)}")


if __name__ == "__main__":
    main()
