/**
 * ComparisonPanel.jsx
 * The main demo centerpiece: runs POST /simulate and shows Baseline vs
 * Recovery IQ side by side on the SAME synthetic batch, plus the three
 * headline numbers (net value lift, contacts avoided %, cost delta).
 *
 * Layout deliberately avoids a "vs card battle" cliche -- it's a two-column
 * ledger under one shared set of row labels, so every number lines up and
 * the eye can compare row-by-row rather than card-by-card.
 */

import { useState } from "react";
import { api } from "../api/client";

function formatRupees(value) {
  const sign = value < 0 ? "-" : "";
  return `${sign}₹${Math.abs(Number(value)).toLocaleString("en-IN", {
    maximumFractionDigits: 0,
  })}`;
}

function StrategyColumn({ title, data, highlight }) {
  const rows = [
    { label: "Revenue recovered", value: formatRupees(data.revenue_recovered) },
    { label: "Intervention cost", value: formatRupees(data.intervention_cost) },
    { label: "Contacts made", value: `${data.contacts_made} of ${data.payments}` },
    {
      label: "Expected churn / annoyance cost",
      value: formatRupees(data.expected_churn_annoyance),
    },
  ];

  return (
    <div className={highlight ? "border border-gain/40 bg-gain-soft/30" : "border border-line bg-surface"}>
      <div className={`px-5 py-3 border-b ${highlight ? "border-gain/40" : "border-line"}`}>
        <p className={`text-sm font-medium ${highlight ? "text-gain" : "text-muted"}`}>{title}</p>
      </div>
      <div>
        {rows.map((row) => (
          <div
            key={row.label}
            className="flex items-baseline justify-between border-b border-line-soft px-5 py-3 last:border-0"
          >
            <span className="text-sm text-muted">{row.label}</span>
            <span className="font-mono text-sm">{row.value}</span>
          </div>
        ))}
        <div className="flex items-baseline justify-between px-5 py-4">
          <span className="text-sm font-medium">Net value</span>
          <span className={`font-mono text-xl font-medium ${highlight ? "text-gain" : "text-text"}`}>
            {formatRupees(data.net_value)}
          </span>
        </div>
      </div>
    </div>
  );
}

export default function ComparisonPanel({ onRun }) {
  const [result, setResult] = useState(null);
  const [running, setRunning] = useState(false);
  const [batchSize, setBatchSize] = useState(20);
  const [error, setError] = useState(null);

  async function handleRun() {
    setRunning(true);
    setError(null);
    try {
      const data = await api.simulate(batchSize);
      setResult(data);
      if (onRun) await onRun();
    } catch (err) {
      setError(err.message);
    } finally {
      setRunning(false);
    }
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-sm font-medium text-muted">Baseline vs Recovery IQ</h2>
        <div className="flex items-center gap-3">
          <label className="text-sm text-muted">
            Batch size
            <input
              type="number"
              min="1"
              max="200"
              value={batchSize}
              onChange={(e) => setBatchSize(Number(e.target.value) || 1)}
              className="ml-2 w-16 border border-line bg-surface px-2 py-1 font-mono text-sm text-text"
            />
          </label>
          <button
            onClick={handleRun}
            disabled={running}
            className="border border-line bg-surface px-4 py-2 text-sm font-medium hover:bg-surface-raised disabled:opacity-50"
          >
            {running ? "Running…" : "Run comparison"}
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 border border-cost/40 bg-cost-soft px-4 py-3 text-sm text-cost">
          {error}
        </div>
      )}

      {!result && !error && (
        <div className="border border-line bg-surface px-6 py-10 text-center">
          <p className="text-muted">
            Run a comparison to see Baseline vs Recovery IQ on the same synthetic batch.
          </p>
        </div>
      )}

      {result && (
        <div>
          <div className="mb-4 grid grid-cols-3 gap-px bg-line">
            <div className="bg-ink px-5 py-4">
              <p className="text-sm text-muted mb-2">Net value lift</p>
              <p
                className={`font-mono text-3xl font-medium ${
                  result.net_value_lift >= 0 ? "text-gain" : "text-cost"
                }`}
              >
                {result.net_value_lift >= 0 ? "+" : ""}
                {formatRupees(result.net_value_lift)}
              </p>
            </div>
            <div className="bg-ink px-5 py-4">
              <p className="text-sm text-muted mb-2">Contacts avoided</p>
              <p className="font-mono text-3xl font-medium text-wait">
                {result.contacts_avoided_pct}%
              </p>
            </div>
            <div className="bg-ink px-5 py-4">
              <p className="text-sm text-muted mb-2">Intervention cost delta</p>
              <p
                className={`font-mono text-3xl font-medium ${
                  result.intervention_cost_saved >= 0 ? "text-gain" : "text-muted"
                }`}
              >
                {result.intervention_cost_saved >= 0 ? "+" : ""}
                {formatRupees(result.intervention_cost_saved)}
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <StrategyColumn title="Baseline — contact everyone" data={result.baseline} />
            <StrategyColumn title="Recovery IQ" data={result.recovery_iq} highlight />
          </div>
        </div>
      )}
    </div>
  );
}