"""
config.py
All the "business assumption" numbers live here, in one place, so the
demo can be tuned without touching the decision engine or ML code.

IMPORTANT: these are DEMO ASSUMPTIONS, not Razorpay's real costs.
Say this explicitly in the pitch if asked.
"""

# ₹ cost of using each intervention channel once.
# annoyance_weight: relative "customer irritation" multiplier used to compute
# expected_customer_impact_cost = annoyance_weight * amount * probability_of_failure_to_recover
INTERVENTION_CONFIG = {
    "retry":          {"base_cost": 20,  "annoyance_weight": 0.01},
    "whatsapp":       {"base_cost": 50,  "annoyance_weight": 0.02},
    "email":          {"base_cost": 10,  "annoyance_weight": 0.01},
    "voice":          {"base_cost": 300, "annoyance_weight": 0.06},
    "discount":       {"base_cost": 250, "annoyance_weight": 0.00},  # cost = discount value given, no annoyance
    "human_followup": {"base_cost": 500, "annoyance_weight": 0.03},
    "wait":           {"base_cost": 0,   "annoyance_weight": 0.00},
    "do_nothing":     {"base_cost": 0,   "annoyance_weight": 0.00},
}

# Actions considered "active" (i.e. Razorpay-style agents would normally fire these)
# Actions considered "active" (i.e. Razorpay-style agents would normally fire these)
ACTIVE_ACTIONS = ["retry", "whatsapp", "email", "voice", "discount", "human_followup"]

# Subset of ACTIVE_ACTIONS that actually contacts the customer (message, call,
# offer). "retry" is deliberately excluded -- it's a silent backend charge
# attempt with no customer-facing message, so opt-out/quiet-hours/contact-cap
# guardrails (which exist to protect the CUSTOMER from unwanted contact)
# don't apply to it. Only a fraud flag blocks retry, since retrying a charge
# on a fraud-flagged account is itself a risk, unrelated to annoying anyone.
CUSTOMER_FACING_ACTIONS = ["whatsapp", "email", "voice", "discount", "human_followup"]

# Passive / restraint actions -- the whole point of Recovery IQ
PASSIVE_ACTIONS = ["wait", "do_nothing"]

ALL_ACTIONS = ACTIVE_ACTIONS + PASSIVE_ACTIONS

# For the "wait" option: how much of the amount do we assume gets recovered
# if the customer self-cures, discounted slightly for the delay.
WAIT_SELF_CURE_DISCOUNT = 0.98  # small time-value discount vs immediate recovery

# Baseline strategy (used only in /simulate comparison mode):
# "contact everyone" = always pick this single default active action, ignoring EV.
BASELINE_DEFAULT_ACTION = "whatsapp"

# --- Compliance / guardrail settings ---
# These are HARD stops that run before the ML model or EV math even sees a
# transaction. They are policy, not economics -- the EV engine never
# overrides them, no matter how favorable a probability looks.
QUIET_HOURS_START_HOUR = 22  # 10 PM
QUIET_HOURS_END_HOUR = 8     # 8 AM (wraps past midnight)
MAX_CONTACT_ATTEMPTS = 10    # stop active contact after this many prior attempts
# Snapshot of the original values, used by the config reset endpoint.
# NOTE: INTERVENTION_CONFIG above is mutated IN PLACE by the /config router
# (never reassigned to a new dict object) so every module that already did
# `from .config import INTERVENTION_CONFIG` keeps seeing live updates.
import copy as _copy
_DEFAULT_INTERVENTION_CONFIG = _copy.deepcopy(INTERVENTION_CONFIG)