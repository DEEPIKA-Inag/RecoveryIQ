"""
routers/ask.py
POST /ask/{transaction_id} -- free-form Q&A about one transaction's decision.

Calls the LLM (with a bounded, smart retry for transient failures -- see
explain/explainer.py). If it's unavailable (no key, exhausted quota,
network issue, or the retry also failed), returns a graceful fallback
message using the decision's own stored reason -- never an error, never
a stuck spinner.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
import json

from .. import models
from ..database import get_db
from ..explain.explainer import answer_question

router = APIRouter(tags=["ask"])


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer: str
    source: str  # "llm" or "unavailable"


def _build_context(transaction: models.Transaction, customer: models.Customer, decision: models.Decision) -> str:
    all_options = json.loads(decision.all_options_json)
    options_text = "\n".join(
        f"  - {o['action']}: probability={o['recovery_probability']:.0%}, "
        f"expected_recovery=Rs{o['expected_recovery']:.0f}, cost=Rs{o['intervention_cost']:.0f}, "
        f"net_value=Rs{o['expected_net_value']:.0f}"
        for o in all_options
    )
    return (
        f"Transaction: Rs {transaction.amount:.0f}, failure reason: {transaction.failure_reason}, "
        f"payment channel: {transaction.payment_channel}, days since failure: {transaction.days_since_failure}\n"
        f"Customer: {customer.name}, segment: {customer.segment}, "
        f"past failures: {customer.total_past_failures}, past self-cures: {customer.past_self_cure_count}, "
        f"opted out: {customer.is_opted_out}, fraud flagged: {customer.is_fraud_flagged}\n"
        f"All options the engine scored:\n{options_text}\n"
        f"Chosen action: {decision.selected_action}, "
        f"final net value: Rs {decision.expected_net_value:.0f}\n"
        f"System's own reason: {decision.reason}"
    )


@router.post("/ask/{transaction_id}", response_model=AskResponse)
def ask_about_transaction(transaction_id: int, payload: AskRequest, db: Session = Depends(get_db)):
    transaction = db.query(models.Transaction).filter(models.Transaction.id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail=f"Transaction {transaction_id} not found")

    customer = db.query(models.Customer).filter(models.Customer.id == transaction.customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail=f"Customer {transaction.customer_id} not found")

    decision = (
        db.query(models.Decision)
        .filter(models.Decision.transaction_id == transaction_id)
        .order_by(models.Decision.created_at.desc())
        .first()
    )
    if not decision:
        raise HTTPException(
            status_code=400,
            detail="This transaction hasn't been analyzed yet -- run /analyze first",
        )

    context = _build_context(transaction, customer, decision)
    answer = answer_question(context, payload.question)

    if answer is None:
        return AskResponse(
            answer=(
                "The AI assistant is unavailable right now (no API key configured, or the "
                f"request failed). Here's what's on record: the engine chose "
                f"'{decision.selected_action}' with a net value of Rs {decision.expected_net_value:.0f}. "
                f"Reason: {decision.reason}"
            ),
            source="unavailable",
        )
    return AskResponse(answer=answer, source="llm")