/**
 * OpportunitiesTable.jsx
 * The "Recovery Opportunities" ledger: one row per transaction, showing
 * what Recovery IQ decided and why. Hairline row dividers instead of card
 * chrome -- this is meant to read like a statement, not a card grid.
 */

function formatRupees(value) {
  return `₹${Number(value).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

function ActionBadge({ action }) {
  const isPassive = action === "wait" || action === "do_nothing";
  const colorClass = isPassive
    ? "text-wait border-wait/40 bg-wait-soft"
    : "text-gain border-gain/40 bg-gain-soft";
  const label = action.replace("_", " ");

  return (
    <span
      className={`inline-block rounded-sm border px-2 py-0.5 text-xs font-medium ${colorClass}`}
    >
      {label}
    </span>
  );
}

function FailureLabel({ reason }) {
  return <span className="text-muted">{reason.replace(/_/g, " ")}</span>;
}

/**
 * Shows WHAT the execution step actually did, not just whether it "did
 * something" (which is true for almost every row, since do_nothing is
 * mathematically rare -- see engine.py, WAIT can only lose to do_nothing
 * if self-cure probability is exactly 0%). This is more honest and more
 * useful: it distinguishes customer-facing outreach from a silent retry
 * from passive monitoring, all real, meaningfully different outcomes.
 */
function StatusBadge({ action }) {
  const CUSTOMER_FACING = ["whatsapp", "email", "voice", "discount", "human_followup"];

  if (CUSTOMER_FACING.includes(action)) {
    return <span className="text-xs text-gain">Contacted</span>;
  }
  if (action === "retry") {
    return <span className="text-xs text-wait">Silent retry</span>;
  }
  if (action === "wait") {
    return <span className="text-xs text-wait">Monitoring</span>;
  }
  return <span className="text-xs text-faint">Closed</span>;
}

/**
 * Shows whether the reason text came from the optional LLM layer or the
 * always-available rule-based fallback. Purely informational -- both are
 * treated as equally valid explanations, this just labels the source
 * honestly rather than implying every explanation was AI-written.
 */
function ExplanationSourceBadge({ source }) {
  if (source === "llm") {
    return (
      <span className="inline-block rounded-sm border border-purple/40 bg-purple-soft px-1.5 py-0.5 text-[10px] font-medium text-purple">
        AI explanation
      </span>
    );
  }
  return (
    <span className="inline-block rounded-sm border border-line px-1.5 py-0.5 text-[10px] font-medium text-faint">
      Rule-based
    </span>
  );
}

export default function OpportunitiesTable({ rows, onSelectTransaction }) {
  if (!rows || rows.length === 0) {
    return (
      <div className="border border-line bg-surface px-6 py-10 text-center">
        <p className="text-muted">
          No transactions analyzed yet. Run a simulation to populate this table.
        </p>
      </div>
    );
  }

  return (
    <div className="border border-line bg-surface">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-line text-muted">
            <th className="px-4 py-3 font-normal">Customer</th>
            <th className="px-4 py-3 font-normal">Amount</th>
            <th className="px-4 py-3 font-normal">Failure</th>
            <th className="px-4 py-3 font-normal">Best action</th>
            <th className="px-4 py-3 font-normal">Status</th>
            <th className="px-4 py-3 font-normal">Probability</th>
            <th className="px-4 py-3 font-normal">Expected net value</th>
            <th className="px-4 py-3 font-normal">Reason</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.transaction_id}
              onClick={() => onSelectTransaction && onSelectTransaction(row.transaction_id)}
              className="cursor-pointer border-b border-line-soft last:border-0 hover:bg-surface-raised"
            >
              <td className="px-4 py-3">
                <div>{row.customer_name}</div>
                <div className="text-xs text-faint">{row.customer_segment}</div>
              </td>
              <td className="px-4 py-3 font-mono">{formatRupees(row.amount)}</td>
              <td className="px-4 py-3">
                <FailureLabel reason={row.failure_reason} />
              </td>
              <td className="px-4 py-3">
                <ActionBadge action={row.selected_action} />
              </td>
              <td className="px-4 py-3">
                <StatusBadge action={row.selected_action} />
              </td>
              <td className="px-4 py-3 font-mono text-muted">
                {(row.recovery_probability * 100).toFixed(0)}%
              </td>
              <td className="px-4 py-3 font-mono text-gain">
                {formatRupees(row.expected_net_value)}
              </td>
              <td className="max-w-xs px-4 py-3 text-xs text-muted">
                <ExplanationSourceBadge source={row.explanation_source} />
                <div className="mt-1">{row.reason}</div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}