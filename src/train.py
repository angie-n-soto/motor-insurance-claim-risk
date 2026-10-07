"""Train and evaluate claim-occurrence models.

Run from the repo root (after python -m src.clean):
    python -m src.train

1. Cross-validate logistic regression and XGBoost on 2022-2023 (GroupKFold by insured).
2. Refit both on all of 2022-2023 and score them once on the untouched 2024 test year.
3. Compare against two baselines: the base rate and the insurer's own premium.
4. Save metrics, plots, and the better model (by CV) to models/claim_model.joblib.
"""

import json
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")  # write files, never open a window
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.model_selection import GroupKFold, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

from src.clean import CATEGORICAL_FEATURES, FEATURES, NUMERIC_FEATURES, OUT_DIR, TARGET

ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "models" / "claim_model.joblib"
FIG_DIR = ROOT / "reports" / "figures"
METRICS_PATH = ROOT / "reports" / "metrics.json"

SEED = 42
CV_FOLDS = 5


def build_preprocessor(scale_numeric: bool) -> ColumnTransformer:
    # Preprocessing lives INSIDE the model pipeline. Two reasons:
    # 1. In cross-validation, the median and scaling are learned from each
    #    training fold only, so validation rows never leak into them.
    # 2. The saved pipeline takes raw feature values, so the API can't
    #    preprocess differently from training (training/serving skew).
    numeric_steps = [("impute", SimpleImputer(strategy="median"))]
    if scale_numeric:
        # Logistic regression's regularization penalizes all coefficients
        # equally, so features need comparable scales. Trees don't care.
        numeric_steps.append(("scale", StandardScaler()))

    return ColumnTransformer(
        [
            # handle_unknown="ignore": a category never seen in training
            # (e.g. a new brand typed into the API) becomes all zeros
            # instead of crashing the prediction.
            ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
            ("num", Pipeline(numeric_steps), NUMERIC_FEATURES),
        ]
    )


def build_models() -> dict[str, Pipeline]:
    logistic = Pipeline(
        [
            ("prep", build_preprocessor(scale_numeric=True)),
            ("model", LogisticRegression(max_iter=2000)),
        ]
    )
    # Not tuned (deadline). These are standard, conservative settings:
    # many small steps (low learning rate) with shallow trees and row/column
    # subsampling, which together resist overfitting.
    xgboost = Pipeline(
        [
            ("prep", build_preprocessor(scale_numeric=False)),
            (
                "model",
                XGBClassifier(
                    n_estimators=500,
                    learning_rate=0.05,
                    max_depth=5,
                    subsample=0.8,
                    colsample_bytree=0.8,
                    tree_method="hist",
                    n_jobs=-1,
                    random_state=SEED,
                ),
            ),
        ]
    )
    return {"logistic": logistic, "xgboost": xgboost}


def decile_table(y_true: np.ndarray, score: np.ndarray) -> pd.DataFrame:
    """Sort policies by predicted risk into 10 equal groups; claim rate per group."""
    df = pd.DataFrame({"y": y_true, "score": score})
    # rank first so ties don't create uneven deciles; decile 10 = riskiest
    df["decile"] = pd.qcut(df["score"].rank(method="first"), 10, labels=range(1, 11))
    table = df.groupby("decile", observed=True).agg(
        policies=("y", "size"), claim_rate=("y", "mean"), mean_predicted=("score", "mean")
    )
    table["lift"] = table["claim_rate"] / df["y"].mean()
    return table


def evaluate(y_true: np.ndarray, score: np.ndarray, is_probability: bool) -> dict:
    metrics = {
        # PR-AUC: how well positives are concentrated at the top of the
        # ranking. With 15% positives, a random ranking scores 0.15.
        "pr_auc": average_precision_score(y_true, score),
        "roc_auc": roc_auc_score(y_true, score),
    }
    # A constant score (the base-rate baseline) ranks nobody, so its
    # deciles would just be arbitrary row order. Leave them out.
    if np.unique(score).size > 1:
        deciles = decile_table(y_true, score)
        metrics["top_decile_lift"] = deciles["lift"].iloc[-1]
        metrics["top_vs_bottom_decile"] = deciles["claim_rate"].iloc[-1] / deciles["claim_rate"].iloc[0]
    if is_probability:
        # Brier score: mean squared error of the probabilities. Only
        # meaningful for real probabilities, not for a premium in euros.
        metrics["brier"] = brier_score_loss(y_true, score)
        metrics["mean_predicted"] = float(np.mean(score))
        metrics["actual_rate"] = float(np.mean(y_true))
    return {k: round(float(v), 4) for k, v in metrics.items()}


