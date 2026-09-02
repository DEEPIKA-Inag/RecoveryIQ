"""
routers/transactions.py
POST /transactions -- create a failed payment record.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from .helpers import get_or_create_customer

router = APIRouter(tags=["transactions"])


@router.post("/transactions", response_model=schemas.TransactionOut)
def create_transaction(payload: schemas.TransactionCreate, db: Session = Depends(get_db)):
    # ensures a customer row exists (auto-creates with plausible defaults if new)
    get_or_create_customer(db, payload.customer_id)

    transaction = models.Transaction(
        customer_id=payload.customer_id,
        amount=payload.amount,
        failure_reason=payload.failure_reason,
        payment_channel=payload.payment_channel,
        days_since_failure=payload.days_since_failure,
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction