"""Run every SQL query against the SYNTHETIC fixture and check the outputs are sane.

These tests check that the SQL runs and behaves (rates in [0, 1], ten
deciles, the data checks find the planted bad rows). They say nothing about
the real portfolio's numbers.
"""

import duckdb
import pandas as pd
import pytest

import sql.run_all as run_all_module
from sql.export_scores import export_scores
from sql.load import FIXTURE_CSV, load
from sql.run_all import query_files, run_all
from src import clean
from tests.fixtures.make_fixture import BAD_ROWS


@pytest.fixture(scope="module")
def db_path(tmp_path_factory):
    path = tmp_path_factory.mktemp("sql") / "fixture.duckdb"
    load(FIXTURE_CSV, path).close()
    export_scores(path)
    return path


@pytest.fixture(scope="module")
def results(db_path, tmp_path_factory):
    return run_all(db_path, tmp_path_factory.mktemp("results"))


def _rate_columns(df: pd.DataFrame) -> list[str]:
    keys = ("rate", "share", "retention", "mean_predicted")
    return [c for c in df.columns if any(k in c for k in keys) and not c.startswith("prev_")]


def test_there_are_ten_queries():
    names = [p.stem for p in query_files()]
    assert len(names) == 10
    assert [n[:2] for n in names] == [f"{i:02d}" for i in range(1, 11)]


def test_every_query_returns_rows(results):
    assert len(results) == 10
    for name, df in results.items():
        assert not df.empty, name


def test_rates_are_between_0_and_1(results):
    for name, df in results.items():
        for col in _rate_columns(df):
            values = df[col].dropna()
            assert values.between(0, 1).all(), f"{name}.{col}"


def test_results_written_as_csv(results, db_path, tmp_path):
    out = tmp_path / "out"
    run_all(db_path, out)
    assert sorted(p.stem for p in out.glob("*.csv")) == sorted(results)


def test_claim_rate_by_year(results):
    df = results["01_claim_rate_by_year"]
    assert df["year"].tolist() == [2022, 2023, 2024]
    raw = clean.load_raw(FIXTURE_CSV)
    assert df["policies"].sum() == (raw["total_exposure"] > 0).sum()


def test_min_exposure_filter(results):
    df = results["02_policy_type_by_payment_frequency"]
    raw = clean.load_raw(FIXTURE_CSV)
    assert (df["exposure_years"] >= 0.01 * raw["total_exposure"].sum() - 0.05).all()


def test_price_vs_risk_indices_positive(results):
    df = results["03_price_vs_risk_by_segment"]
    assert (df["price_index"] > 0).all()
    assert (df["risk_index"] >= 0).all()


def test_brand_yoy_lag(results):
    df = results["04_brand_yoy_change"]
    assert df["vehicle_brand"].nunique() <= 15
    first_years = df.sort_values("year").groupby("vehicle_brand").head(1)
    assert first_years["prev_year_claim_rate"].isna().all()  # LAG has nothing before the first year


def test_claim_persistence_matches_clean_py(results):
    """Query 05 must build prev_year_claim exactly like src/clean.py does."""
    df = results["05_claim_persistence"]
    assert set(df["prev_year_claim"]) <= {"yes", "no", "no_history"}
    train, _ = clean.build_modelling_table(clean.load_raw(FIXTURE_CSV))
    expected = train.groupby("prev_year_claim")[clean.TARGET].agg(["size", "mean"])
    sql = df[df["split"] == "train"].set_index("prev_year_claim")
    for category, row in expected.iterrows():
        assert sql.loc[category, "policies"] == row["size"]
        assert sql.loc[category, "claim_rate"] == pytest.approx(row["mean"], abs=1e-4)


def test_brand_ranks_within_fuel(results):
    df = results["06_brand_rank_within_fuel"]
    for _, group in df.groupby("fuel_type"):
        assert group["rank_in_fuel"].min() == 1
        assert (group["dense_rank_in_fuel"] <= group["rank_in_fuel"]).all()


def test_decile_lift(results, db_path):
    df = results["07_decile_lift"]
    assert df["decile"].tolist() == list(range(1, 11))
    con = duckdb.connect(str(db_path), read_only=True)
    n_scores = con.execute("SELECT count(*) FROM scores").fetchone()[0]
    con.close()
    assert df["policies"].sum() == n_scores
    assert df["policies"].max() - df["policies"].min() <= 1  # NTILE: equal-sized groups
    assert df["mean_predicted"].is_monotonic_increasing


def test_running_totals(results):
    df = results["08_running_totals_by_age_band"]
    assert df["running_exposure"].is_monotonic_increasing
    assert df["running_claims"].is_monotonic_increasing
    assert df["cumulative_exposure_share"].iloc[-1] == pytest.approx(1.0)
    assert df["running_claims"].iloc[-1] == df["claims"].sum()


def test_data_quality_finds_the_planted_bad_rows(results):
    checks = results["09_data_quality_checks"].set_index("check_name")["n_rows"]
    assert checks["total_rows"] == len(clean.load_raw(FIXTURE_CSV))
    assert checks["duplicate_insured_year_rows"] == BAD_ROWS["duplicate_insured_year"]
    assert checks["zero_exposure"] == BAD_ROWS["zero_exposure"]
    assert checks["licence_age_under_16"] == BAD_ROWS["licence_age_under_16"]
    assert checks["null_fuel_type"] == BAD_ROWS["missing_fuel_type"]
    assert checks["null_vehicle_value"] == BAD_ROWS["missing_vehicle_value"]
    assert checks["null_age_driving_licence"] == BAD_ROWS["missing_age_driving_licence"]
    assert checks["null_vehicle_age"] == BAD_ROWS["missing_vehicle_age"]


def test_retention(results):
    row = results["10_retention"].iloc[0]
    raw = clean.load_raw(FIXTURE_CSV)
    ids = {y: set(raw.loc[raw["year"] == y, "insured_id"]) for y in (2022, 2023, 2024)}
    assert row["cohort_2022"] == len(ids[2022])
    assert row["renewed_2023"] == len(ids[2022] & ids[2023])
    assert row["renewed_both"] == len(ids[2022] & ids[2023] & ids[2024])
    assert row["renewed_both"] <= min(row["renewed_2023"], row["present_2024"])


def test_synthetic_results_never_go_to_sql_results(db_path, monkeypatch, tmp_path):
    monkeypatch.setattr(run_all_module, "SYNTHETIC_RESULTS_DIR", tmp_path / "synthetic")
    monkeypatch.setattr(run_all_module, "RESULTS_DIR", tmp_path / "real")
    run_all_module.run_all(db_path)  # no out_dir: the default is chosen from load_info
    assert len(list((tmp_path / "synthetic").glob("*.csv"))) == 10
    assert not (tmp_path / "real").exists()
