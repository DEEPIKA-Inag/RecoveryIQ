"""
generate_synthetic_data.py

Generates a synthetic historical dataset of failed-payment recovery attempts,
with realistic embedded patterns so the ML model in train_model.py has
something genuine to learn (not pure noise).

Patterns baked in on purpose:
  1. Small amounts + "insufficient_funds" -> high self-cure rate, low value
     in contacting the customer at all.
  2. Customers with a history of opting out / being over-contacted show
     LOWER response probability and a higher annoyance flag when contacted
     again ("fatigue").
  3. High-value customers ("high_value" segment) respond well to voice/human
     followup but are rare and expensive to contact.
  4. Each customer has a personal channel preference (some only respond to
     WhatsApp, some only to voice) baked into their historical response rates.
  5. days_since_failure matters: self-cure probability decays the longer a
     failure sits unresolved without ever being fixed.

Output: backend/data/synthetic_transactions.csv
Run with (from backend/, venv active):
    python -m app.ml.generate_synthetic_data
"""

import os
import random
import csv
from datetime import datetime, timedelta

random.seed(42)  # reproducible dataset

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT_PATH = os.path.join(BASE_DIR, "data", "synthetic_transactions.csv")

FAILURE_REASONS = ["insufficient_funds", "timeout", "card_declined", "network_error", "bank_server_down"]
PAYMENT_CHANNELS = ["upi", "card", "netbanking", "wallet"]
INTERVENTIONS = ["retry", "whatsapp", "email", "voice", "discount", "human_followup"]
SEGMENTS = ["new", "regular", "high_value"]

NUM_CUSTOMERS = 180
RECORDS_TARGET = 1200  # within the 500-2000 range requested


def make_customers(n):
    customers = []
    for cid in range(1, n + 1):
        segment = random.choices(SEGMENTS, weights=[0.3, 0.5, 0.2])[0]

        # Each customer has a hidden "channel affinity" -- which intervention
        # they historically respond best to. This is what the model has to
        # discover from past_X_success / past_X_attempts ratios.
        preferred_channel = random.choice(["whatsapp", "email", "voice", "retry"])

        past_recovery_attempts = random.randint(0, 12)
        past_opt_outs = 0
        # customers contacted a lot without opting out are "tolerant";
        # some fraction of heavily-contacted customers develop opt-outs (fatigue)
        if past_recovery_attempts > 6 and random.random() < 0.35:
            past_opt_outs = random.randint(1, 2)

        total_past_failures = past_recovery_attempts + random.randint(0, 5)
        past_self_cure_count = max(0, total_past_failures - past_recovery_attempts) + random.randint(0, 3)
        total_past_payments = random.randint(5, 100)

        # Build per-channel historical success/attempt counts, biased toward preferred_channel
        channel_stats = {}
        for ch in ["whatsapp", "email", "call"]:
            attempts = random.randint(0, 6)
            base_rate = 0.75 if (ch == "call" and preferred_channel == "voice") else \
                        0.75 if ch == preferred_channel else 0.35
            # fatigue reduces success rate
            fatigue_penalty = 0.25 if past_opt_outs > 0 else 0.0
            success_rate = max(0.05, base_rate - fatigue_penalty)
            successes = sum(1 for _ in range(attempts) if random.random() < success_rate)
            channel_stats[ch] = (successes, attempts)

        customers.append({
            "id": cid,
            "segment": segment,
            "preferred_channel": preferred_channel,
            "total_past_payments": total_past_payments,
            "total_past_failures": total_past_failures,
            "past_self_cure_count": past_self_cure_count,
            "past_recovery_attempts": past_recovery_attempts,
            "past_whatsapp_success": channel_stats["whatsapp"][0],
            "past_whatsapp_attempts": channel_stats["whatsapp"][1],
            "past_email_success": channel_stats["email"][0],
            "past_email_attempts": channel_stats["email"][1],
            "past_call_success": channel_stats["call"][0],
            "past_call_attempts": channel_stats["call"][1],
            "past_opt_outs": past_opt_outs,
        })
    return customers


def sample_amount(segment):
    if segment == "high_value":
        return round(random.uniform(5000, 50000), 2)
    if segment == "regular":
        return round(random.uniform(500, 8000), 2)
    return round(random.uniform(100, 3000), 2)  # new


def self_cure_probability(amount, failure_reason, days_since_failure, customer):
    """Probability the customer would recover the payment with ZERO contact."""
    p = 0.5

    if failure_reason == "insufficient_funds" and amount < 1000:
        p += 0.30
    if failure_reason == "network_error":
        p += 0.20
    if failure_reason == "bank_server_down":
        p += 0.15
    if failure_reason == "card_declined":
        p -= 0.10
    if failure_reason == "timeout":
        p += 0.05

    # historical self-cure tendency
    hist_ratio = customer["past_self_cure_count"] / max(1, customer["total_past_failures"])
    p += (hist_ratio - 0.5) * 0.4

    # decays the longer it's been unresolved
    p -= min(0.25, days_since_failure * 0.03)

    return min(0.95, max(0.02, p))


