"""
routers/analyze.py
POST /analyze/{transaction_id}   -- run the agent (detect->determine->execute), persist everything, return the result
GET  /recovery-options/{transaction_id} -- return all ranked options without persisting a new decision
"""

import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from .. import models, schemas
from ..database import get_db
from ..decision_engine.engine import evaluate_transaction
from ..agent.graph import run_agent
from ..explain.explainer import generate_llm_explanation
from .helpers import transaction_to_engine_input, customer_to_engine_input

router = APIRouter(tags=["analyze"])


def _get_transaction_and_customer(db: Session, transaction_id: int):
    transaction = db.query(models.Transaction).filter(models.Transaction.id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail=f"Transaction {transaction_id} not found")
    customer = db.query(models.Customer).filter(models.Customer.id == transaction.customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail=f"Customer {transaction.customer_id} not found")
    return transaction, customer


@router.post("/analyze/{transaction_id}", response_model=schemas.AnalyzeResult)
def analyze_transaction(transaction_id: int, db: Session = Depends(get_db)):
    transaction, customer = _get_transaction_and_customer(db, transaction_id)

    txn_input = transaction_to_engine_input(transaction)
    cust_input = customer_to_engine_input(customer)

    # Run the full detect -> determine -> execute agent (LangGraph). This
    # replaces separate calls to evaluate_transaction()/execute_action() --
    # the underlying logic in engine.py/guardrails.py/executor.py is
    # unchanged, only the orchestration is now graph-based.
    agent_state = run_agent(
        transaction=txn_input,
        customer=cust_input,
        customer_name=customer.name,
        payment_channel=transaction.payment_channel,
    )
    result = agent_state["result"]
    execution = agent_state["execution"]

    # Try an LLM-generated explanation; falls back to the rule-based reason
    # from the decision engine if the LLM is unavailable or fails. The LLM
    # only narrates numbers that are ALREADY final -- it cannot change them.
    llm_reason = generate_llm_explanation({
        "action": result["recommended_action"],
        "probability": result["recovery_probability"],
        "amount": result["amount"],
        "expected_recovery": result["expected_recovery"],
        "intervention_cost": result["intervention_cost"],
        "expected_customer_impact_cost": result["expected_customer_impact_cost"],
        "net_value": result["expected_net_value"],
        "failure_reason": transaction.failure_reason,
    })
    explanation_source = "llm" if llm_reason else "rule_based"
    final_reason = llm_reason or result["reason"]

    # persist a Prediction row per option considered (audit trail of raw ML outputs)
    for option in result["all_options"]:
        db.add(models.Prediction(
            transaction_id=transaction_id,
            intervention_name=option["action"],
            recovery_probability=option["recovery_probability"],
        ))

    # persist the Decision row
    decision = models.Decision(
        transaction_id=transaction_id,
        selected_action=result["recommended_action"],
        recovery_probability=result["recovery_probability"],
        expected_recovery=result["expected_recovery"],
        intervention_cost=result["intervention_cost"],
        expected_customer_impact_cost=result["expected_customer_impact_cost"],
        expected_net_value=result["expected_net_value"],
        reason=final_reason,
        explanation_source=explanation_source,
        all_options_json=result["all_options_json"],
    )
    db.add(decision)

    db.add(models.AuditLog(
        transaction_id=transaction_id,
        event_type="decision_made",
        detail=(
            f"Selected '{result['recommended_action']}' with net value "
            f"{result['expected_net_value']} (explanation source: {explanation_source})"
        ),
    ))

    # EXECUTE step's own distinct, timestamped audit event -- produced by
    # the agent's execute node, separate from the decision event above.
    db.add(models.AuditLog(
        transaction_id=transaction_id,
        event_type="action_executed",
        detail=execution["detail"],
    ))

    db.commit()

    return schemas.AnalyzeResult(
        transaction_id=transaction_id,
        amount=result["amount"],
        recommended_action=result["recommended_action"],
        recovery_probability=result["recovery_probability"],
        expected_recovery=result["expected_recovery"],
        intervention_cost=result["intervention_cost"],
        expected_customer_impact_cost=result["expected_customer_impact_cost"],
        expected_net_value=result["expected_net_value"],
        reason=final_reason,
        all_options=[schemas.OptionResult(**o) for o in result["all_options"]],
    )


@router.get("/recovery-options/{transaction_id}", response_model=List[schemas.OptionResult])
def recovery_options(transaction_id: int, db: Session = Depends(get_db)):
    transaction, customer = _get_transaction_and_customer(db, transaction_id)

    txn_input = transaction_to_engine_input(transaction)
    cust_input = customer_to_engine_input(customer)
    result = evaluate_transaction(txn_input, cust_input)

    ranked = sorted(result["all_options"], key=lambda o: -o["expected_net_value"])
    return [schemas.OptionResult(**o) for o in ranked]