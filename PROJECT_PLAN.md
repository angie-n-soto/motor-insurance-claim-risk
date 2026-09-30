# Motor Insurance Claim Risk — Project Plan

**Goal:** A deployed, explainable model that estimates the probability that a motor policy has at least one claim in a year. Served with FastAPI, containerized with Docker, with a live demo link.

**Dataset:** Mendeley "Dataset of motor insurance portfolio" (https://data.mendeley.com/datasets/sw4jmdb2sm/1). Spanish motor portfolio, 2022–2024, 354,140 policy-years × 47 columns, 185,678 unique insureds. Check the license on the Mendeley page and cite it in the README.

---

## Initial data profile findings

These findings come from a first profile of the data. Each one feeds into a design decision below. Anything marked *to verify* is confirmed or rejected in the EDA notebook before it changes the data.

| # | Finding | Evidence | What we do about it |
|---|---------|----------|---------------------|
| 1 | **`vehicle_age` may be mislabeled** (*to verify*). The data suggests it holds *years licensed* (driver_age − age when licensed), even though the data dictionary says "vehicle age". | Matches `driver_age − age_driving_licence` within ±1 year in 99.9% of rows; correlates 0.86 with driver age but only 0.06 with vehicle value; 15% of rows would be vehicles 40+ years old, with the same brand mix as the rest of the portfolio; all 392 drivers licensed this year have a `vehicle_age` of exactly 0. An alternative explanation (collectible or imported vehicles) is tested in EDA. | Raw data stays unchanged. If EDA confirms it, rename the column to `years_licensed` in the cleaning step and list "no true vehicle-age feature" as a limitation. |
| 2 | **`age_driving_licence` looks like the age when licensed, not the year** (the data dictionary says "year"). | Values are 0–80 with a median of 20, not years like 2004. | Verify in EDA. If confirmed, rename it to `licence_age`. Treat values < 16 (57 rows) as data errors → set to missing. |
| 3 | **20 columns are outcome information** (`*_claims`, `*_incurred`). | They are the claims themselves. | Drop them all from features. `total_claims` is used only to build the target. |
| 4 | **`policy_status` (Active/Cancelled) is recorded "at time of analysis".** | That is *after* the policy year. Cancelled policies have lower exposure. | Drop it: it's target leakage (information from the future). |
| 5 | **Exposure strongly drives the claim rate.** | Claim rate is 3.3% at ≤0.25 yr exposure vs 19.3% at a full year. 42% of rows cover less than a full year. | Use `total_exposure` as a feature (not a filter). The API fixes it at 1.0, meaning "probability of a claim over a full year". Drop the 49 rows with 0 exposure. |
| 6 | **Premiums are earned, pro-rated by exposure.** | `total_premium` correlates 0.60 with exposure. | Exclude premiums from model features. Use them for a benchmark instead: *does our model rank risk better than the insurer's own price?* |
| 7 | **Prior-year claims are highly predictive.** | Claim rate is 25.2% after a claim year, 17.4% after a clean year, and 10.7% with no history. | Engineer a lagged feature, `prev_year_claim` ∈ {yes, no, no_history}, built only from the *previous* row of the same insured. |
| 8 | Missing values are small. | `fuel_type` 1,287; `vehicle_value` 513; 2 each in two age columns. Missing `fuel_type` has a 21% claim rate vs 14% overall. | Categorical: add an explicit `"missing"` category (the missingness carries signal). Numeric: median impute inside the pipeline. |
| 9 | 8,543 policies have claims but €0 incurred. | Claims closed without payment. | Keep them as positives (a claim was *reported*). Document it. |
| 10 | Claim rate rises by year (13.0% → 14.0% → 15.1%). | | This is drift, and it's another reason to test on a later year (below). |

---

## Design decisions (and why)

**Target:** `has_claim = total_claims > 0` (14.3% positive). This is a binary classification problem, which is simpler than modelling claim frequency, but the exposure feature keeps it honest.

**Split: out-of-time instead of a random group split**
- **Test set = 2024** (168k rows). **Train = 2022–2023.**
- *Why:* In real life, an insurer trains on past years and predicts next year. A random split lets the model "see the future" and hides drift. The concern that the same person could appear in both train and test only matters when features leak identity or the future. The lag feature uses only prior-year information, so a returning customer appearing in 2024 is realistic, not leakage.
- **Hyperparameter tuning inside train:** `GroupKFold` by `insured_id`, so the same person's 2022 and 2023 rows are never split across CV folds.

**Imbalance:** No SMOTE and no heavy reweighting. 14% positives is only moderate imbalance, and the API returns a *probability*, which reweighting would distort. We'll check calibration instead.

**Metrics (headline → supporting):**
1. **PR-AUC**: ranking quality focused on the positive class.
2. **Decile lift chart**: "the top 10% riskiest policies have X× the claim rate of the bottom 10%". This is how insurers actually judge risk models.
3. **Calibration plot**: when the model says 20%, do 20% of those policies claim?
4. **Precision/recall at a chosen threshold**, framed as "flag for underwriting review".

**Features for the model (all known at policy start):**
`policy_type, business_type, payment_frequency, bonus_score, driver_age, vehicle_age / years_licensed, age_driving_licence / licence_age, fuel_type, vehicle_value, seats, power_to_weight_ratio, vehicle_brand (top ~15 + "other"), municipality_type, circulation_area, total_exposure, prev_year_claim`

---

## Tentative timeline

Roughly 1–2 weeks, working phase by phase. Durations are estimates.

| Phase | Est. time | Work | Concepts |
|-------|-----------|------|----------|
| 0. Setup | ✅ done | Dataset chosen, repo + environment set up | Reproducible environments |
| 1. EDA & cleaning | 1–2 days | EDA notebook: verify column meanings (incl. `vehicle_age`), leakage audit, exposure analysis, claim rate by feature. Write `src/clean.py`. | Verifying data dictionaries; leakage |
| 2. Features & split | 1 day | `prev_year_claim`, brand grouping, confirmed renames. Out-of-time split. sklearn `ColumnTransformer` pipeline. | Why preprocessing lives *inside* a pipeline (prevents leakage and makes serving identical to training) |
| 3. Modelling | 1–2 days | Baselines: (a) base rate, (b) premium-only, (c) logistic regression. Then XGBoost + GroupKFold tuning. | Baseline-first; regularization; boosting vs bagging |
| 4. Evaluation | 1 day | On 2024 data: PR-AUC, lift, calibration, threshold. Premium benchmark. Error analysis. | Why accuracy misleads; business framing of thresholds |
| 5. Explainability | 1 day | SHAP: global summary + 3 waterfall plots. Sanity-check against insurance intuition. Save model artifact. | Explainability; spotting a model that learned something wrong |
| 6. Deployment | 1–2 days | FastAPI (`/predict`, `/health`, and a simple HTML form at `/`). Dockerfile. Deploy to Hugging Face Spaces. | API design, Pydantic validation, containers |
| 7. Documentation | 1 day | README, model card, limitations, screenshots | Communicating ML work |

**If time runs short**, cut in this order: hyperparameter tuning (use defaults) → the premium benchmark → the HTML form (fall back to FastAPI's `/docs`). **Never cut:** the leakage audit, the out-of-time test, or deployment.

---

## Deployment plan

- **Local environment:** Python 3.14 in `.venv`, with versions pinned in `requirements.txt` (all ML libraries have 3.14 wheels, verified). The Docker image will use `python:3.14-slim` so the deployed app matches local training exactly.
- **Docker:** Hugging Face Spaces builds the Dockerfile in the cloud, so a local Docker install is useful for testing but not required.
- **Host:** Hugging Face Spaces (Docker SDK, free) gives a public, shareable link. Render's free tier is the backup (it sleeps after 15 minutes and cold-starts slowly).
- **Demo UX:** A one-page form where someone enters a driver age, policy type, etc. and gets back a *risk score, how it compares with the average, and the top 3 reasons*. `/docs` stays available for technical reviewers.

---

## Out of scope (future work, named in the README)
- Poisson frequency model with an exposure offset; Gamma severity model; pure premium
- Using the full multi-year history (only a 1-year lag is used here)
- Fairness review by age (age is a legal rating factor in Spain, but the model should still be discussed critically)
- A real vehicle-age feature, if EDA confirms finding #1
