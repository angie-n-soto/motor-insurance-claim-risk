"""Score the 2024 test year with the committed model and save a `scores` table.

Run from the repo root, after python -m sql.load:
    python -m sql.export_scores

Query 07 (decile lift) reads this table. The test set is rebuilt with
src/clean.py from the same CSV that load.py loaded (recorded in the
load_info table), so the scores are exactly the ones src/train.py evaluated.
"""

import argparse
from pathlib import Path

import duckdb
import pandas as pd

from src.clean import TARGET, TEST_YEAR, build_modelling_table, load_raw
from src.explain import load_model

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "claims.duckdb"


def score_test_year(csv_path: Path) -> pd.DataFrame:
    _, test = build_modelling_table(load_raw(Path(csv_path)))
    bundle = load_model()
    probability = bundle["pipeline"].predict_proba(test[bundle["features"]])[:, 1]
    return pd.DataFrame(
        {
            "insured_id": test["insured_id"],
            "year": test["year"],
            "predicted_probability": probability,
            "has_claim": test[TARGET],
            "total_exposure": test["total_exposure"],
            "total_premium": test["total_premium"],
        }
    )


def export_scores(db_path: Path = DEFAULT_DB, csv_path: Path | None = None) -> int:
    con = duckdb.connect(str(db_path))
    try:
        if csv_path is None:
            csv_path = Path(con.execute("SELECT source_csv FROM load_info").fetchone()[0])
        scores = score_test_year(csv_path)
        con.register("scores_df", scores)
        con.execute("CREATE OR REPLACE TABLE scores AS SELECT * FROM scores_df")
        con.unregister("scores_df")
        return len(scores)
    finally:
        con.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--csv", type=Path, default=None, help="default: the CSV load.py used")
    args = parser.parse_args()
    n = export_scores(args.db, args.csv)
    print(f"Wrote {n:,} scored {TEST_YEAR} policies to `scores` in {args.db}")


if __name__ == "__main__":
    main()
