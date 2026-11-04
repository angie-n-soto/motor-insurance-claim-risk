"""Tests for src/clean.py: the cleaning steps and the leakage rules.

Runs on hand-made frames and on the SYNTHETIC fixture
(tests/fixtures/policies_sample.csv). No real data is needed.
"""

import numpy as np
import pandas as pd
import pytest

from src import clean
from tests.fixtures.make_fixture import BAD_ROWS, GUESSED_COLUMNS

FIXTURE = clean.ROOT / "tests" / "fixtures" / "policies_sample.csv"


def _row(insured_id, year, total_claims=0, **overrides):
    """One raw-schema row with sensible defaults."""
    row = {
        "insured_id": insured_id,
        "year": year,
        "policy_status": "Active",
        "policy_type": "CC",
        "business_type": "P",
        "payment_frequency": "A",
        "bonus_score": "G",
        "driver_age": 40,
        "age_driving_licence": 20,
        "vehicle_age": 20,
        "vehicle_brand": "SEAT",
        "fuel_type": "D",
        "vehicle_value": 20000.0,
        "seats": 5,
        "power_to_weight_ratio": 12.0,
        "municipality_type": "I",
        "circulation_area": "U",
        "total_exposure": 1.0,
        "liability_exposure": 1.0,
        "total_premium": 400.0,
        "liability_premium": 200.0,
        "total_claims": total_claims,
        "liability_claims": 0,
        "total_incurred": 0.0,
        "liability_incurred": 0.0,
    }
    row.update(overrides)
    return row


@pytest.fixture(scope="module")
def raw_fixture() -> pd.DataFrame:
    return clean.load_raw(FIXTURE)


@pytest.fixture(scope="module")
def tables(raw_fixture):
    return clean.build_modelling_table(raw_fixture)


# --- Leakage rules on the feature list -------------------------------------

LEAKY_EXACT = {"policy_status", "total_premium", "total_claims", "has_claim", "insured_id", "year"}


def test_features_exclude_leaky_columns():
    assert LEAKY_EXACT.isdisjoint(clean.FEATURES)
    for feature in clean.FEATURES:
        assert not feature.endswith(("_claims", "_incurred", "_premium")), feature


def test_target_and_ids_are_not_features():
    assert clean.TARGET not in clean.FEATURES
    assert set(clean.ID_COLUMNS).isdisjoint(clean.FEATURES)
    assert "total_premium" in clean.ID_COLUMNS  # kept for the benchmark only


def test_features_use_renamed_columns_not_raw_names():
    assert "vehicle_age" not in clean.FEATURES
    assert "age_driving_licence" not in clean.FEATURES
    assert {"years_licensed", "licence_age"} <= set(clean.FEATURES)


def test_modelling_table_has_only_allowed_columns(tables):
    expected = clean.ID_COLUMNS + clean.FEATURES + [clean.TARGET]
    for part in tables:
        assert list(part.columns) == expected
        assert "policy_status" not in part.columns
        for col in GUESSED_COLUMNS:  # claim / incurred / premium breakdowns
            assert col not in part.columns


# --- Individual cleaning steps ---------------------------------------------


def test_rename_mislabeled():
    df = clean.rename_mislabeled(pd.DataFrame([_row(1, 2022)]))
    assert "years_licensed" in df.columns and "vehicle_age" not in df.columns
    assert "licence_age" in df.columns and "age_driving_licence" not in df.columns


def test_licence_age_under_16_becomes_missing_and_row_is_kept():
    raw = pd.DataFrame(
        [_row(1, 2022, age_driving_licence=15), _row(2, 2022, age_driving_licence=16),
         _row(3, 2022, age_driving_licence=0)]
    )
    df = clean.fix_invalid_values(clean.rename_mislabeled(raw))
    assert len(df) == 3
    assert df["licence_age"].isna().tolist() == [True, False, True]
    assert df.loc[1, "licence_age"] == clean.MIN_LICENCE_AGE


def test_missing_fuel_type_becomes_its_own_category():
    raw = pd.DataFrame([_row(1, 2022, fuel_type=np.nan), _row(2, 2022, fuel_type="G")])
    df = clean.fix_invalid_values(clean.rename_mislabeled(raw))
    assert df["fuel_type"].tolist() == ["missing", "G"]


