"""Generate tests/fixtures/policies_sample.csv: a SYNTHETIC stand-in for the raw file.

Run from the repo root:
    python tests/fixtures/make_fixture.py

Every value in the output is made up with a fixed random seed. It is NOT a
sample of the Mendeley portfolio (that file is not committed, its license is
still TBD). It exists so the tests, the SQL queries, dbt and the Power BI
export can run in CI without the real data.

It copies the RAW layout of data/raw/motor_portfolio.csv as far as the code
in this repo tells us: semicolon-delimited, one row per insured per year,
2022-2024, the raw (mislabeled) names vehicle_age and age_driving_licence,
and the category codes the model was trained on.

Columns are in two groups:
- CONFIRMED: read by src/clean.py, src/train.py or notebooks/01_eda.ipynb, so
  the real file has them under exactly these names.
- GUESSED: the real file has 47 columns, including 20 *_claims / *_incurred
  columns and several *_premium breakdowns whose names the code never
  spells out. A few plausible ones are included so the leakage tests have
  something to catch. Nothing in sql/, dbt/ or dashboards/ reads them.

Deliberately bad rows (counts in BAD_ROWS) mirror the problems found in the
EDA: zero exposure, licence ages under 16, missing fuel_type / vehicle_value /
age columns, plus one duplicated (insured_id, year) row that the
data-quality query must catch.
"""

from pathlib import Path

import numpy as np
import pandas as pd

OUT_PATH = Path(__file__).resolve().parent / "policies_sample.csv"
SEED = 20261104
N_INSUREDS = 245
YEARS = [2022, 2023, 2024]

CONFIRMED_COLUMNS = [
    "insured_id",
    "year",
    "policy_status",
    "policy_type",
    "business_type",
    "payment_frequency",
    "bonus_score",
    "driver_age",
    "age_driving_licence",
    "vehicle_age",
    "vehicle_brand",
    "fuel_type",
    "vehicle_value",
    "seats",
    "power_to_weight_ratio",
    "municipality_type",
    "circulation_area",
    "total_exposure",
    "liability_exposure",
    "total_premium",
    "total_claims",
]
GUESSED_COLUMNS = [
    "liability_premium",
    "liability_claims",
    "total_incurred",
    "liability_incurred",
]
COLUMNS = CONFIRMED_COLUMNS + GUESSED_COLUMNS

# How many of each deliberately bad row the file contains. tests/test_sql.py
# checks that the data-quality query finds exactly these.
BAD_ROWS = {
    "zero_exposure": 3,
    "licence_age_under_16": 3,
    "missing_fuel_type": 12,
    "missing_vehicle_value": 6,
    "missing_age_driving_licence": 1,
    "missing_vehicle_age": 1,
    "duplicate_insured_year": 1,
}

# Which years each insured appears in, and how often. Includes a gap
# (2022 + 2024) so tests can check that prev_year_claim only looks at year - 1.
YEAR_PATTERNS = [
    ([2022, 2023, 2024], 0.35),
    ([2022], 0.10),
    ([2022, 2023], 0.15),
    ([2023, 2024], 0.15),
    ([2024], 0.15),
    ([2023], 0.05),
    ([2022, 2024], 0.05),
]

# 15 common brands (the model's top-15 list) plus a few rare ones that should
# end up in the OTHER bucket.
COMMON_BRANDS = [
    "VOLKSWAGEN", "SEAT", "RENAULT", "PEUGEOT", "TOYOTA", "FORD", "OPEL", "CITROEN",
    "BMW", "AUDI", "MERCEDES", "NISSAN", "KIA", "HYUNDAI", "FIAT",
]
RARE_BRANDS = ["DACIA", "SKODA", "MAZDA", "VOLVO", "HONDA"]

POLICY_TYPES = ["TP", "TPG", "CC", "COMP_E", "COMP_N"]
POLICY_TYPE_P = [0.20, 0.15, 0.30, 0.20, 0.15]
# Wider cover -> more ways to claim (same direction as the SHAP results).
POLICY_TYPE_RISK = {"TP": 0.45, "TPG": 0.7, "CC": 0.85, "COMP_E": 1.2, "COMP_N": 2.0}
POLICY_TYPE_PRICE = {"TP": 250, "TPG": 320, "CC": 420, "COMP_E": 650, "COMP_N": 900}


def _insureds(rng: np.random.Generator) -> pd.DataFrame:
    """One row per insured: the attributes that stay fixed across years."""
    n = N_INSUREDS
    age_2022 = rng.normal(46, 14, n).round().clip(18, 85).astype(int)
    licence_age = np.minimum(18 + rng.gamma(1.5, 2.5, n).round().astype(int), age_2022)
    brands = np.where(
        rng.random(n) < 0.9,
        rng.choice(COMMON_BRANDS, n),
        rng.choice(RARE_BRANDS, n),
    )
    pattern_idx = rng.choice(len(YEAR_PATTERNS), n, p=[p for _, p in YEAR_PATTERNS])
    return pd.DataFrame(
        {
            "insured_id": np.arange(100001, 100001 + n),
            "age_2022": age_2022,
            "age_driving_licence": licence_age,
            "vehicle_brand": brands,
            "fuel_type": rng.choice(["D", "G"], n, p=[0.55, 0.45]),
            "vehicle_value": rng.lognormal(np.log(20000), 0.45, n).round(0),
            "seats": rng.choice([2, 4, 5, 7, 9], n, p=[0.03, 0.07, 0.82, 0.06, 0.02]),
            "power_to_weight_ratio": rng.uniform(6, 25, n).round(2),
            "municipality_type": rng.choice(["I", "C", "IS"], n, p=[0.6, 0.3, 0.1]),
            "circulation_area": rng.choice(["U", "R"], n, p=[0.7, 0.3]),
            # Hidden per-insured riskiness, so claims persist across years
            # (the effect the prev_year_claim feature picks up).
            "frailty": rng.gamma(2.0, 0.5, n),
            "years": [YEAR_PATTERNS[i][0] for i in pattern_idx],
        }
    )


