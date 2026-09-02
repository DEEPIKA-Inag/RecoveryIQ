/**
 * NetValueChart.jsx
 * Horizontal bar chart: total expected net value grouped by selected action.
 * Built as plain SVG/CSS -- deliberately no charting library dependency,
 * since one less package to install correctly is one less thing that can
 * break right before a demo. Aggregates client-side from the same
 * `opportunities` data the table already has, so no extra API call.
 */

function formatRupees(value) {
  return `₹${Number(value).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

const PASSIVE_ACTIONS = new Set(["wait", "do_nothing"]);

function aggregateByAction(rows) {
  const totals = {};
  rows.forEach((row) => {
    const key = row.selected_action;
    totals[key] = (totals[key] || 0) + row.expected_net_value;
  });
  return Object.entries(totals)
    .map(([action, value]) => ({ action, value }))
    .sort((a, b) => b.value - a.value);
}

export default function NetValueChart({ rows }) {
  if (!rows || rows.length === 0) {
    return (
      <div className="border border-line bg-surface px-6 py-10 text-center">
        <p className="text-muted">No data yet. Run a comparison to populate this chart.</p>
      </div>
    );
  }

  const data = aggregateByAction(rows);
  const maxValue = Math.max(...data.map((d) => d.value), 1);

  return (
    <div className="border border-line bg-surface px-6 py-5">
      <div className="space-y-3">
        {data.map((d) => {
          const widthPct = Math.max(2, (d.value / maxValue) * 100);
          const isPassive = PASSIVE_ACTIONS.has(d.action);
          const barColor = isPassive ? "bg-wait" : "bg-gain";

          return (
            <div key={d.action} className="flex items-center gap-3">
              <span className="w-32 shrink-0 text-sm text-muted">
                {d.action.replace("_", " ")}
              </span>
              <div className="h-6 flex-1 bg-line-soft">
                <div
                  className={`h-6 ${barColor}`}
                  style={{ width: `${widthPct}%` }}
                />
              </div>
              <span className="w-24 shrink-0 text-right font-mono text-sm">
                {formatRupees(d.value)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}