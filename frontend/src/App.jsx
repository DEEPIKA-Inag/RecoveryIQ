import { useEffect, useState, useCallback } from "react";
import { api } from "./api/client";
import SummaryCards from "./components/SummaryCards";
import OpportunitiesTable from "./components/OpportunitiesTable";
import ComparisonPanel from "./components/ComparisonPanel";
import AuditDrawer from "./components/AuditDrawer";
import NetValueChart from "./components/NetValueChart";
import ModelReliability from "./components/ModelReliability";
import RecoveryBudget from "./components/RecoveryBudget";

export default function App() {
  const [connection, setConnection] = useState("checking");
  const [summary, setSummary] = useState(null);
  const [opportunities, setOpportunities] = useState([]);
  const [error, setError] = useState(null);
  const [selectedTransactionId, setSelectedTransactionId] = useState(null);

  const loadData = useCallback(async () => {
    try {
      const [summaryData, oppsData] = await Promise.all([
        api.dashboard(),
        api.opportunities(),
      ]);
      setSummary(summaryData);
      setOpportunities(oppsData);
      setError(null);
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => {
    api
      .health()
      .then(() => {
        setConnection("connected");
        loadData();
      })
      .catch(() => setConnection("offline"));
  }, [loadData]);

  return (
    <div className="min-h-screen bg-ink text-text font-sans">
      <header className="border-b border-line px-8 py-5">
        <div className="flex items-baseline justify-between">
          <h1 className="text-lg font-semibold tracking-tight">Recovery IQ</h1>
          <span className="text-sm text-muted">Economic decision engine for payment recovery</span>
        </div>
      </header>

      <main className="px-8 py-10">
        {connection === "offline" && (
          <div className="mb-6 border border-cost/40 bg-cost-soft px-4 py-3 text-sm text-cost">
            Backend offline. Make sure the FastAPI server is running at http://127.0.0.1:8000
          </div>
        )}

        {error && (
          <div className="mb-6 border border-cost/40 bg-cost-soft px-4 py-3 text-sm text-cost">
            {error}
          </div>
        )}

        <p className="mb-6 text-sm text-muted">
          {summary ? `${summary.payments_analyzed} payments analyzed so far` : "No data yet"}
        </p>

        <div className="mb-10">
          <SummaryCards summary={summary} />
        </div>

        <div className="mb-12">
          <h2 className="mb-3 text-sm font-medium text-muted">Net value by action</h2>
          <NetValueChart rows={opportunities} />
        </div>

        <div className="mb-4">
          <ModelReliability />
        </div>

        <div className="mb-12">
          <ComparisonPanel onRun={loadData} />
        </div>

        <div className="mb-12">
          <RecoveryBudget />
        </div>

        <div>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-medium text-muted">Recovery opportunities</h2>
            <div className="flex items-center gap-4">
              <span className="text-xs text-faint">Click a row to see the full audit trail</span>
              <button
                onClick={loadData}
                className="text-sm text-muted underline decoration-line underline-offset-4 hover:text-text"
              >
                Refresh
              </button>
            </div>
          </div>
          <OpportunitiesTable rows={opportunities} onSelectTransaction={setSelectedTransactionId} />
        </div>
      </main>

      <AuditDrawer
        transactionId={selectedTransactionId}
        onClose={() => setSelectedTransactionId(null)}
      />
    </div>
  );
}