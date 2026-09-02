"""
predictor.py

Loads the trained model once at import time and exposes a single function:
    predict_probability(transaction_dict, customer_dict, intervention_name) -> float

This is the ONLY function the decision engine calls into the ML layer.
It builds a one-row feature frame using the EXACT same transformation as
train_model.build_features(), using the saved feature_columns.json to
guarantee column order matches what the model was trained on.
"""

import os
import json
import pandas as pd
import joblib

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_MODEL_PATH = os.path.join(_THIS_DIR, "model.joblib")
_FEATURES_PATH = os.path.join(_THIS_DIR, "feature_columns.json")

_FAILURE_REASONS = ["insufficient_funds", "timeout", "card_declined", "network_error", "bank_server_down"]
_INTERVENTIONS = ["retry", "whatsapp", "email", "voice", "discount", "human_followup", "none"]

_model = None
_feature_columns = None


def _load():
    global _model, _feature_columns
    if _model is None:
        if not os.path.exists(_MODEL_PATH):
            raise FileNotFoundError(
                f"Model not found at {_MODEL_PATH}. Run `python -m app.ml.train_model` first."
            )
        _model = joblib.load(_MODEL_PATH)
        with open(_FEATURES_PATH) as f:
            _feature_columns = json.load(f)
    return _model, _feature_columns


def _build_single_row(transaction: dict, customer: dict, intervention_name: str) -> pd.DataFrame:
    """
    transaction: dict with keys amount, failure_reason, days_since_failure
    customer: dict with keys total_past_payments, total_past_failures,
              past_self_cure_count, past_recovery_attempts, past_opt_outs,
              past_whatsapp_success, past_whatsapp_attempts,
              past_email_success, past_email_attempts,
              past_call_success, past_call_attempts
    intervention_name: one of _INTERVENTIONS ("none" = do_nothing/wait case)
    """
    row = {}
    row["amount"] = transaction["amount"]
    row["days_since_failure"] = transaction["days_since_failure"]
    row["total_past_payments"] = customer["total_past_payments"]
    row["total_past_failures"] = customer["total_past_failures"]
    row["past_self_cure_count"] = customer["past_self_cure_count"]
    row["past_recovery_attempts"] = customer["past_recovery_attempts"]
    row["past_opt_outs"] = customer["past_opt_outs"]

    row["whatsapp_success_rate"] = customer["past_whatsapp_success"] / max(1, customer["past_whatsapp_attempts"])
    row["email_success_rate"] = customer["past_email_success"] / max(1, customer["past_email_attempts"])
    row["call_success_rate"] = customer["past_call_success"] / max(1, customer["past_call_attempts"])
    row["self_cure_rate"] = customer["past_self_cure_count"] / max(1, customer["total_past_failures"])

    for reason in _FAILURE_REASONS:
        row[f"reason_{reason}"] = 1 if transaction["failure_reason"] == reason else 0

    for interv in _INTERVENTIONS:
        row[f"interv_{interv}"] = 1 if intervention_name == interv else 0

    return pd.DataFrame([row])


def predict_probability(transaction: dict, customer: dict, intervention_name: str) -> float:
    """
    Returns P(recovered=1) for this transaction if `intervention_name` is used.
    intervention_name="none" means "no active contact" -- used for the WAIT/DO_NOTHING case.
    """
    model, feature_columns = _load()
    row_df = _build_single_row(transaction, customer, intervention_name)

    # reorder/align columns to exactly match training schema; fill any
    # unexpected gaps with 0 (shouldn't happen if schemas stay in sync)
    row_df = row_df.reindex(columns=feature_columns, fill_value=0)

    proba = model.predict_proba(row_df)[0][1]
    return float(proba)