def channel_recovery_probability(channel, amount, customer, failure_reason):
    """Probability of recovery IF this channel is used to contact the customer."""
    if channel == "retry":
        base = 0.55 if failure_reason in ("timeout", "network_error", "bank_server_down") else 0.35
    elif channel == "whatsapp":
        ratio = customer["past_whatsapp_success"] / max(1, customer["past_whatsapp_attempts"])
        base = 0.4 + ratio * 0.4 if customer["past_whatsapp_attempts"] > 0 else 0.55
    elif channel == "email":
        ratio = customer["past_email_success"] / max(1, customer["past_email_attempts"])
        base = 0.3 + ratio * 0.4 if customer["past_email_attempts"] > 0 else 0.35
    elif channel == "voice":
        ratio = customer["past_call_success"] / max(1, customer["past_call_attempts"])
        base = 0.45 + ratio * 0.4 if customer["past_call_attempts"] > 0 else 0.6
    elif channel == "discount":
        base = 0.65  # discount is generally persuasive but expensive
    elif channel == "human_followup":
        base = 0.7 if customer["segment"] == "high_value" else 0.5
    else:
        base = 0.4

    # fatigue penalty: customers with opt-out history respond worse to any active contact
    if customer["past_opt_outs"] > 0:
        base -= 0.20 * customer["past_opt_outs"]

    # very high amounts are slightly harder to recover regardless of channel
    if amount > 20000:
        base -= 0.05

    return min(0.97, max(0.03, base))


def annoyance_flag(channel, customer):
    """Whether this contact attempt causes visible annoyance/churn signal."""
    if channel in ("wait", "do_nothing", "retry"):
        return False
    fatigue_score = customer["past_opt_outs"] * 0.3 + max(0, customer["past_recovery_attempts"] - 5) * 0.05
    if channel == "voice":
        fatigue_score += 0.15  # voice is more intrusive
    if channel == "human_followup":
        fatigue_score += 0.05
    return random.random() < min(0.9, fatigue_score)


def generate():
    customers = make_customers(NUM_CUSTOMERS)
    rows = []
    start_date = datetime(2025, 1, 1)

    while len(rows) < RECORDS_TARGET:
        customer = random.choice(customers)
        amount = sample_amount(customer["segment"])
        failure_reason = random.choice(FAILURE_REASONS)
        payment_channel = random.choice(PAYMENT_CHANNELS)
        days_since_failure = round(random.uniform(0, 10), 1)
        event_date = start_date + timedelta(days=random.randint(0, 500))

        chosen_intervention = random.choices(
            INTERVENTIONS + ["none"],
            weights=[10, 20, 12, 8, 6, 5, 15],
        )[0]

        if chosen_intervention == "none":
            p_recover = self_cure_probability(amount, failure_reason, days_since_failure, customer)
            recovered = random.random() < p_recover
            contacted = False
            churn_flag = False
            recovery_time_hours = round(random.uniform(1, 72), 1) if recovered else None
        else:
            p_recover = channel_recovery_probability(chosen_intervention, amount, customer, failure_reason)
            recovered = random.random() < p_recover
            contacted = True
            churn_flag = annoyance_flag(chosen_intervention, customer)
            recovery_time_hours = round(random.uniform(0.1, 48), 1) if recovered else None

        amount_recovered = amount if recovered else 0.0

        rows.append({
            "customer_id": customer["id"],
            "customer_segment": customer["segment"],
            "amount": amount,
            "failure_reason": failure_reason,
            "payment_channel": payment_channel,
            "days_since_failure": days_since_failure,
            "event_date": event_date.strftime("%Y-%m-%d"),
            "total_past_payments": customer["total_past_payments"],
            "total_past_failures": customer["total_past_failures"],
            "past_self_cure_count": customer["past_self_cure_count"],
            "past_recovery_attempts": customer["past_recovery_attempts"],
            "past_whatsapp_success": customer["past_whatsapp_success"],
            "past_whatsapp_attempts": customer["past_whatsapp_attempts"],
            "past_email_success": customer["past_email_success"],
            "past_email_attempts": customer["past_email_attempts"],
            "past_call_success": customer["past_call_success"],
            "past_call_attempts": customer["past_call_attempts"],
            "past_opt_outs": customer["past_opt_outs"],
            "intervention_used": chosen_intervention,
            "contacted": contacted,
            "recovered": recovered,
            "amount_recovered": amount_recovered,
            "recovery_time_hours": recovery_time_hours if recovery_time_hours is not None else "",
            "churn_or_annoyance_flag": churn_flag,
        })

    return rows, customers


def write_csv(rows):
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    fieldnames = list(rows[0].keys())
    with open(OUTPUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    rows, customers = generate()
    write_csv(rows)

    recovered_count = sum(1 for r in rows if r["recovered"])
    contacted_count = sum(1 for r in rows if r["contacted"])
    none_count = sum(1 for r in rows if r["intervention_used"] == "none")
    churn_count = sum(1 for r in rows if r["churn_or_annoyance_flag"])

    print(f"Generated {len(rows)} records for {len(customers)} customers")
    print(f"Written to: {OUTPUT_PATH}")
    print(f"Overall recovery rate: {recovered_count/len(rows):.2%}")
    print(f"Contacted: {contacted_count} ({contacted_count/len(rows):.2%}) | Left alone (none): {none_count}")
    print(f"Annoyance/churn flags: {churn_count} ({churn_count/len(rows):.2%})")

    small_insuff = [r for r in rows if r["failure_reason"] == "insufficient_funds" and r["amount"] < 1000 and r["intervention_used"] == "none"]
    if small_insuff:
        rate = sum(1 for r in small_insuff if r["recovered"]) / len(small_insuff)
        print(f"Sanity check -- small insufficient_funds, no contact, recovery rate: {rate:.2%} (expect high)")