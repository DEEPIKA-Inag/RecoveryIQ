"""
routers/simulate.py
POST /simulate -- generates a batch of synthetic failed payments, runs BOTH
strategies against the same batch, and returns a side-by-side comparison.

BASELINE strategy: "contact everyone" via a single default active channel
  (config.BASELINE_DEFAULT_ACTION), regardless of economics. Even the naive
  baseline respects hard legal/compliance stops (opt-out, fraud-flag) -- no
  real system would ignore those. It deliberately does NOT respect quiet
  hours or the contact-attempt cap, which is exactly the "dumb" behavior
  Recovery IQ's guardrails improve on.

RECOVERY IQ strategy: runs the full agent (detect -> determine -> execute,
  built on LangGraph -- see app/agent/graph.py) and picks whichever option
  -- including WAIT/DO_NOTHING -- maximizes expected net value.

Both strategies are compared using EXPECTED VALUE math (not random simulated
outcomes) so the demo numbers are fully reproducible and fully auditable --
every number traces back to a probability the model produced and the cost
config in config.py. Nothing here is hardcoded; all totals are computed live
from the freshly generated batch.
"""

import random
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from .. import models, schemas
from ..database import get_db
from ..decision_engine.engine import evaluate_transaction
from ..agent.graph import run_agent
from ..ml.predictor import predict_probability
from ..config import INTERVENTION_CONFIG, ACTIVE_ACTIONS, BASELINE_DEFAULT_ACTION
from .helpers import get_or_create_customer, transaction_to_engine_input, customer_to_engine_input

router = APIRouter(tags=["simulate"])

FAILURE_REASONS = ["insufficient_funds", "timeout", "card_declined", "network_error", "bank_server_down"]
PAYMENT_CHANNELS = ["upi", "card", "netbanking", "wallet"]


def _random_amount():
    tier = random.choices(["small", "medium", "large"], weights=[0.4, 0.4, 0.2])[0]
    if tier == "small":
        return round(random.uniform(200, 1500), 2)
    if tier == "medium":
        return round(random.uniform(1500, 8000), 2)
    return round(random.uniform(8000, 40000), 2)


def _next_synthetic_customer_id(db: Session) -> int:
    max_id = db.query(func.max(models.Customer.id)).scalar() or 0
    return max_id + 1


