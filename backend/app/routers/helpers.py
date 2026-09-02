"""
helpers.py
Small shared utilities used by multiple routers -- kept separate so
transactions.py and analyze.py don't duplicate this logic.
"""

import random
from sqlalchemy.orm import Session
from .. import models


def get_or_create_customer(db: Session, customer_id: int) -> models.Customer:
    """
    Looks up a customer by id. If they don't exist yet, creates one with
    randomized-but-plausible default history so the demo can create
    transactions for "new" customer ids without a separate /customers
    endpoint. Real production version would require the customer to
    already exist.
    """
    customer = db.query(models.Customer).filter(models.Customer.id == customer_id).first()
    if customer:
        return customer

    total_past_failures = random.randint(0, 8)
    past_self_cure_count = random.randint(0, total_past_failures)
    customer = models.Customer(
        id=customer_id,
        name=f"Customer {customer_id}",
        segment=random.choice(["new", "regular", "high_value"]),
        total_past_payments=random.randint(1, 50),
        total_past_failures=total_past_failures,
        past_self_cure_count=past_self_cure_count,
        past_recovery_attempts=random.randint(0, 6),
        past_whatsapp_success=random.randint(0, 3),
        past_whatsapp_attempts=random.randint(0, 5),
        past_email_success=random.randint(0, 2),
        past_email_attempts=random.randint(0, 4),
        past_call_success=random.randint(0, 2),
        past_call_attempts=random.randint(0, 3),
        past_opt_outs=random.choice([0, 0, 0, 1]),
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def transaction_to_engine_input(transaction: models.Transaction) -> dict:
    return {
        "amount": transaction.amount,
        "failure_reason": transaction.failure_reason,
        "days_since_failure": transaction.days_since_failure,
    }


def customer_to_engine_input(customer: models.Customer) -> dict:
    return {
        "total_past_payments": customer.total_past_payments,
        "total_past_failures": customer.total_past_failures,
        "past_self_cure_count": customer.past_self_cure_count,
        "past_recovery_attempts": customer.past_recovery_attempts,
        "past_opt_outs": customer.past_opt_outs,
        "past_whatsapp_success": customer.past_whatsapp_success,
        "past_whatsapp_attempts": customer.past_whatsapp_attempts,
        "past_email_success": customer.past_email_success,
        "past_email_attempts": customer.past_email_attempts,
        "past_call_success": customer.past_call_success,
        "past_call_attempts": customer.past_call_attempts,
    }