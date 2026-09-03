"""
explainer.py

Optional LLM layer, using Google's Gemini API. Per the project spec: the
LLM ONLY writes a human-readable sentence explaining a decision that has
ALREADY been made by engine.py's arithmetic. It is never given the ability
to change a probability, cost, or the selected action -- those are passed
in as already-computed facts, and the model is instructed to just narrate
them.

Reliability rules for a live demo:
  - If GEMINI_API_KEY isn't set, or the `google-genai` package isn't
    installed, or the call fails/times out for any reason -- this
    function returns None. The caller (routers/analyze.py) falls back
    to the rule-based reason from engine.py. The demo NEVER blocks or
    crashes because of this layer; it's a pure enhancement.
  - max_output_tokens is set generously (2000) because this model spends
    a portion of its budget on internal reasoning before writing visible
    output -- too low a budget causes the response to get cut off
    mid-sentence (finish_reason=MAX_TOKENS), which is explicitly checked
    for and discarded below rather than ever being used as a real answer.
"""

import os

_MODEL = "gemini-3.6-flash"  # fast, cheap -- fine for a one-sentence explanation
_TIMEOUT_MS = 10000  # Google's API requires a minimum 10s deadline

try:
    from google import genai
    from google.genai import types

    _client = None
    _api_key = os.environ.get("GEMINI_API_KEY")
    if _api_key:
        _client = genai.Client(api_key=_api_key)
except ImportError:
    genai = None
    types = None
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
        response = _client.models.generate_content(
            model=_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=2000,
                http_options=types.HttpOptions(timeout=_TIMEOUT_MS),
            ),
        )
        finish_reason = response.candidates[0].finish_reason if response.candidates else None
        if finish_reason is not None and str(finish_reason).endswith("MAX_TOKENS"):
            # Truncated mid-generation -- a broken half-sentence is worse
            # than falling back to the solid rule-based explanation.
            return None
        text = (response.text or "").strip()
        return text or None
    except Exception:
        # Any failure (timeout, bad key, rate limit, network) -- silently
        # fall back. A demo must never hang or 500 because of this.
        return None