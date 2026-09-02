"""
train_model.py

Trains an explainable ML model to predict recovery probability, given:
  - transaction features (amount, failure_reason, days_since_failure)
  - the intervention being considered (retry/whatsapp/email/voice/discount/human_followup/none)
  - customer historical behavior features

This is the ONLY place probabilities are learned. The decision engine
(Step 6) calls predictor.py, which loads this trained model -- it never
re-derives probabilities itself. The LLM (optional, later) never touches
these numbers either.

Model: RandomForestClassifier (explainable via feature_importances_,
handles mixed numeric/categorical features well without heavy preprocessing).

Run with (from backend/, venv active):
    python -m app.ml.train_model
"""

import os
import json
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, roc_auc_score, classification_report
import joblib

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_PATH = os.path.join(BASE_DIR, "data", "synthetic_transactions.csv")
MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model.joblib")
FEATURES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "feature_columns.json")

FAILURE_REASONS = ["insufficient_funds", "timeout", "card_declined", "network_error", "bank_server_down"]
INTERVENTIONS = ["retry", "whatsapp", "email", "voice", "discount", "human_followup", "none"]


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Turns the raw CSV into a numeric feature matrix.
    Categorical columns (failure_reason, intervention_used) are one-hot encoded.
    This function is reused at INFERENCE time by predictor.py, so the exact
    same transformation must be applied there.
    """
    features = pd.DataFrame()

    features["amount"] = df["amount"]
    features["days_since_failure"] = df["days_since_failure"]
    features["total_past_payments"] = df["total_past_payments"]
    features["total_past_failures"] = df["total_past_failures"]
    features["past_self_cure_count"] = df["past_self_cure_count"]
    features["past_recovery_attempts"] = df["past_recovery_attempts"]
    features["past_opt_outs"] = df["past_opt_outs"]

    # ratio features -- these carry more signal than raw counts
    features["whatsapp_success_rate"] = df["past_whatsapp_success"] / df["past_whatsapp_attempts"].clip(lower=1)
    features["email_success_rate"] = df["past_email_success"] / df["past_email_attempts"].clip(lower=1)
    features["call_success_rate"] = df["past_call_success"] / df["past_call_attempts"].clip(lower=1)
    features["self_cure_rate"] = df["past_self_cure_count"] / df["total_past_failures"].clip(lower=1)

    # one-hot encode failure_reason
    for reason in FAILURE_REASONS:
        features[f"reason_{reason}"] = (df["failure_reason"] == reason).astype(int)

    # one-hot encode intervention_used -- this is what lets the SAME model
    # answer "what if we used whatsapp" vs "what if we did nothing" for the
    # same transaction, by flipping this one-hot block at inference time.
    for interv in INTERVENTIONS:
        features[f"interv_{interv}"] = (df["intervention_used"] == interv).astype(int)

    return features


def train():
    df = pd.read_csv(DATA_PATH)

    X = build_features(df)
    y = df["recovered"].astype(int)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=8,
        min_samples_leaf=5,
        random_state=42,
        class_weight="balanced",
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    acc = accuracy_score(y_test, y_pred)
    auc = roc_auc_score(y_test, y_proba)

    print(f"Test accuracy: {acc:.3f}")
    print(f"Test ROC-AUC:  {auc:.3f}")
    print()
    print(classification_report(y_test, y_pred, target_names=["not_recovered", "recovered"]))

    print("Top 10 feature importances:")
    importances = sorted(
        zip(X.columns, model.feature_importances_), key=lambda x: -x[1]
    )
    for name, importance in importances[:10]:
        print(f"  {name:30s} {importance:.4f}")

    # Save model + the exact feature column order it expects at inference time
    joblib.dump(model, MODEL_PATH)
    with open(FEATURES_PATH, "w") as f:
        json.dump(list(X.columns), f, indent=2)

    print()
    print(f"Model saved to:   {MODEL_PATH}")
    print(f"Features saved to: {FEATURES_PATH}")


if __name__ == "__main__":
    train()