"""
explainer.py

Optional LLM layer, using Google's Gemini API. Two functions:

  - generate_llm_explanation(): writes ONE fixed-format sentence narrating
    a decision that's ALREADY been made by engine.py's arithmetic.

  - answer_question(): free-form Q&A about a specific transaction's
    decision, grounded ONLY in real numbers passed in via `context`.

Reliability rules for a live demo:
  - If GEMINI_API_KEY isn't set, or the `google-genai` package isn't
    installed, or the call fails/times out for any reason -- both
    functions return None. Callers fall back to a safe default.
"""

import os

_MODEL = "gemini-3.6-flash"
_TIMEOUT_MS = 10000

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
            return None
        text = (response.text or "").strip()
        return text or None
    except Exception:
        return None


def answer_question(context: str, question: str) -> str | None:
    if _client is None:
        return None

    prompt = (
        "You are explaining a payment recovery decision-support system's output "
        "to someone asking a question about it. Use ONLY the facts given below to "
        "answer -- do not invent numbers or assumptions not stated. If the question "
        "can't be answered from the facts given, say so honestly rather than "
        "guessing. Keep the answer to 2-4 sentences, plain language, no marketing "
        "tone.\n\n"
        f"FACTS:\n{context}\n\n"
        f"QUESTION: {question}\n\n"
        "ANSWER:"
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
        finish_reason = response.candidates[0].finish_reason if response.candidates else "NO CANDIDATES"
        text = (response.text or "").strip()
        return text or None
    except Exception as e:
        print(f"[ASK ERROR] {type(e).__name__}: {e}")
        return None