/**
 * ModelReliability.jsx
 * Answers "can we trust your probabilities?" -- shows the calibration
 * check comparing predicted probability vs actual outcome on held-out
 * data the model never saw during training. Collapsed by default.
 */

import { useState } from "react";
import { api } from "../api/client";

export default function ModelReliability() {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function handleOpen() {
    const next = !open;
    setOpen(next);
    if (next && !data) {
      setLoading(true);
      setError(null);
      try {
        const result = await api.modelQuality();
        setData(result);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
  }

  return (
    <div className="border border-line bg-surface">
      <button
        onClick={handleOpen}
        className="flex w-full items-center justify-between px-5 py-3 text-left"
      >
        <span className="text-sm font-medium text-muted">
          Model reliability — is the 61% real?
        </span>
        <span className="text-muted">{open ? "−" : "+"}</span>
      </button>

      {open && (
        <div className="border-t border-line px-5 py-4">
          {loading && <p className="text-sm text-muted">Checking calibration on held-out data…</p>}
          {error && <p className="text-sm text-cost">{error}</p>}

          {data && (
            <>
              <p className="mb-4 text-sm text-muted">
                When the model says "70% chance of recovery," does it actually recover ~70% of
                the time? Tested on data the model never saw during training.
              </p>

              <div className="mb-3 grid grid-cols-4 gap-3 text-xs text-muted">
                <span>Predicted range</span>
                <span className="text-right">Sample size</span>
                <span className="text-right">Predicted</span>
                <span className="text-right">Actual</span>
              </div>
              <div className="space-y-1">
                {data.bins.map((bin) => {
                  const gapMagnitude = Math.abs(bin.gap);
                  const gapColor =
                    gapMagnitude < 0.08 ? "text-gain" : gapMagnitude < 0.2 ? "text-wait" : "text-cost";
                  return (
                    <div
                      key={bin.range_label}
                      className="grid grid-cols-4 gap-3 border-b border-line-soft py-2 font-mono text-sm last:border-0"
                    >
                      <span>{bin.range_label}</span>
                      <span className="text-right text-muted">n={bin.sample_count}</span>
                      <span className="text-right">{(bin.mean_predicted * 100).toFixed(0)}%</span>
                      <span className={`text-right ${gapColor}`}>
                        {(bin.actual_recovery_rate * 100).toFixed(0)}%
                      </span>
                    </div>
                  );
                })}
              </div>

              <div className="mt-4 border-t border-line pt-3">
                <span className="text-sm text-muted">Weighted calibration error: </span>
                <span className="font-mono text-sm text-gain">
                  {(data.weighted_calibration_error * 100).toFixed(1)}%
                </span>
                <span className="ml-2 text-xs text-faint">(lower is better; under ~8% is solid for a demo model)</span>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}