def _policy_years(insureds: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    df = insureds.explode("years").rename(columns={"years": "year"}).reset_index(drop=True)
    df["year"] = df["year"].astype(int)
    n = len(df)

    df["driver_age"] = df["age_2022"] + (df["year"] - 2022)
    # Raw quirk (EDA finding 1): vehicle_age actually holds years licensed.
    df["vehicle_age"] = df["driver_age"] - df["age_driving_licence"]

    df["policy_type"] = rng.choice(POLICY_TYPES, n, p=POLICY_TYPE_P)
    first_year = df.groupby("insured_id")["year"].transform("min")
    df["business_type"] = np.where(df["year"] == first_year, "NB", "P")
    df["payment_frequency"] = rng.choice(["A", "S", "Q"], n, p=[0.65, 0.2, 0.15])
    df["bonus_score"] = rng.choice(["G", "N", "B"], n, p=[0.9, 0.07, 0.03])

    full_year = rng.random(n) < 0.58
    df["total_exposure"] = np.where(full_year, 1.0, rng.uniform(0.05, 0.99, n).round(3))
    df["liability_exposure"] = df["total_exposure"]

    annual_price = df["policy_type"].map(POLICY_TYPE_PRICE) * rng.uniform(0.8, 1.25, n)
    df["total_premium"] = (annual_price * df["total_exposure"]).round(2)
    df["liability_premium"] = (df["total_premium"] * rng.uniform(0.35, 0.6, n)).round(2)

    young = np.where(df["driver_age"] < 25, 1.6, 1.0)
    trend = 1 + 0.06 * (df["year"] - 2022)  # claim rate drifts up by year
    rate = (
        0.22 * df["policy_type"].map(POLICY_TYPE_RISK) * df["frailty"] * young * trend
    )
    df["total_claims"] = rng.poisson(rate * df["total_exposure"])
    df["liability_claims"] = rng.binomial(df["total_claims"], 0.4)
    paid = (df["total_claims"] > 0) & (rng.random(n) < 0.75)  # some close at 0
    df["total_incurred"] = np.where(
        paid, rng.lognormal(np.log(1200), 0.9, n) * df["total_claims"], 0.0
    ).round(2)
    df["liability_incurred"] = np.where(
        df["liability_claims"] > 0, df["total_incurred"] * 0.5, 0.0
    ).round(2)

    cancelled = (df["total_exposure"] < 1.0) & (rng.random(n) < 0.5)
    df["policy_status"] = np.where(cancelled, "Cancelled", "Active")
    return df


def _inject_bad_rows(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Overwrite disjoint, randomly chosen rows with the known data problems."""
    df = df.copy()
    n_needed = sum(v for k, v in BAD_ROWS.items() if k != "duplicate_insured_year")
    picks = iter(rng.choice(len(df), n_needed, replace=False))

    def take(k: int) -> list[int]:
        return [next(picks) for _ in range(k)]

    rows = take(BAD_ROWS["zero_exposure"])
    df.loc[rows, ["total_exposure", "liability_exposure"]] = 0.0
    df.loc[rows, ["total_premium", "liability_premium", "total_incurred", "liability_incurred"]] = 0.0
    df.loc[rows, ["total_claims", "liability_claims"]] = 0

    rows = take(BAD_ROWS["licence_age_under_16"])
    df.loc[rows, "age_driving_licence"] = [0, 12, 15][: len(rows)]
    df.loc[rows, "vehicle_age"] = df.loc[rows, "driver_age"] - df.loc[rows, "age_driving_licence"]

    df.loc[take(BAD_ROWS["missing_fuel_type"]), "fuel_type"] = np.nan
    df.loc[take(BAD_ROWS["missing_vehicle_value"]), "vehicle_value"] = np.nan
    df.loc[take(BAD_ROWS["missing_age_driving_licence"]), "age_driving_licence"] = pd.NA
    df.loc[take(BAD_ROWS["missing_vehicle_age"]), "vehicle_age"] = pd.NA

    # One exact copy of a 2024 row. 2024 is the last year, so the copy can't
    # leak into anybody's prev_year_claim; it only shows up in data checks.
    flagged = set(df.index[df.isna().any(axis=1) | (df["total_exposure"] == 0)])
    candidates = [i for i in df.index[df["year"] == 2024] if i not in flagged]
    dup = df.loc[rng.choice(candidates, BAD_ROWS["duplicate_insured_year"], replace=False)]
    return pd.concat([df, dup]).reset_index(drop=True)


def make_fixture(seed: int = SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    df = _policy_years(_insureds(rng), rng)
    # Integer columns that can hold missing values: nullable Int64, so the
    # CSV says "45" rather than "45.0", like the real file.
    for col in ["age_driving_licence", "vehicle_age"]:
        df[col] = df[col].astype("Int64")
    df = _inject_bad_rows(df, rng)
    df = df.sort_values(["year", "insured_id"], kind="stable").reset_index(drop=True)
    return df[COLUMNS]


def main() -> None:
    df = make_fixture()
    df.to_csv(OUT_PATH, sep=";", index=False)
    print(f"wrote {OUT_PATH.name}: {len(df)} rows x {df.shape[1]} columns (SYNTHETIC)")
    print(df["year"].value_counts().sort_index().to_string())


if __name__ == "__main__":
    main()