@router.post("/simulate", response_model=schemas.SimulateResult)
def simulate(payload: schemas.SimulateRequest, db: Session = Depends(get_db)):
    batch_size = max(1, payload.batch_size)

    baseline_revenue = 0.0
    baseline_cost = 0.0
    baseline_impact_cost = 0.0
    baseline_contacts = 0

    iq_revenue = 0.0
    iq_cost = 0.0
    iq_impact_cost = 0.0
    iq_contacts = 0

    next_customer_id = _next_synthetic_customer_id(db)

    for i in range(batch_size):
        customer_id = next_customer_id + i
        customer = get_or_create_customer(db, customer_id)

        transaction = models.Transaction(
            customer_id=customer_id,
            amount=_random_amount(),
            failure_reason=random.choice(FAILURE_REASONS),
            payment_channel=random.choice(PAYMENT_CHANNELS),
            days_since_failure=round(random.uniform(0, 6), 1),
        )
        db.add(transaction)
        db.commit()
        db.refresh(transaction)

        txn_input = transaction_to_engine_input(transaction)
        cust_input = customer_to_engine_input(customer)

        # ---------- BASELINE: always contact via the default channel ----------
        # Even the naive baseline respects hard legal/compliance stops (opt-out,
        # fraud-flag) -- no real system would ignore those. It deliberately does
        # NOT respect quiet hours or the contact-attempt cap, which is exactly
        # the "dumb" behavior Recovery IQ's guardrails improve on.
        baseline_hard_blocked = cust_input["is_opted_out"] or cust_input["is_fraud_flagged"]

        if baseline_hard_blocked:
            baseline_probability = predict_probability(txn_input, cust_input, "none")
            b_expected_recovery = transaction.amount * baseline_probability
            b_cost = 0.0
            b_impact_cost = 0.0
            baseline_contacted = False
        else:
            baseline_action = BASELINE_DEFAULT_ACTION
            baseline_probability = predict_probability(txn_input, cust_input, baseline_action)
            cfg = INTERVENTION_CONFIG[baseline_action]
            b_expected_recovery = transaction.amount * baseline_probability
            b_cost = cfg["base_cost"]
            b_impact_cost = cfg["annoyance_weight"] * transaction.amount * (1 - baseline_probability)
            baseline_contacted = True

        baseline_revenue += b_expected_recovery
        baseline_cost += b_cost
        baseline_impact_cost += b_impact_cost
        if baseline_contacted:
            baseline_contacts += 1

        db.add(models.Outcome(
            transaction_id=transaction.id,
            recovered=baseline_probability >= 0.5,
            amount_recovered=round(b_expected_recovery, 2),
            contacted=baseline_contacted,
            churn_or_annoyance_flag=b_impact_cost > 0,
            strategy_label="baseline",
        ))

        # ---------- RECOVERY IQ: full agent (detect -> determine -> execute) ----------
        agent_state = run_agent(
            transaction=txn_input,
            customer=cust_input,
            customer_name=customer.name,
            payment_channel=transaction.payment_channel,
        )
        result = agent_state["result"]
        execution = agent_state["execution"]

        # persist the real decision, same as /analyze does
        for option in result["all_options"]:
            db.add(models.Prediction(
                transaction_id=transaction.id,
                intervention_name=option["action"],
                recovery_probability=option["recovery_probability"],
            ))
        db.add(models.Decision(
            transaction_id=transaction.id,
            selected_action=result["recommended_action"],
            recovery_probability=result["recovery_probability"],
            expected_recovery=result["expected_recovery"],
            intervention_cost=result["intervention_cost"],
            expected_customer_impact_cost=result["expected_customer_impact_cost"],
            expected_net_value=result["expected_net_value"],
            reason=result["reason"],
            all_options_json=result["all_options_json"],
        ))
        db.add(models.AuditLog(
            transaction_id=transaction.id,
            event_type="decision_made",
            detail=f"[simulate] Selected '{result['recommended_action']}' with net value {result['expected_net_value']}",
        ))

        # EXECUTE step's own distinct, timestamped audit event -- produced
        # by the agent's execute node, separate from the decision event.
        db.add(models.AuditLog(
            transaction_id=transaction.id,
            event_type="action_executed",
            detail=execution["detail"],
        ))

        iq_revenue += result["expected_recovery"]
        iq_cost += result["intervention_cost"]
        iq_impact_cost += result["expected_customer_impact_cost"]
        if result["recommended_action"] in ACTIVE_ACTIONS:
            iq_contacts += 1

        db.add(models.Outcome(
            transaction_id=transaction.id,
            recovered=result["recovery_probability"] >= 0.5,
            amount_recovered=result["expected_recovery"],
            contacted=result["recommended_action"] in ACTIVE_ACTIONS,
            churn_or_annoyance_flag=result["expected_customer_impact_cost"] > 0,
            strategy_label="recovery_iq",
        ))

        db.commit()

    baseline_net_value = baseline_revenue - baseline_cost - baseline_impact_cost
    iq_net_value = iq_revenue - iq_cost - iq_impact_cost

    baseline_result = schemas.StrategyResult(
        strategy="baseline",
        payments=batch_size,
        revenue_recovered=round(baseline_revenue, 2),
        intervention_cost=round(baseline_cost, 2),
        contacts_made=baseline_contacts,
        expected_churn_annoyance=round(baseline_impact_cost, 2),
        net_value=round(baseline_net_value, 2),
    )
    iq_result = schemas.StrategyResult(
        strategy="recovery_iq",
        payments=batch_size,
        revenue_recovered=round(iq_revenue, 2),
        intervention_cost=round(iq_cost, 2),
        contacts_made=iq_contacts,
        expected_churn_annoyance=round(iq_impact_cost, 2),
        net_value=round(iq_net_value, 2),
    )

    net_value_lift = round(iq_net_value - baseline_net_value, 2)
    contacts_avoided_pct = round(
        ((baseline_contacts - iq_contacts) / baseline_contacts * 100) if baseline_contacts else 0.0, 2
    )
    intervention_cost_saved = round(baseline_cost - iq_cost, 2)

    return schemas.SimulateResult(
        baseline=baseline_result,
        recovery_iq=iq_result,
        net_value_lift=net_value_lift,
        contacts_avoided_pct=contacts_avoided_pct,
        intervention_cost_saved=intervention_cost_saved,
    )