"""
engine.py

The economic decision engine. Pure Python arithmetic -- no ML model calls
happen inside this file. It receives probabilities (already computed by
predictor.py) and applies the EV formula from the spec:

    expected_recovery_value = amount * probability_of_recovery
    expected_net_value = expected_recovery_value
                          - intervention_cost
                          - expected_customer_impact_cost

expected_customer_impact_cost = annoyance_weight * amount * (1 - probability)
  -- i.e. the "cost" of annoying a customer is weighted by how likely the
  contact was to fail anyway (a failed, unwanted contact is the worst outcome).

WAIT and DO_NOTHING are always included as candidate options:
  - WAIT: uses the model's "no active contact" (intervention_name="none")
    self-cure probability, discounted slightly for time value, cost = 0.
  - DO_NOTHING: a hard floor option -- permanently stop pursuing this
    transaction. Expected recovery = 0, cost = 0, impact cost = 0, net = 0.
    This exists so the engine never has to pick a genuinely money-losing
    active intervention just because it's the "least bad" -- DO_NOTHING at
    net value 0 will always beat a negative-EV active intervention.

This separation (ML predicts probabilities only, engine does the money math)
is deliberate and is the answer to "how do we trust this with real money":
the arithmetic is fully auditable and doesn't depend on an LLM or black box.

GUARDRAILS: two-tier compliance filtering runs before any active option is
scored. hard_block_reasons() blocks EVERY active action including retry
(fraud only). contact_block_reasons() blocks only customer-facing actions
(opt-out, quiet hours, contact cap) -- retry is a silent backend charge
attempt with no customer-facing message, so it stays allowed even when
contact is blocked.
"""

import json
from ..config import INTERVENTION_CONFIG, ACTIVE_ACTIONS, CUSTOMER_FACING_ACTIONS, WAIT_SELF_CURE_DISCOUNT
from ..ml.predictor import predict_probability
from .guardrails import hard_block_reasons as _hard_block_reasons
from .guardrails import contact_block_reasons as _contact_block_reasons


def _reason_for(action: str, probability: float, net_value: float, is_best: bool) -> str:
    if action == "do_nothing":
        return "No option had a positive expected net value; permanently stopping pursuit avoids further cost."
    if action == "wait":
        return (
            f"Customer has a {probability:.0%} probability of self-curing without any contact; "
            f"waiting captures most of the value at zero cost and zero annoyance risk."
        )
    if probability >= 0.7:
        return f"High historical recovery rate ({probability:.0%}) for this channel at relatively low cost."
    if probability >= 0.4:
        return f"Moderate recovery rate ({probability:.0%}); still the best available economic trade-off."
    return f"Recovery rate is low ({probability:.0%}), but still nets more value than the alternatives."


def evaluate_transaction(transaction: dict, customer: dict, now=None) -> dict:
    """
    transaction: dict with amount, failure_reason, days_since_failure
    customer: dict with the customer history fields predictor.py expects,
              plus is_opted_out / is_fraud_flagged for guardrails
    now: optional datetime override, used for testing quiet-hours logic

    Returns a dict matching the AnalyzeResult shape:
        transaction_id (caller fills in), amount, recommended_action,
        recovery_probability, expected_recovery, intervention_cost,
        expected_customer_impact_cost, expected_net_value, reason,
        all_options (list of every option considered, for the audit trail)
    """
    amount = transaction["amount"]
    options = []

    # --- Guardrails, checked BEFORE any active channel is scored ---
    # hard_blocks: block EVERY active action, including retry (fraud only).
    # contact_blocks: block only customer-facing actions (opt-out, quiet
    # hours, contact cap) -- retry stays allowed since it never contacts
    # the customer, it's a silent backend charge attempt.
    hard_blocks = _hard_block_reasons(customer)
    contact_blocks = _contact_block_reasons(customer, now)
    all_blocks = hard_blocks + contact_blocks

    # --- Active interventions ---
    if not hard_blocks:
        for action in ACTIVE_ACTIONS:
            if action in CUSTOMER_FACING_ACTIONS and contact_blocks:
                continue  # this specific action is customer-facing and contact is blocked

            probability = predict_probability(transaction, customer, action)
            cfg = INTERVENTION_CONFIG[action]

            expected_recovery = amount * probability
            intervention_cost = cfg["base_cost"]
            expected_customer_impact_cost = cfg["annoyance_weight"] * amount * (1 - probability)
            expected_net_value = expected_recovery - intervention_cost - expected_customer_impact_cost

            options.append({
                "action": action,
                "recovery_probability": round(probability, 4),
                "expected_recovery": round(expected_recovery, 2),
                "intervention_cost": round(intervention_cost, 2),
                "expected_customer_impact_cost": round(expected_customer_impact_cost, 2),
                "expected_net_value": round(expected_net_value, 2),
            })

    # --- WAIT: self-cure probability, discounted, zero cost ---
    self_cure_probability = predict_probability(transaction, customer, "none")
    wait_expected_recovery = amount * self_cure_probability * WAIT_SELF_CURE_DISCOUNT
    options.append({
        "action": "wait",
        "recovery_probability": round(self_cure_probability, 4),
        "expected_recovery": round(wait_expected_recovery, 2),
        "intervention_cost": 0.0,
        "expected_customer_impact_cost": 0.0,
        "expected_net_value": round(wait_expected_recovery, 2),
    })

    # --- DO_NOTHING: hard floor at net value 0 ---
    options.append({
        "action": "do_nothing",
        "recovery_probability": 0.0,
        "expected_recovery": 0.0,
        "intervention_cost": 0.0,
        "expected_customer_impact_cost": 0.0,
        "expected_net_value": 0.0,
    })

    # --- Pick the winner ---
    best = max(options, key=lambda o: o["expected_net_value"])

    if all_blocks:
        reason = (
            "Active contact blocked (" + "; ".join(all_blocks) + "). "
            + _reason_for(best["action"], best["recovery_probability"], best["expected_net_value"], True)
        )
    else:
        reason = _reason_for(best["action"], best["recovery_probability"], best["expected_net_value"], True)

    return {
        "amount": amount,
        "recommended_action": best["action"],
        "recovery_probability": best["recovery_probability"],
        "expected_recovery": best["expected_recovery"],
        "intervention_cost": best["intervention_cost"],
        "expected_customer_impact_cost": best["expected_customer_impact_cost"],
        "expected_net_value": best["expected_net_value"],
        "reason": reason,
        "guardrails_blocked": all_blocks,
        "all_options": options,
        "all_options_json": json.dumps(options),
    }