/**
 * client.js
 * Thin wrapper around fetch for talking to the Recovery IQ backend.
 * All functions return parsed JSON or throw with a readable message.
 *
 * BASE_URL comes from VITE_API_BASE_URL if set (used in production builds
 * pointing at a deployed backend), otherwise falls back to localhost for
 * local development -- so `npm run dev` keeps working with zero config.
 */

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      // ignore JSON parse failure, fall back to statusText
    }
    throw new Error(`${res.status} ${detail}`);
  }
  return res.json();
}

export const api = {
  health: () => request("/health"),

  createTransaction: (payload) =>
    request("/transactions", { method: "POST", body: JSON.stringify(payload) }),

  analyze: (transactionId) =>
    request(`/analyze/${transactionId}`, { method: "POST" }),

  recoveryOptions: (transactionId) =>
    request(`/recovery-options/${transactionId}`),

  decisions: () => request("/decisions"),

  opportunities: () => request("/opportunities"),

  audit: (transactionId) => request(`/audit/${transactionId}`),

  dashboard: () => request("/dashboard"),

  simulate: (batchSize = 20) =>
    request("/simulate", {
      method: "POST",
      body: JSON.stringify({ batch_size: batchSize }),
    }),

  allocate: (batchSize, budgetCap) =>
    request("/allocate",{
      method: "POST",
      body: JSON.stringify({ batch_size: batchSize, budget_cap: budgetCap }),
    }),

  modelQuality: () => request("/model-quality"),
};