/**
 * SummaryCards.jsx
 * Top-of-page metric strip. Deliberately NOT the generic "rounded card with
 * soft shadow" pattern -- these are ledger-style blocks: hairline top rule,
 * label above, big tabular-mono number below, no shadow, minimal radius.
 */

function formatRupees(value) {
  return `₹${Number(value).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

function Card({ label, value, accent }) {
  const accentClass =
    accent === "gain" ? "text-gain" : accent === "wait" ? "text-wait" : "text-text";

  return (
    <div className="border-t-2 border-line bg-surface px-5 py-4">
      <p className="text-sm text-muted mb-2">{label}</p>
      <p className={`font-mono text-3xl font-medium ${accentClass}`}>{value}</p>
    </div>
  );
}

export default function SummaryCards({ summary }) {
  if (!summary) return null;

  return (
    <div className="grid grid-cols-2 gap-px bg-line md:grid-cols-5">
      <Card label="Payments analyzed" value={summary.payments_analyzed} />
      <Card label="Revenue at risk" value={formatRupees(summary.revenue_at_risk)} />
      <Card
        label="Expected recovery"
        value={formatRupees(summary.expected_recovery)}
        accent="gain"
      />
      <Card
        label="Expected net value"
        value={formatRupees(summary.expected_net_value)}
        accent="gain"
      />
      <Card
        label="Interventions avoided"
        value={summary.interventions_avoided}
        accent="wait"
      />
    </div>
  );
}