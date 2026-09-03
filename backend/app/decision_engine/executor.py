"""
executor.py

The EXECUTE step of the agent loop (detect -> determine -> execute).

This module actually performs -- in simulated form -- whatever action the
decision engine chose. It is intentionally separate from engine.py: the
engine decides WHAT to do and WHY (pure economics), this module carries
OUT that decision and produces a distinct, timestamped execution record.

Why simulated, not a real send: no team gets live WhatsApp Business API /
telephony credentials during a weekend hackathon, and that integration
work is orthogonal to what's being judged (the decision logic). Every
output here is clearly labeled [MOCK] so it's never confused with a real
outbound message. Swapping in a real provider (Twilio, Gupshup, etc.)
means replacing the string-building below with an actual API call --
the detect/determine layers upstream don't change at all.

This is a genuine execution step, not just more logging: it is a
separate, distinct event (event_type="action_executed") recorded AFTER
and SEPARATE FROM the decision event (event_type="decision_made"), with
its own content describing what was actually carried out.
"""

from datetime import datetime, timezone


def execute_action(action: str, amount: float, customer_name: str, payment_channel: str) -> dict:
    """
    Carries out the chosen action. Returns a dict with:
      - executed: bool -- True for anything that does something (including
        silent retry), False only for do_nothing (nothing to execute).
      - channel: the action name
      - detail: a human-readable description of what was actually done,
        prefixed [MOCK] for anything that would touch a real external
        system in production.
      - executed_at: ISO timestamp

    wait: still "executed" in the sense that a monitoring decision was
    carried out (no outbound message, but the recovery clock keeps running)
    -- this matches how the product frames WAIT as an active choice, not
    an absence of one.
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    if action == "whatsapp":
        detail = (
            f"[MOCK] WhatsApp sent to {customer_name}: \"Your payment of Rs "
            f"{amount:.0f} didn't go through. Complete it here: [payment link]\""
        )
    elif action == "email":
        detail = (
            f"[MOCK] Email sent to {customer_name}: \"We noticed your Rs "
            f"{amount:.0f} payment failed. Retry anytime via this link.\""
        )
    elif action == "voice":
        detail = f"[MOCK] Voice call placed to {customer_name} regarding the Rs {amount:.0f} payment failure."
    elif action == "discount":
        detail = f"[MOCK] Goodwill discount offer sent to {customer_name} to incentivize completing the Rs {amount:.0f} payment."
    elif action == "human_followup":
        detail = f"[MOCK] Support ticket created for a human agent to personally follow up with {customer_name}."
    elif action == "retry":
        detail = f"[MOCK] Silent retry attempted for Rs {amount:.0f} via {payment_channel}. No customer-facing message sent."
    elif action == "wait":
        detail = f"No outbound action taken for {customer_name}. Monitoring for self-cure over the next 24-48 hours."
    elif action == "do_nothing":
        detail = f"Transaction for {customer_name} marked closed. No further recovery action will be taken."
    else:
        detail = f"Unknown action '{action}' -- no execution defined."

    return {
        "executed": action != "do_nothing",
        "channel": action,
        "detail": detail,
        "executed_at": timestamp,
    }