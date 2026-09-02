/**
 * RecoveryBudget.jsx
 * UI for the budget-constrained allocator. Given a fixed ₹ spend cap,
 * shows which transactions get funded vs deferred to maximize total
 * value within that budget -- a genuinely different question than the
 * per-transaction EV engine answers alone.
 */

import { useState } from "react";
import { api } from "../api/client";

function formatRupees(value) {
  return `₹${Number(value).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

export default function RecoveryBudget() {
  const [batchSize, setBatchSize] = useState(30);
  const [budgetCap, setBudgetCap] = useState(500);
  const [result, setResult] = useState(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState(null);

  async function handleRun() {
    setRunning(true);
    setError(null);
    try {
      const data = await api.allocate(batchSize, budgetCap);
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setRunning(false);
    }
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-sm font-medium text-muted">
          Recovery budget — what if we can't afford to contact everyone?
        </h2>
        <div className="flex items-center gap-3">
          <label className="text-sm text-muted">
            Batch
            <input
              type="number"
              min="1"
              max="200"
              value={batchSize}
              onChange={(e) => setBatchSize(Number(e.target.value) || 1)}
              className="ml-2 w-16 border border-line bg-surface px-2 py-1 font-mono text-sm text-text"
            />
          </label>
          <label className="text-sm text-muted">
            Budget ₹
            <input
              type="number"
              min="0"
              value={budgetCap}
              onChange={(e) => setBudgetCap(Number(e.target.value) || 0)}
              className="ml-2 w-24 border border-line bg-surface px-2 py-1 font-mono text-sm text-text"
            />
          </label>
          <button
            onClick={handleRun}
            disabled={running}
            className="border border-line bg-surface px-4 py-2 text-sm font-medium hover:bg-surface-raised disabled:opacity-50"
          >
            {running ? "Allocating…" : "Allocate budget"}
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
            Set a budget cap and allocate — the engine funds the highest-value-per-rupee
            opportunities first and defers the rest to WAIT.
          </p>
        </div>
      )}

      {result && (
        <div>
          <div className="mb-4 grid grid-cols-4 gap-px bg-line">
            <div className="bg-ink px-5 py-4">
              <p className="text-sm text-muted mb-2">Funded</p>
              <p className="font-mono text-2xl font-medium text-gain">{result.transactions_funded}</p>
            </div>
            <div className="bg-ink px-5 py-4">
              <p className="text-sm text-muted mb-2">Deferred</p>
              <p className="font-mono text-2xl font-medium text-wait">{result.transactions_deferred}</p>
            </div>
            <div className="bg-ink px-5 py-4">
              <p className="text-sm text-muted mb-2">Budget spent</p>
              <p className="font-mono text-2xl font-medium">
                {formatRupees(result.budget_spent)} / {formatRupees(result.budget_cap)}
              </p>
            </div>
            <div className="bg-ink px-5 py-4">
              <p className="text-sm text-muted mb-2">Value lost to cap</p>
              <p className="font-mono text-2xl font-medium text-cost">
                {formatRupees(result.value_lost_to_budget_cap)}
              </p>
            </div>
          </div>

          <div className="border border-line bg-surface px-5 py-4">
            <div className="flex items-baseline justify-between border-b border-line-soft py-2">
              <span className="text-sm text-muted">Unconstrained total net value (unlimited budget)</span>
              <span className="font-mono text-sm">{formatRupees(result.unconstrained_total_net_value)}</span>
            </div>
            <div className="flex items-baseline justify-between py-2">
              <span className="text-sm font-medium">Achieved within this budget</span>
              <span className="font-mono text-lg text-gain">
                {formatRupees(result.budget_constrained_total_net_value)}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}