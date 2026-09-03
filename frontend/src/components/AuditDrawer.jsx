/**
 * AuditDrawer.jsx
 * Side panel showing the full decision trail for one transaction:
 * every option the ML model scored, which one was picked, and why.
 * This is the direct answer to "can I see why it made that call?"
 */

import { useEffect, useState } from "react";
import { api } from "../api/client";
import AskBox from "./AskBox";

function formatRupees(value) {
  return `₹${Number(value).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

/**
 * engine.py prefixes the reason with "Active contact blocked (reason1;
 * reason2). " when a guardrail fired. Split that out so it can be shown
 * as its own distinct callout instead of buried in a paragraph.
 */
function splitGuardrailReason(reason) {
  const prefix = "Active contact blocked (";
  if (!reason || !reason.startsWith(prefix)) {
    return { guardrails: [], economicReason: reason };
  }
  const closeIdx = reason.indexOf("). ");
  if (closeIdx === -1) {
    return { guardrails: [], economicReason: reason };
  }
  const inside = reason.slice(prefix.length, closeIdx);
  const guardrails = inside.split("; ").map((s) => s.trim());
  const economicReason = reason.slice(closeIdx + 3);
  return { guardrails, economicReason };
}

export default function AuditDrawer({ transactionId, onClose }) {
  const [audit, setAudit] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!transactionId) return;
    setLoading(true);
    setError(null);
    api
      .audit(transactionId)
      .then(setAudit)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [transactionId]);

  if (!transactionId) return null;

  const latestDecision = audit?.decisions?.[audit.decisions.length - 1];
  const predictions = audit?.predictions || [];

  const latestByAction = {};
  predictions.forEach((p) => {
    latestByAction[p.intervention_name] = p.recovery_probability;
  });
  const sortedActions = Object.entries(latestByAction).sort((a, b) => b[1] - a[1]);

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative h-full w-full max-w-md overflow-y-auto border-l border-line bg-surface">
        <div className="flex items-center justify-between border-b border-line px-6 py-4">
          <h3 className="text-sm font-medium">Transaction #{transactionId} — audit trail</h3>
          <button onClick={onClose} className="text-muted hover:text-text">
            ✕
          </button>
        </div>

        <div className="px-6 py-5">
          {loading && <p className="text-sm text-muted">Loading…</p>}
          {error && <p className="text-sm text-cost">{error}</p>}

          {audit && (
            <>
              <section className="mb-6">
                <p className="mb-2 text-sm text-muted">Transaction</p>
                <div className="space-y-1 font-mono text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted">Amount</span>
                    <span>{formatRupees(audit.transaction.amount)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted">Failure reason</span>
                    <span>{audit.transaction.failure_reason.replace(/_/g, " ")}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted">Payment channel</span>
                    <span>{audit.transaction.payment_channel}</span>
                  </div>
                </div>
              </section>

              {latestDecision && (() => {
                const { guardrails, economicReason } = splitGuardrailReason(latestDecision.reason);
                return (
                  <section className="mb-6 border border-gain/40 bg-gain-soft/30 px-4 py-4">
                    <p className="mb-1 text-sm text-muted">Decision explanation</p>
                    <p className="mb-2 font-mono text-lg text-gain">
                      {latestDecision.selected_action.replace("_", " ")}
                    </p>

                    {guardrails.length > 0 && (
                      <div className="mb-3 border border-cost/40 bg-cost-soft px-3 py-2">
                        <p className="mb-1 text-xs font-medium text-cost">
                          Guardrail triggered — active contact blocked
                        </p>
                        <ul className="list-inside list-disc text-xs text-cost">
                          {guardrails.map((g) => (
                            <li key={g}>{g}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    <p className="text-sm text-muted">{economicReason}</p>
                    <div className="mt-3 space-y-1 font-mono text-xs text-muted">
                      <div className="flex justify-between">
                        <span>Expected recovery</span>
                        <span>{formatRupees(latestDecision.expected_recovery)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Intervention cost</span>
                        <span>{formatRupees(latestDecision.intervention_cost)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Customer impact cost</span>
                        <span>{formatRupees(latestDecision.expected_customer_impact_cost)}</span>
                      </div>
                      <div className="flex justify-between text-gain">
                        <span>Net value</span>
                        <span>{formatRupees(latestDecision.expected_net_value)}</span>
                      </div>
                    </div>
                  </section>
                );
                            })()}

              <AskBox transactionId={transactionId} />

              <section>
                <p className="mb-2 text-sm text-muted">All options the model scored</p>
                <div className="space-y-1">
                  {sortedActions.map(([action, probability]) => (
                    <div
                      key={action}
                      className="flex items-center justify-between border-b border-line-soft py-2 last:border-0"
                    >
                      <span className="text-sm">{action.replace("_", " ")}</span>
                      <span className="font-mono text-sm text-muted">
                        {(probability * 100).toFixed(0)}%
                      </span>
                    </div>
                  ))}
                </div>
              </section>
            </>
          )}
        </div>
      </div>
    </div>
  );
}