def test_zero_exposure_rows_are_dropped():
    raw = pd.DataFrame([_row(1, 2022, total_exposure=0.0), _row(2, 2022, total_exposure=0.01)])
    df = clean.drop_zero_exposure(raw)
    assert df["insured_id"].tolist() == [2]


def test_target_counts_any_claim_even_with_zero_incurred():
    raw = pd.DataFrame(
        [_row(1, 2022, total_claims=0), _row(2, 2022, total_claims=1, total_incurred=0.0),
         _row(3, 2022, total_claims=3)]
    )
    assert clean.add_target(raw)[clean.TARGET].tolist() == [0, 1, 1]


# --- prev_year_claim uses only the previous year ---------------------------


def _prev(rows):
    df = clean.add_prev_year_claim(clean.add_target(pd.DataFrame(rows)))
    return df.set_index(["insured_id", "year"])["prev_year_claim"].to_dict()


def test_prev_year_claim_values():
    prev = _prev(
        [_row(1, 2022, total_claims=1), _row(1, 2023), _row(1, 2024),
         _row(2, 2023, total_claims=2)]
    )
    assert prev[(1, 2022)] == "no_history"
    assert prev[(1, 2023)] == "yes"  # 2022 had a claim
    assert prev[(1, 2024)] == "no"  # 2023 was clean
    assert prev[(2, 2023)] == "no_history"


def test_prev_year_claim_ignores_current_and_future_years():
    clean_now = _prev([_row(1, 2022), _row(1, 2023, total_claims=0), _row(1, 2024, total_claims=0)])
    claim_now = _prev([_row(1, 2022), _row(1, 2023, total_claims=5), _row(1, 2024, total_claims=5)])
    # Changing 2023's own outcome must not change 2023's feature, and the
    # future (2024) must not reach back into 2022 or 2023.
    assert clean_now[(1, 2023)] == claim_now[(1, 2023)] == "no"
    assert clean_now[(1, 2022)] == claim_now[(1, 2022)] == "no_history"
    assert claim_now[(1, 2024)] == "yes"


def test_prev_year_claim_needs_the_immediately_preceding_year():
    # A gap year means no history, even though there's an older claim.
    prev = _prev([_row(1, 2022, total_claims=1), _row(1, 2024)])
    assert prev[(1, 2024)] == "no_history"


def test_prev_year_claim_does_not_mix_insureds():
    prev = _prev([_row(1, 2022, total_claims=1), _row(2, 2023)])
    assert prev[(2, 2023)] == "no_history"


# --- Brand grouping and the out-of-time split ------------------------------


def test_top_brands_are_learned_from_train_only():
    rows = [_row(i, 2022, vehicle_brand="SEAT") for i in range(1, 4)]
    # A brand that only exists in the test year must be grouped as OTHER.
    rows += [_row(i, 2024, vehicle_brand="NEWBRAND") for i in range(10, 30)]
    train, test = clean.build_modelling_table(pd.DataFrame(rows))
    assert set(train["vehicle_brand"]) == {"SEAT"}
    assert set(test["vehicle_brand"]) == {"OTHER"}


def test_group_rare_brands():
    df = pd.DataFrame({"vehicle_brand": ["SEAT", "DACIA", "BMW"]})
    assert clean.group_rare_brands(df, ["SEAT", "BMW"])["vehicle_brand"].tolist() == [
        "SEAT", "OTHER", "BMW"
    ]


def test_out_of_time_split(tables):
    train, test = tables
    assert set(train["year"]) == {2022, 2023}
    assert set(test["year"]) == {clean.TEST_YEAR}


# --- End to end on the synthetic fixture -----------------------------------


def test_fixture_end_to_end(raw_fixture, tables):
    train, test = tables
    # Only the zero-exposure rows are lost (the real data loses 49 this way).
    assert len(train) + len(test) == len(raw_fixture) - BAD_ROWS["zero_exposure"]
    for part in tables:
        assert (part["total_exposure"] > 0).all()
        assert set(part[clean.TARGET]) <= {0, 1}
        assert set(part["prev_year_claim"]) <= {"yes", "no", "no_history"}
        assert part["licence_age"].dropna().ge(clean.MIN_LICENCE_AGE).all()
        assert part["fuel_type"].notna().all()
        assert part["vehicle_brand"].nunique() <= clean.TOP_N_BRANDS + 1
    # The dataset starts in 2022, so 2022 has no history by construction.
    assert set(train.loc[train["year"] == 2022, "prev_year_claim"]) == {"no_history"}
