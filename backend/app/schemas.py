"""
schemas.py
Pydantic models for API request/response validation.
Kept separate from models.py (ORM) on purpose -- API shape and DB shape
are allowed to diverge as the project grows.
"""

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


# ---------- Transactions ----------

class TransactionCreate(BaseModel):
    customer_id: int
    amount: float
    failure_reason: str
    payment_channel: str
    days_since_failure: float = 0.0


class TransactionOut(BaseModel):
    id: int
    customer_id: int
    amount: float
    failure_reason: str
    payment_channel: str
    days_since_failure: float
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Recovery options / analysis ----------

class OptionResult(BaseModel):
    action: str
    recovery_probability: float
    expected_recovery: float
    intervention_cost: float
    expected_customer_impact_cost: float
    expected_net_value: float


class AnalyzeResult(BaseModel):
    transaction_id: int
    amount: float
    recommended_action: str
    recovery_probability: float
    expected_recovery: float
    intervention_cost: float
    expected_customer_impact_cost: float
    expected_net_value: float
    reason: str
    all_options: List[OptionResult]


# ---------- Decisions / audit ----------

class DecisionOut(BaseModel):
    id: int
    transaction_id: int
    selected_action: str
    recovery_probability: float
    expected_recovery: float
    intervention_cost: float
    expected_customer_impact_cost: float
    expected_net_value: float
    reason: str
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Dashboard ----------

class DashboardSummary(BaseModel):
    payments_analyzed: int
    revenue_at_risk: float
    expected_recovery: float
    expected_net_value: float
    interventions_avoided: int
    wait_decisions: int
    do_not_contact_decisions: int
    recovery_rate: Optional[float] = None


# ---------- Simulation / comparison ----------

class SimulateRequest(BaseModel):
    batch_size: int = 20


class StrategyResult(BaseModel):
    strategy: str
    payments: int
    revenue_recovered: float
    intervention_cost: float
    contacts_made: int
    expected_churn_annoyance: float
    net_value: float


class SimulateResult(BaseModel):
    baseline: StrategyResult
    recovery_iq: StrategyResult
    net_value_lift: float
    contacts_avoided_pct: float
    intervention_cost_saved: float