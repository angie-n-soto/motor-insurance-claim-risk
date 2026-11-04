"""Tests for the FastAPI service, using the committed models/claim_model.joblib."""

import pytest
from fastapi.testclient import TestClient

from src import clean
from src.api import BUNDLE, app

client = TestClient(app)

SAMPLE_POLICY = {
    "policy_type": "COMP_N",
    "business_type": "P",
    "payment_frequency": "Q",
    "bonus_score": "N",
    "fuel_type": None,
    "vehicle_brand": "seat",
    "municipality_type": "C",
    "circulation_area": "U",
    "prev_year_claim": "yes",
    "driver_age": 23,
    "licence_age": 18,
    "vehicle_value": 15000,
    "seats": 5,
    "power_to_weight_ratio": 10.5,
}


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "model": BUNDLE["model_name"]}


def test_model_expects_the_features_clean_py_builds():
    # If src/clean.py and the saved model drift apart, serving breaks silently.
    assert BUNDLE["features"] == clean.FEATURES


@pytest.mark.parametrize("payload", [{}, SAMPLE_POLICY], ids=["defaults", "sample_policy"])
def test_predict_returns_probability_and_reasons(payload):
    response = client.post("/predict", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert 0.0 <= body["claim_probability"] <= 1.0
    assert 0.0 < body["average_probability"] < 1.0
    assert body["risk_level"] in {"low", "average", "high"}
    assert len(body["top_reasons"]) > 0
    for reason in body["top_reasons"]:
        assert reason["effect"] in {"raises risk", "lowers risk"}
        # Exposure is fixed at a full year, so it is never given as a reason.
        assert reason["feature"] != "total_exposure"


def test_riskier_profile_scores_higher_than_safer_one():
    safe = {"policy_type": "TP", "prev_year_claim": "no_history", "driver_age": 55, "licence_age": 20}
    risky = {"policy_type": "COMP_N", "prev_year_claim": "yes", "driver_age": 22, "licence_age": 18}
    p_safe = client.post("/predict", json=safe).json()["claim_probability"]
    p_risky = client.post("/predict", json=risky).json()["claim_probability"]
    assert p_risky > p_safe


def test_unknown_brand_is_accepted_as_other():
    response = client.post("/predict", json={"vehicle_brand": "NOT_A_REAL_BRAND"})
    assert response.status_code == 200


@pytest.mark.parametrize(
    "bad",
    [
        {"licence_age": 50, "driver_age": 30},  # licensed after current age
        {"driver_age": 17},  # below the training range
        {"policy_type": "XYZ"},  # unknown code
    ],
)
def test_invalid_input_is_rejected(bad):
    assert client.post("/predict", json=bad).status_code == 422


def test_form_page():
    response = client.get("/")
    assert response.status_code == 200
    assert "<html" in response.text.lower()
