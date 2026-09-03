/**
 * AskBox.jsx
 * Interactive Q&A about one transaction's decision. Unlike the fixed-format
 * explanation shown elsewhere, this lets the person type any question and
 * get a real LLM-generated answer, grounded in the actual stored numbers
 * for that transaction -- never re-running the decision engine.
 */

import { useState } from "react";
import { api } from "../api/client";

export default function AskBox({ transactionId }) {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState(null);
  const [source, setSource] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function handleAsk() {
    if (!question.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const result = await api.ask(transactionId, question.trim());
      setAnswer(result.answer);
      setSource(result.source);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleAsk();
    }
  }

  return (
    <section className="mb-6 border border-line bg-surface px-4 py-4">
      <p className="mb-2 text-sm text-muted">Ask about this decision</p>

      <div className="flex gap-2">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="e.g. Why not use voice call instead?"
          className="flex-1 border border-line bg-ink px-3 py-2 text-sm text-text placeholder:text-faint"
        />
        <button
          onClick={handleAsk}
          disabled={loading || !question.trim()}
          className="border border-line bg-surface-raised px-4 py-2 text-sm font-medium hover:bg-surface disabled:opacity-50"
        >
          {loading ? "Asking…" : "Ask"}
        </button>
      </div>

      {error && <p className="mt-3 text-sm text-cost">{error}</p>}

      {answer && (
        <div className="mt-3 border-t border-line-soft pt-3">
          <div className="mb-1 flex items-center justify-between">
            <span className="text-xs text-faint">Answer</span>
            {source === "llm" ? (
              <span className="rounded-sm border border-purple/40 bg-purple-soft px-1.5 py-0.5 text-[10px] font-medium text-purple">
                AI explanation
              </span>
            ) : (
              <span className="rounded-sm border border-line px-1.5 py-0.5 text-[10px] font-medium text-faint">
                Unavailable — fallback
              </span>
            )}
          </div>
          <p className="text-sm text-text">{answer}</p>
        </div>
      )}
    </section>
  );
}