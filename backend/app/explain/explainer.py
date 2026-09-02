"""
explainer.py

Optional LLM layer. Per the project spec: the LLM ONLY writes a human-
readable sentence explaining a decision that has ALREADY been made by
engine.py's arithmetic. It is never given the ability to change a
probability, cost, or the selected action -- those are passed in as
already-computed facts, and the model is instructed to just narrate them.

Reliability rules for a live demo:
  - If ANTHROPIC_API_KEY isn't set, or the `anthropic` package isn't
    installed, or the call fails/times out for any reason -- this
    function returns None. The caller (routers/analyze.py) falls back
    to the rule-based reason from engine.py. The demo NEVER blocks or
    crashes because of this layer; it's a pure enhancement.
  - Strict 4-second timeout so a slow network never stalls the UI.
"""

import os

_TIMEOUT_SECONDS = 4.0
_MODEL = "claude-haiku-4-5-20251001"  # fast, cheap -- fine for a one-sentence explanation

try:
    import anthropic
    _client = None
    if os.environ.get("ANTHROPIC_API_KEY"):
        _client = anthropic.Anthropic(timeout=_TIMEOUT_SECONDS)
except ImportError:
    _client = None


def generate_llm_explanation(decision: dict) -> str | None:
    """
    decision: dict with keys action, probability, amount, expected_recovery,
              intervention_cost, expected_customer_impact_cost, net_value,
              failure_reason
    Returns a one-sentence explanation string, or None if the LLM is
    unavailable/fails for any reason (caller should fall back).
    """
    if _client is None:
        return None

    prompt = (
        "A payment recovery decision engine already chose an action using pure "
        "arithmetic. Write ONE plain sentence (under 30 words) explaining this "
        "decision to a merchant. Do not invent any numbers beyond what's given. "
        "Do not use exclamation marks or marketing language.\n\n"
        f"Action chosen: {decision['action']}\n"
        f"Recovery probability: {decision['probability']:.0%}\n"
        f"Transaction amount: Rs {decision['amount']:.0f}\n"
        f"Expected recovery: Rs {decision['expected_recovery']:.0f}\n"
        f"Intervention cost: Rs {decision['intervention_cost']:.0f}\n"
        f"Customer impact cost: Rs {decision['expected_customer_impact_cost']:.0f}\n"
        f"Net value: Rs {decision['net_value']:.0f}\n"
        f"Failure reason: {decision['failure_reason']}\n"
    )

    try:
        response = _client.messages.create(
            model=_MODEL,
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        ).strip()
        return text or None
    except Exception:
        # Any failure (timeout, bad key, rate limit, network) -- silently
        # fall back. A demo must never hang or 500 because of this.
        return None