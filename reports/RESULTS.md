# Results log

What the pipeline found, and why each number matters. Regenerate everything with:

```bash
python -m src.clean
python -m src.train
python -m src.explain
```

Raw numbers live in [metrics.json](metrics.json); plots in [figures/](figures/).

---

## 1. Data after cleaning (`src/clean.py`)

| Split | Years | Rows | Claim rate |
|---|---|---|---|
| Train | 2022–2023 | 186,006 | 13.6% |
| Test | 2024 | 168,085 | 15.1% |

- Raw data is 354,140 rows. Exactly 49 rows (those with zero exposure) were dropped; nothing else was lost.
- The claim rate by prior-year history matches the EDA:

| `prev_year_claim` | Train | Test |
|---|---|---|
| yes | 24.5% | 25.5% |
| no | 17.4% | 17.3% |
| no_history | 11.2% | 9.5% |

**Limitation:** every 2022 row is `no_history` because the dataset starts in 2022, not because those insureds are new. In train that category mixes new customers with renewals; in 2024 it means genuinely new customers.

## 2. Model performance (`src/train.py`)

**Model selection.** 5-fold `GroupKFold` by insured on 2022–23, scored by PR-AUC:
- XGBoost: 0.253 ± 0.007
- Logistic regression: 0.248 ± 0.004

XGBoost was selected. The 2024 test set was not used to choose the model.

**Test year 2024 (scored once):**

| Model | PR-AUC | ROC-AUC | Top-decile lift | Top vs bottom decile | Brier |
|---|---|---|---|---|---|
| Base rate (13.6% for all) | 0.151 | 0.500 | — | — | 0.129 |
| Insurer's earned premium | 0.264 | 0.678 | 2.11× | 13.7× | — |
| Logistic regression | 0.269 | 0.679 | 2.16× | 11.4× | 0.122 |
| **XGBoost (deployed)** | **0.281** | **0.686** | **2.24×** | **13.9×** | **0.121** |

**Decile lift** ([decile_lift.png](figures/decile_lift.png)): the riskiest 10% of 2024 policies claimed **33.9%** of the time and the safest 10% claimed **2.4%**. The model never saw 2024 data.

**Calibration** ([calibration.png](figures/calibration.png)): mean predicted 15.1% vs actual 15.1% on 2024. The claim rate rose from 13.6% in train, but the predictions still track it. A likely reason: 2024 has proportionally fewer `no_history` policies, and the model already knows they claim less.

**How to read it**
- A ROC-AUC around 0.69 is typical for claim occurrence, because whether a claim happens is partly luck.
- The model ranks risk slightly better than the insurer's premium. But premiums price claim *cost*, not occurrence, and include business constraints. So this isn't "beating the actuaries". It suggests prior-year claim history may be underused in pricing.
- Not tuned. XGBoost uses fixed conservative settings (500 trees, learning rate 0.05, depth 5, 0.8 subsampling).

## 3. Explainability (`src/explain.py`)

SHAP values are summed back from one-hot columns to the original features. A per-row check confirms they add up exactly to the model's prediction (max error 4e-7).

**Global importance** (mean |SHAP|, log-odds; [shap_importance.png](figures/shap_importance.png)):

| Feature | Importance | Feature | Importance |
|---|---|---|---|
| total_exposure | 0.496 | fuel_type | 0.063 |
| policy_type | 0.232 | circulation_area | 0.045 |
| prev_year_claim | 0.119 | driver_age | 0.045 |
| payment_frequency | 0.083 | vehicle_brand | 0.037 |
| vehicle_value | 0.069 | bonus_score | 0.017 |
| years_licensed | 0.065 | business_type | 0.007 |

**Sanity check against insurance intuition** ([shap_effects.png](figures/shap_effects.png)):

- **Exposure:** less time insured means less risk (−1.37 log-odds for under 0.41 years). Expected.
- **Policy type reflects coverage breadth, not driver risk.** The target counts any claim, so wider coverage creates more ways to claim:
  - TP (liability only): −0.82
  - CC: −0.16
  - COMP_E (comprehensive with excess): +0.26
  - COMP_N (comprehensive, no excess): +0.85

  Comprehensive without an excess vs with one is moral hazard: a deductible discourages small claims.
- **Prior-year claim:** yes +0.40, no +0.11, no_history −0.07. SHAP compares against the average policy, and that average includes many low-risk `no_history` rows. So "no" still sits above it.
- **Years licensed:** risk falls steadily with experience, from +0.10 at 16 years or less to −0.10 at 38 or more. Driver age alone is weak and noisy. The renamed column (it was mislabeled `vehicle_age`) is more useful than age.
- **Missing fuel type:** +0.18. This confirms the decision to keep "missing" as its own category.
- **Bonus score:** weak, because about 96% of policies have score G and `prev_year_claim` already carries claim history.

**For the API:** `top_reasons()` leaves out `total_exposure`. The API fixes exposure at a full year, so it would top every explanation without saying anything about the policy.
