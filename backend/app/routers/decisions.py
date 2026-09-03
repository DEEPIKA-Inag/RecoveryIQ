"""
routers/decisions.py
GET /decisions           -- list all past decisions (most recent first)
GET /audit/{transaction_id} -- full decision + prediction + audit-log history for one transaction
GET /opportunities       -- joined view powering the 'Recovery Opportunities' dashboard table
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from .. import models, schemas
from ..database import get_db

router = APIRouter(tags=["decisions"])


@router.get("/decisions", response_model=List[schemas.DecisionOut])
def list_decisions(db: Session = Depends(get_db), limit: int = 100):
    decisions = (
        db.query(models.Decision)
        .order_by(models.Decision.created_at.desc())
        .limit(limit)
        .all()
    )
    return decisions


@router.get("/opportunities")
def recovery_opportunities(db: Session = Depends(get_db), limit: int = 50):
    """
    Joined view of Decision + Transaction + Customer, shaped for the
    'Recovery Opportunities' table on the dashboard:
    customer | amount | failure | best action | probability | net value | reason
    """
    rows = (
        db.query(models.Decision, models.Transaction, models.Customer)
        .join(models.Transaction, models.Decision.transaction_id == models.Transaction.id)
        .join(models.Customer, models.Transaction.customer_id == models.Customer.id)
        .order_by(models.Decision.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "transaction_id": txn.id,
            "customer_name": cust.name,
            "customer_segment": cust.segment,
            "amount": txn.amount,
            "failure_reason": txn.failure_reason,
            "selected_action": dec.selected_action,
            "recovery_probability": dec.recovery_probability,
            "expected_net_value": dec.expected_net_value,
            "reason": dec.reason,
            "explanation_source": dec.explanation_source,
            "created_at": dec.created_at,
        }
        for dec, txn, cust in rows
    ]


@router.get("/audit/{transaction_id}")
def audit_trail(transaction_id: int, db: Session = Depends(get_db)):
    transaction = db.query(models.Transaction).filter(models.Transaction.id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail=f"Transaction {transaction_id} not found")

    predictions = (
        db.query(models.Prediction)
        .filter(models.Prediction.transaction_id == transaction_id)
        .order_by(models.Prediction.created_at.asc())
        .all()
    )
    decisions = (
        db.query(models.Decision)
        .filter(models.Decision.transaction_id == transaction_id)
        .order_by(models.Decision.created_at.asc())
        .all()
    )
    outcomes = (
        db.query(models.Outcome)
        .filter(models.Outcome.transaction_id == transaction_id)
        .order_by(models.Outcome.created_at.asc())
        .all()
    )
    logs = (
        db.query(models.AuditLog)
        .filter(models.AuditLog.transaction_id == transaction_id)
        .order_by(models.AuditLog.created_at.asc())
        .all()
    )

    return {
        "transaction": {
            "id": transaction.id,
            "customer_id": transaction.customer_id,
            "amount": transaction.amount,
            "failure_reason": transaction.failure_reason,
            "payment_channel": transaction.payment_channel,
            "days_since_failure": transaction.days_since_failure,
            "created_at": transaction.created_at,
        },
        "predictions": [
            {
                "intervention_name": p.intervention_name,
                "recovery_probability": p.recovery_probability,
                "created_at": p.created_at,
            }
            for p in predictions
        ],
        "decisions": [
            {
                "selected_action": d.selected_action,
                "recovery_probability": d.recovery_probability,
                "expected_recovery": d.expected_recovery,
                "intervention_cost": d.intervention_cost,
                "expected_customer_impact_cost": d.expected_customer_impact_cost,
                "expected_net_value": d.expected_net_value,
                "reason": d.reason,
                "explanation_source": d.explanation_source,
                "created_at": d.created_at,
            }
            for d in decisions
        ],
        "outcomes": [
            {
                "recovered": o.recovered,
                "amount_recovered": o.amount_recovered,
                "contacted": o.contacted,
                "churn_or_annoyance_flag": o.churn_or_annoyance_flag,
                "strategy_label": o.strategy_label,
                "created_at": o.created_at,
            }
            for o in outcomes
        ],
        "audit_logs": [
            {"event_type": l.event_type, "detail": l.detail, "created_at": l.created_at}
            for l in logs
        ],
    }