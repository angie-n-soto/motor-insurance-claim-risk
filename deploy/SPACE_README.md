---
title: Motor Insurance Claim Risk
emoji: 🚗
colorFrom: blue
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: Claim probability for a motor policy, with SHAP reasons
---

# Motor Insurance Claim Risk

Estimates the probability that a motor insurance policy has at least one claim over the next year, and shows the top reasons behind each score.

- **Model:** XGBoost, trained on 186k Spanish policy-years from 2022–23 and tested on 168k from 2024.
- **Results:** the riskiest 10% of 2024 policies claimed 33.9% of the time vs 2.4% for the safest 10%.
- **Try it:** use the form on the home page, or the interactive API at `/docs`.

Source code, methodology and limitations: https://github.com/angie-n-soto/motor-insurance-claim-risk
