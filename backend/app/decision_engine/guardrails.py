"""
guardrails.py

Hard compliance/policy filters. These run BEFORE the ML model or the EV
engine sees a transaction, and are never overridden by economics -- no
matter how favorable a probability looks, a customer-facing contact never
happens if a guardrail blocks it. This is deliberately separate from
engine.py's arithmetic: guardrails are policy, not optimization.

Two tiers of blocking, because "retry" is a silent backend charge attempt
with no customer-facing message -- guardrails that exist to protect the
CUSTOMER from unwanted contact (opt-out, quiet hours, contact-attempt cap)
don't apply to it. Only fraud blocks retry too, since retrying a charge on
a fraud-flagged account is a risk unrelated to annoying anyone.

  - hard_block_reasons(): blocks ALL active actions, including retry.
    Currently just fraud-flag.
  - contact_block_reasons(): blocks only CUSTOMER_FACING_ACTIONS (retry
    stays allowed). Opt-out, quiet hours, contact-attempt cap.

Cheaper than a model call, so these run first and short-circuit prediction
for actions that would be blocked anyway.
"""

from datetime import datetime
from typing import List, Optional

from ..config import QUIET_HOURS_START_HOUR, QUIET_HOURS_END_HOUR, MAX_CONTACT_ATTEMPTS


def is_within_quiet_hours(now: Optional[datetime] = None) -> bool:
    now = now or datetime.now()
    hour = now.hour
    if QUIET_HOURS_START_HOUR > QUIET_HOURS_END_HOUR:
        # window wraps past midnight, e.g. 22 -> 8
        return hour >= QUIET_HOURS_START_HOUR or hour < QUIET_HOURS_END_HOUR
    return QUIET_HOURS_START_HOUR <= hour < QUIET_HOURS_END_HOUR


def hard_block_reasons(customer: dict) -> List[str]:
    """
    Reasons that block ALL active actions, including retry (a non-contact,
    silent backend action). Currently: fraud flag only. Retrying a charge
    on a fraud-flagged account is itself a risk, so it's blocked too --
    unlike opt-out/quiet-hours/contact-cap, which only protect the customer
    from unwanted CONTACT and have no reason to stop a silent retry.
    """
    reasons = []
    if customer.get("is_fraud_flagged"):
        reasons.append("customer is fraud-flagged (defense-only policy: no outbound action, including retry)")
    return reasons


def contact_block_reasons(customer: dict, now: Optional[datetime] = None) -> List[str]:
    """
    Reasons that block CUSTOMER-FACING active actions only (WhatsApp, email,
    voice, discount, human follow-up). Retry remains allowed even if these
    fire, since it never contacts the customer.
    """
    reasons = []
    if customer.get("is_opted_out"):
        reasons.append("customer has opted out of contact")
    if customer.get("past_recovery_attempts", 0) >= MAX_CONTACT_ATTEMPTS:
        reasons.append(f"contact cap reached ({MAX_CONTACT_ATTEMPTS} prior attempts)")
    if is_within_quiet_hours(now):
        reasons.append("current time is within configured quiet hours")
    return reasons


def blocked_reasons(customer: dict, now: Optional[datetime] = None) -> List[str]:
    """
    Backwards-compatible combined view: ALL reasons that block AT LEAST
    customer-facing contact (used for display/audit purposes). Does not
    distinguish hard vs contact-only blocks -- engine.py calls the two
    functions above directly to apply them with different scope.
    """
    return hard_block_reasons(customer) + contact_block_reasons(customer, now)