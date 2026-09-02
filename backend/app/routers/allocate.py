"""
routers/allocate.py
POST /allocate -- budget-constrained portfolio allocation.

The core decision engine (engine.py) picks the best action for EACH
transaction independently, implicitly assuming unlimited recovery budget.
Real merchants have a finite monthly spend cap. This endpoint answers a
different question: "given only ₹X to spend this month on active outreach,
which subset of failures should actually get contacted to maximize total
net value?"

Approach: for every transaction, compute the INCREMENTAL value of
intervening -- the engine's chosen active option's net value minus the
best passive (WAIT/DO_NOTHING) alternative's net value. That's the real
value an intervention buys, on top of what you'd get by doing nothing.
Rank all active-worthy transactions by incremental value per rupee spent
(classic greedy knapsack heuristic), fund them in that order until the
budget runs out, then downgrade everything past the cutoff to its passive
alternative.

This is a NEW, isolated endpoint. It does not modify /simulate, /analyze,
or any other existing route -- it reuses the same engine.evaluate_transaction
and helpers already tested elsewhere.
"""

import random
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import List

from .. import models
from ..database import get_db
from ..decision_engine.engine import evaluate_transaction
from ..config import ACTIVE_ACTIONS, PASSIVE_ACTIONS
from .helpers import get_or_create_customer, transaction_to_engine_input, customer_to_engine_input
from .simulate import FAILURE_REASONS, PAYMENT_CHANNELS, _random_amount, _next_synthetic_customer_id

router = APIRouter(tags=["allocate"])


class AllocateRequest(BaseModel):
    batch_size: int = 20
    budget_cap: float = 500.0


class AllocatedTransaction(BaseModel):
    transaction_id: int
    amount: float
    unconstrained_action: str
    unconstrained_net_value: float
    incremental_value: float
    intervention_cost: float
    funded: bool
    final_action: str
    final_net_value: float


class AllocateResult(BaseModel):
    batch_size: int
    budget_cap: float
    budget_spent: float
    transactions_funded: int
    transactions_deferred: int
    unconstrained_total_net_value: float
    budget_constrained_total_net_value: float
    value_lost_to_budget_cap: float
    allocations: List[AllocatedTransaction]


@router.post("/allocate", response_model=AllocateResult)
def allocate(payload: AllocateRequest, db: Session = Depends(get_db)):
    batch_size = max(1, payload.batch_size)
    budget_cap = max(0.0, payload.budget_cap)

    next_customer_id = _next_synthetic_customer_id(db)
    candidates = []

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
        result = evaluate_transaction(txn_input, cust_input)

        passive_options = [o for o in result["all_options"] if o["action"] in PASSIVE_ACTIONS]
        best_passive = max(passive_options, key=lambda o: o["expected_net_value"])

        is_active = result["recommended_action"] in ACTIVE_ACTIONS
        incremental_value = (
            result["expected_net_value"] - best_passive["expected_net_value"] if is_active else 0.0
        )

        candidates.append({
            "transaction_id": transaction.id,
            "amount": transaction.amount,
            "unconstrained_action": result["recommended_action"],
            "unconstrained_net_value": result["expected_net_value"],
            "incremental_value": round(incremental_value, 2),
            "intervention_cost": result["intervention_cost"] if is_active else 0.0,
            "best_passive_action": best_passive["action"],
            "best_passive_net_value": best_passive["expected_net_value"],
        })

    active_candidates = [c for c in candidates if c["incremental_value"] > 0 and c["intervention_cost"] > 0]
    active_candidates.sort(key=lambda c: c["incremental_value"] / c["intervention_cost"], reverse=True)

    funded_ids = set()
    budget_spent = 0.0
    for c in active_candidates:
        if budget_spent + c["intervention_cost"] <= budget_cap:
            funded_ids.add(c["transaction_id"])
            budget_spent += c["intervention_cost"]

    allocations = []
    unconstrained_total = 0.0
    constrained_total = 0.0

    for c in candidates:
        unconstrained_total += c["unconstrained_net_value"]

        if c["transaction_id"] in funded_ids:
            final_action = c["unconstrained_action"]
            final_net_value = c["unconstrained_net_value"]
            funded = True
        else:
            final_action = c["best_passive_action"]
            final_net_value = c["best_passive_net_value"]
            funded = False

        constrained_total += final_net_value

        allocations.append(AllocatedTransaction(
            transaction_id=c["transaction_id"],
            amount=c["amount"],
            unconstrained_action=c["unconstrained_action"],
            unconstrained_net_value=c["unconstrained_net_value"],
            incremental_value=c["incremental_value"],
            intervention_cost=c["intervention_cost"],
            funded=funded,
            final_action=final_action,
            final_net_value=round(final_net_value, 2),
        ))

    transactions_funded = sum(1 for a in allocations if a.funded)
    transactions_deferred = batch_size - transactions_funded

    return AllocateResult(
        batch_size=batch_size,
        budget_cap=budget_cap,
        budget_spent=round(budget_spent, 2),
        transactions_funded=transactions_funded,
        transactions_deferred=transactions_deferred,
        unconstrained_total_net_value=round(unconstrained_total, 2),
        budget_constrained_total_net_value=round(constrained_total, 2),
        value_lost_to_budget_cap=round(unconstrained_total - constrained_total, 2),
        allocations=allocations,
    )