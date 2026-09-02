"""
models.py
ORM table definitions. This is the single source of truth for the DB schema.

Tables:
- Customer        : one row per synthetic customer, holds behavioral history
- Transaction      : one row per failed payment event
- Intervention     : reference table of possible actions + their configurable costs
- Prediction       : ML-model output (recovery probability) per transaction x intervention
- Decision         : decision engine output for a transaction (the chosen action + numbers)
- Outcome          : what actually happened after the decision (for simulation/backtesting)
- AuditLog         : full trace of every decision, for the /audit/{id} endpoint
"""

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from .database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    segment = Column(String, nullable=False)          # e.g. "high_value", "regular", "new"

    # behavioral history features used by the ML model
    total_past_payments = Column(Integer, default=0)
    total_past_failures = Column(Integer, default=0)
    past_self_cure_count = Column(Integer, default=0)       # times they fixed it without contact
    past_recovery_attempts = Column(Integer, default=0)     # times an agent contacted them
    past_whatsapp_success = Column(Integer, default=0)
    past_whatsapp_attempts = Column(Integer, default=0)
    past_email_success = Column(Integer, default=0)
    past_email_attempts = Column(Integer, default=0)
    past_call_success = Column(Integer, default=0)
    past_call_attempts = Column(Integer, default=0)
    past_opt_outs = Column(Integer, default=0)               # times they complained/unsubscribed

    transactions = relationship("Transaction", back_populates="customer")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)

    amount = Column(Float, nullable=False)
    failure_reason = Column(String, nullable=False)   # e.g. "insufficient_funds", "timeout", "card_declined"
    payment_channel = Column(String, nullable=False)  # e.g. "upi", "card", "netbanking"
    days_since_failure = Column(Float, default=0.0)
    created_at = Column(DateTime, default=utcnow)

    customer = relationship("Customer", back_populates="transactions")
    predictions = relationship("Prediction", back_populates="transaction")
    decisions = relationship("Decision", back_populates="transaction")
    outcomes = relationship("Outcome", back_populates="transaction")


class Intervention(Base):
    __tablename__ = "interventions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)  # "whatsapp", "email", "voice", "retry",
                                                          # "discount", "human_followup", "wait", "do_nothing"
    base_cost = Column(Float, nullable=False)            # configurable ₹ cost per use
    annoyance_weight = Column(Float, default=0.0)        # relative intrusiveness, used in impact-cost calc
    is_active_action = Column(Boolean, default=True)     # False for wait/do_nothing


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=False)
    intervention_name = Column(String, nullable=False)
    recovery_probability = Column(Float, nullable=False)  # ML model output, 0..1
    created_at = Column(DateTime, default=utcnow)

    transaction = relationship("Transaction", back_populates="predictions")


class Decision(Base):
    __tablename__ = "decisions"

    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=False)

    selected_action = Column(String, nullable=False)
    recovery_probability = Column(Float, nullable=False)
    expected_recovery = Column(Float, nullable=False)
    intervention_cost = Column(Float, nullable=False)
    expected_customer_impact_cost = Column(Float, nullable=False)
    expected_net_value = Column(Float, nullable=False)
    reason = Column(Text, nullable=False)

    # snapshot of ALL options considered, stored as JSON text, for the audit trail
    all_options_json = Column(Text, nullable=False)

    created_at = Column(DateTime, default=utcnow)

    transaction = relationship("Transaction", back_populates="decisions")


class Outcome(Base):
    __tablename__ = "outcomes"

    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=False)
    decision_id = Column(Integer, ForeignKey("decisions.id"), nullable=True)

    recovered = Column(Boolean, nullable=False)
    amount_recovered = Column(Float, default=0.0)
    contacted = Column(Boolean, default=False)
    churn_or_annoyance_flag = Column(Boolean, default=False)
    strategy_label = Column(String, default="recovery_iq")  # "baseline" or "recovery_iq", used in comparison mode

    created_at = Column(DateTime, default=utcnow)

    transaction = relationship("Transaction", back_populates="outcomes")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=False)
    event_type = Column(String, nullable=False)   # "prediction_generated", "decision_made", "outcome_recorded"
    detail = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utcnow)