"""Clean the raw motor portfolio and build the modelling table.

Run from the repo root:
    python -m src.clean

Reads  data/raw/motor_portfolio.csv
Writes data/processed/train.parquet (2022-2023) and test.parquet (2024)

Every decision here is backed by a finding in notebooks/01_eda.ipynb;
the numbers in comments refer to the findings table in PROJECT_PLAN.md.
"""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "data" / "raw" / "motor_portfolio.csv"
OUT_DIR = ROOT / "data" / "processed"

TEST_YEAR = 2024
TOP_N_BRANDS = 15
MIN_LICENCE_AGE = 16

TARGET = "has_claim"

# Columns the model is allowed to see. Everything here is known at policy start.
CATEGORICAL_FEATURES = [
    "policy_type",
    "business_type",
    "payment_frequency",
    "bonus_score",
    "fuel_type",
    "vehicle_brand",
    "municipality_type",
    "circulation_area",
    "prev_year_claim",
]
NUMERIC_FEATURES = [
    "driver_age",
    "years_licensed",
    "licence_age",
    "vehicle_value",
    "seats",
    "power_to_weight_ratio",
    "total_exposure",
]
FEATURES = CATEGORICAL_FEATURES + NUMERIC_FEATURES

# Kept alongside the features but never fed to the model:
# insured_id for GroupKFold, year for the split, total_premium for the benchmark.
ID_COLUMNS = ["insured_id", "year", "total_premium"]


def load_raw(path: Path = RAW_PATH) -> pd.DataFrame:
    return pd.read_csv(path, sep=";")


def rename_mislabeled(df: pd.DataFrame) -> pd.DataFrame:
    # Findings 1 and 2: the data dictionary is wrong about these two columns.
    # vehicle_age == driver_age - age_driving_licence in 99.9% of rows, so it is
    # years licensed; age_driving_licence holds an age (median 20), not a year.
    return df.rename(
        columns={"vehicle_age": "years_licensed", "age_driving_licence": "licence_age"}
    )


def fix_invalid_values(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # Nobody legally drives before 16, so these are data-entry errors. Setting
    # them to missing (not dropping the row) keeps the rest of the row's
    # information; the model pipeline imputes them later.
    df.loc[df["licence_age"] < MIN_LICENCE_AGE, "licence_age"] = np.nan

    # Finding 8: missing fuel_type has a 21% claim rate vs 14% overall, so
    # "missing" is itself informative. Make it an explicit category instead of
    # imputing the most common value, which would hide that signal.
    df["fuel_type"] = df["fuel_type"].fillna("missing")
    return df


def drop_zero_exposure(df: pd.DataFrame) -> pd.DataFrame:
    # Finding 5: a policy that was never in force for a single day had no
    # chance to claim. These 49 rows aren't policies, they're noise.
    return df[df["total_exposure"] > 0].copy()


def add_target(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # Finding 9: claims closed at 0 incurred still count. A reported claim is
    # the event we're predicting, whether or not the insurer paid.
    df[TARGET] = (df["total_claims"] > 0).astype(int)
    return df


def add_prev_year_claim(df: pd.DataFrame) -> pd.DataFrame:
    """Finding 7: did this insured claim in the immediately preceding year?

    Values: "yes", "no", or "no_history" (we have no row for them last year).
    Built only from year-1, so it uses nothing the insurer wouldn't know at
    renewal time. That's what makes it safe, not leakage.
    """
    df = df.copy()
    prev = df[["insured_id", "year", TARGET]].copy()
    prev["year"] = prev["year"] + 1  # shift last year's outcome onto this year
    prev = prev.rename(columns={TARGET: "_prev_claim"})

    df = df.merge(prev, on=["insured_id", "year"], how="left")
    df["prev_year_claim"] = (
        df["_prev_claim"].map({1: "yes", 0: "no"}).fillna("no_history")
    )
    return df.drop(columns="_prev_claim")


def group_rare_brands(df: pd.DataFrame, top_brands: list[str]) -> pd.DataFrame:
    # 68 brands, long tail. Rare brands have too few rows to learn a reliable
    # claim rate, so they share one "OTHER" bucket.
    df = df.copy()
    df["vehicle_brand"] = df["vehicle_brand"].where(
        df["vehicle_brand"].isin(top_brands), "OTHER"
    )
    return df


def build_modelling_table(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = rename_mislabeled(raw)
    df = fix_invalid_values(df)
    df = drop_zero_exposure(df)
    df = add_target(df)
    df = add_prev_year_claim(df)

    train = df[df["year"] < TEST_YEAR]
    test = df[df["year"] == TEST_YEAR]

    # The top-brand list is learned from TRAIN only, then applied to both.
    # If 2024 data chose the list, test data would have influenced a training
    # decision, a small but real form of leakage.
    top_brands = train["vehicle_brand"].value_counts().head(TOP_N_BRANDS).index.tolist()
    train = group_rare_brands(train, top_brands)
    test = group_rare_brands(test, top_brands)

    # Selecting columns explicitly (instead of dropping the bad ones) means the
    # 20 claim/incurred columns (finding 3), policy_status (finding 4), and the
    # premium breakdowns (finding 6) can never sneak in as features by accident.
    keep = ID_COLUMNS + FEATURES + [TARGET]
    return train[keep].reset_index(drop=True), test[keep].reset_index(drop=True)


def main() -> None:
    raw = load_raw()
    train, test = build_modelling_table(raw)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    train.to_parquet(OUT_DIR / "train.parquet", index=False)
    test.to_parquet(OUT_DIR / "test.parquet", index=False)

    print(f"raw:   {len(raw):,} rows")
    for name, part in [("train", train), ("test", test)]:
        print(
            f"{name}: {len(part):,} rows, claim rate {part[TARGET].mean():.1%}, "
            f"years {sorted(part['year'].unique().tolist())}"
        )
    print("\nclaim rate by prev_year_claim (train):")
    print(train.groupby("prev_year_claim")[TARGET].agg(["mean", "size"]).round(3))


if __name__ == "__main__":
    main()
