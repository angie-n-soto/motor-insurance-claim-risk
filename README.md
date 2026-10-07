# Motor Insurance Claim Risk

Predicts the probability that a motor insurance policy has at least one claim in a year, with per-prediction explanations (SHAP), served through a FastAPI app in Docker.

**🔗 Live demo: https://motor-insurance-claim-risk.onrender.com** (API docs at [/docs](https://motor-insurance-claim-risk.onrender.com/docs)). Free hosting: the first load after 15 idle minutes takes about a minute to wake up.

Full results: [reports/RESULTS.md](reports/RESULTS.md) · Plan and decisions: [PROJECT_PLAN.md](PROJECT_PLAN.md)

**Headline (test year 2024, unseen):** the riskiest 10% of policies claimed 33.9% of the time vs 2.4% for the safest 10%. PR-AUC 0.281 vs 0.264 for ranking by the insurer's own premium; well calibrated (15.1% predicted vs 15.1% actual).

## Data
Mendeley Data: *Dataset of motor insurance portfolio*, https://data.mendeley.com/datasets/sw4jmdb2sm/1 (license: TBD, check the dataset page).
Not committed to the repo. Download it and save it as `data/raw/motor_portfolio.csv`.

## Setup
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```
