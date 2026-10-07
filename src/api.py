"""FastAPI service for the claim-risk model.

Run locally from the repo root:
    uvicorn src.api:app --reload

Then open http://127.0.0.1:8000 (demo form) or /docs (interactive API docs).
"""

from pathlib import Path
from typing import Literal

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, model_validator

from src.explain import load_model, top_reasons

STATIC_DIR = Path(__file__).resolve().parent / "static"

# Loaded once at startup, not per request: unpickling the model is slow.
BUNDLE = load_model()
PIPELINE = BUNDLE["pipeline"]
AVERAGE_RATE = BUNDLE["full_year_claim_rate"]
KNOWN_BRANDS = set(
    PIPELINE.named_steps["prep"].named_transformers_["cat"].categories_[
        BUNDLE["features"].index("vehicle_brand")
    ]
)

# Human-readable labels so explanations read as sentences, not column names.
FEATURE_LABELS = {
    "policy_type": "Coverage type",
    "business_type": "Customer type",
    "payment_frequency": "Payment frequency",
    "bonus_score": "Bonus score",
    "fuel_type": "Fuel type",
    "vehicle_brand": "Vehicle brand",
    "municipality_type": "Area",
    "circulation_area": "Driving environment",
    "prev_year_claim": "Claim last year",
    "driver_age": "Driver age",
    "years_licensed": "Years licensed",
    "licence_age": "Age when licensed",
    "vehicle_value": "Vehicle value (€)",
    "seats": "Seats",
    "power_to_weight_ratio": "Weight-to-power ratio",
}
VALUE_LABELS = {
    "policy_type": {"TP": "third-party only", "TPG": "third-party + glass",
                    "CC": "third-party + extras", "COMP_E": "comprehensive with excess",
                    "COMP_N": "comprehensive, no excess"},
    "business_type": {"NB": "new business", "P": "existing portfolio"},
    "payment_frequency": {"A": "annual", "S": "semiannual", "Q": "quarterly"},
    "bonus_score": {"G": "good", "N": "neutral", "B": "bad"},
    "fuel_type": {"D": "diesel", "G": "gasoline", "missing": "not recorded"},
    "municipality_type": {"I": "inland", "C": "coastal", "IS": "islands"},
    "circulation_area": {"U": "urban", "R": "rural"},
    "prev_year_claim": {"yes": "yes", "no": "no", "no_history": "no history"},
}


class Policy(BaseModel):
    """One policy. Pydantic rejects invalid input with a clear 422 error
    before it ever reaches the model, so the model only sees values like
    the ones it was trained on."""

    # Literal = only these codes are accepted (the ones seen in training).
    policy_type: Literal["TP", "TPG", "CC", "COMP_E", "COMP_N"] = "CC"
    business_type: Literal["NB", "P"] = "NB"
    payment_frequency: Literal["A", "S", "Q"] = "A"
    bonus_score: Literal["G", "N", "B"] = "G"
    fuel_type: Literal["D", "G"] | None = Field("D", description="null if unknown")
    vehicle_brand: str = Field("VOLKSWAGEN", description="Brands outside the top 15 count as OTHER")
    municipality_type: Literal["I", "C", "IS"] = "I"
    circulation_area: Literal["U", "R"] = "U"
    prev_year_claim: Literal["yes", "no", "no_history"] = "no_history"
    # Bounds follow the training data (roughly its 0th-100th percentiles).
    # Outside them a tree model just extrapolates flat, so refuse instead.
    driver_age: int = Field(40, ge=18, le=90)
    licence_age: int = Field(19, ge=16, le=75, description="Age when the licence was obtained")
    vehicle_value: float | None = Field(25000, gt=0, le=400000, description="null if unknown")
    seats: int = Field(5, ge=2, le=9)
    power_to_weight_ratio: float = Field(12.0, ge=0, le=65, description="kg per horsepower")

    @model_validator(mode="after")
    def licence_before_age(self):
        if self.licence_age > self.driver_age:
            raise ValueError("licence_age cannot be greater than driver_age")
        return self

    def to_features(self) -> dict:
        row = self.model_dump()
        # Derived exactly as in the data (see EDA finding 1), so the user
        # can't enter an inconsistent age / licence / experience combination.
        row["years_licensed"] = self.driver_age - self.licence_age
        row["fuel_type"] = self.fuel_type or "missing"
        brand = self.vehicle_brand.strip().upper()
        row["vehicle_brand"] = brand if brand in KNOWN_BRANDS else "OTHER"
        # Fixed at a full year: the API answers "probability of a claim over
        # the next policy year", which is the question an underwriter asks.
        row["total_exposure"] = 1.0
        return row


class Reason(BaseModel):
    feature: str
    value: str
    effect: Literal["raises risk", "lowers risk"]
    shap_log_odds: float


class Prediction(BaseModel):
    claim_probability: float
    average_probability: float
    relative_risk: float
    risk_level: Literal["low", "average", "high"]
    top_reasons: list[Reason]


app = FastAPI(
    title="Motor Insurance Claim Risk",
    description="Probability that a motor policy has at least one claim over a full year, "
    "with the top reasons behind each score. XGBoost trained on 2022–23, tested on 2024.",
    version="1.0.0",
)


@app.get("/health")
def health() -> dict:
    # Hosting platforms ping this to check the container is alive.
    return {"status": "ok", "model": BUNDLE["model_name"]}


@app.post("/predict", response_model=Prediction)
def predict(policy: Policy) -> Prediction:
    row = policy.to_features()
    try:
        probability = float(PIPELINE.predict_proba(pd.DataFrame([row])[BUNDLE["features"]])[0, 1])
        reasons = top_reasons(row)
    except Exception as exc:  # never leak a stack trace to the client
        raise HTTPException(status_code=500, detail="Prediction failed") from exc

    relative = probability / AVERAGE_RATE
    level = "low" if relative < 0.8 else "high" if relative > 1.25 else "average"
    return Prediction(
        claim_probability=round(probability, 4),
        average_probability=round(AVERAGE_RATE, 4),
        relative_risk=round(relative, 2),
        risk_level=level,
        top_reasons=[
            Reason(
                feature=FEATURE_LABELS[r["feature"]],
                value=VALUE_LABELS.get(r["feature"], {}).get(r["value"], str(r["value"])),
                effect=r["effect"],
                shap_log_odds=r["shap_log_odds"],
            )
            for r in reasons
        ],
    )


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def form() -> str:
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")
