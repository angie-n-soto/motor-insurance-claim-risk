# Motor Insurance Claim Risk

Predicts the probability that a motor insurance policy has at least one claim in a year, with per-prediction explanations (SHAP), served through a FastAPI app in Docker.

> 🚧 Work in progress. See [PROJECT_PLAN.md](PROJECT_PLAN.md).

## Data
Mendeley Data: *Dataset of motor insurance portfolio*, https://data.mendeley.com/datasets/sw4jmdb2sm/1 (license: TBD, check the dataset page).
Not committed to the repo. Download it and save it as `data/raw/motor_portfolio.csv`.

## Setup
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```
