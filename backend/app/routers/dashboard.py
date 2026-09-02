"""
routers/dashboard.py
GET /dashboard -- aggregated summary stats across all decisions made so far.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from .. import models, schemas
from ..database import get_db
from ..config import PASSIVE_ACTIONS

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=schemas.DashboardSummary)
def dashboard_summary(db: Session = Depends(get_db)):
    decisions = db.query(models.Decision).all()

    payments_analyzed = len(decisions)

    txn_ids = [d.transaction_id for d in decisions]
    revenue_at_risk = 0.0
    if txn_ids:
        revenue_at_risk = (
            db.query(func.sum(models.Transaction.amount))
            .filter(models.Transaction.id.in_(txn_ids))
            .scalar()
        ) or 0.0

    expected_recovery = sum(d.expected_recovery for d in decisions)
    expected_net_value = sum(d.expected_net_value for d in decisions)

    wait_decisions = sum(1 for d in decisions if d.selected_action == "wait")
    do_not_contact_decisions = sum(1 for d in decisions if d.selected_action == "do_nothing")
    interventions_avoided = sum(1 for d in decisions if d.selected_action in PASSIVE_ACTIONS)

    outcomes = db.query(models.Outcome).all()
    recovery_rate = None
    if outcomes:
        recovered = sum(1 for o in outcomes if o.recovered)
        recovery_rate = round(recovered / len(outcomes), 4)

    return schemas.DashboardSummary(
        payments_analyzed=payments_analyzed,
        revenue_at_risk=round(revenue_at_risk, 2),
        expected_recovery=round(expected_recovery, 2),
        expected_net_value=round(expected_net_value, 2),
        interventions_avoided=interventions_avoided,
        wait_decisions=wait_decisions,
        do_not_contact_decisions=do_not_contact_decisions,
        recovery_rate=recovery_rate,
    )