def plot_deciles(table: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(table.index.astype(int), table["claim_rate"], color="#3b6ea5")
    ax.axhline(table["claim_rate"].mean(), color="#888", linestyle="--", label="portfolio average")
    ax.set_xlabel("Risk decile (1 = lowest predicted risk, 10 = highest)")
    ax.set_ylabel("Actual claim rate, 2024")
    ax.set_title("Claim rate by predicted-risk decile (test year 2024)")
    ax.set_xticks(range(1, 11))
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_calibration(y_true: np.ndarray, probs: dict[str, np.ndarray], path: Path) -> None:
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.plot([0, 0.5], [0, 0.5], color="#888", linestyle="--", label="perfect calibration")
    for name, p in probs.items():
        frac_pos, mean_pred = calibration_curve(y_true, p, n_bins=10, strategy="quantile")
        ax.plot(mean_pred, frac_pos, marker="o", label=name)
    ax.set_xlabel("Predicted probability")
    ax.set_ylabel("Actual claim rate")
    ax.set_title("Calibration on 2024")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main() -> None:
    train = pd.read_parquet(OUT_DIR / "train.parquet")
    test = pd.read_parquet(OUT_DIR / "test.parquet")
    X_train, y_train = train[FEATURES], train[TARGET].to_numpy()
    X_test, y_test = test[FEATURES], test[TARGET].to_numpy()

    models = build_models()

    # --- 1. Model selection on train only --------------------------------
    # GroupKFold keeps all rows of one insured in the same fold. Otherwise
    # the model could see someone's 2022 row and be validated on their 2023
    # row, which inflates the score.
    cv = GroupKFold(n_splits=CV_FOLDS)
    cv_results = {}
    for name, pipe in models.items():
        scores = cross_val_score(
            pipe, X_train, y_train, groups=train["insured_id"], cv=cv,
            scoring="average_precision", n_jobs=1,
        )
        cv_results[name] = {"pr_auc_mean": round(scores.mean(), 4), "pr_auc_std": round(scores.std(), 4)}
        print(f"CV {name:9s} PR-AUC {scores.mean():.4f} ± {scores.std():.4f}")
    best_name = max(cv_results, key=lambda n: cv_results[n]["pr_auc_mean"])
    print(f"-> selected by CV: {best_name}\n")

    # --- 2. Final evaluation on the 2024 test year (touched once) --------
    test_results, test_probs = {}, {}
    for name, pipe in models.items():
        pipe.fit(X_train, y_train)
        test_probs[name] = pipe.predict_proba(X_test)[:, 1]
        test_results[name] = evaluate(y_test, test_probs[name], is_probability=True)

    # --- 3. Baselines -----------------------------------------------------
    # Base rate: predict the training claim rate for everyone. It ranks
    # nobody, so its PR-AUC equals the positive rate. That's the floor.
    base_rate = np.full(len(y_test), y_train.mean())
    test_results["baseline_base_rate"] = evaluate(y_test, base_rate, is_probability=True)
    # Insurer's premium: the earned premium is the insurer's own estimate of
    # expected cost for the exposure period. Ranking by it asks: does our
    # model sort risk better than the price the insurer actually charged?
    test_results["baseline_insurer_premium"] = evaluate(
        y_test, test["total_premium"].to_numpy(), is_probability=False
    )

    print(pd.DataFrame(test_results).T.to_string())

    # --- 4. Save artifacts ------------------------------------------------
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    deciles = decile_table(y_test, test_probs[best_name])
    print(f"\nDeciles ({best_name}, 2024):\n{deciles.round(3).to_string()}")
    plot_deciles(deciles, FIG_DIR / "decile_lift.png")
    plot_calibration(y_test, test_probs, FIG_DIR / "calibration.png")

    METRICS_PATH.write_text(
        json.dumps({"cv_train_2022_2023": cv_results, "test_2024": test_results,
                    "selected_model": best_name}, indent=2)
    )

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "pipeline": models[best_name],
            "model_name": best_name,
            "features": FEATURES,
            "train_claim_rate": float(y_train.mean()),
            # The API always predicts a full year (exposure = 1.0), so its
            # "compared with average" must use full-year policies only.
            # The overall rate (13.6%) includes part-year policies and would
            # make nearly every full-year prediction look above average.
            "full_year_claim_rate": float(y_train[train["total_exposure"] == 1.0].mean()),
        },
        MODEL_PATH,
    )
    print(f"\nSaved {best_name} to {MODEL_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
