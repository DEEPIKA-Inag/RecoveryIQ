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

// Free-tier hosts (e.g. Render) spin down when idle and can take 20-60s to
// wake back up on the next request. A cold container refuses the connection
// outright, which surfaces as a network-level fetch failure (TypeError),
// NOT an HTTP error response. We retry only that specific failure mode --
// a real 4xx/5xx from a server that's actually responding fails immediately,
// since retrying won't fix a genuine error.
const COLD_START_RETRY_DELAYS_MS = [3000, 6000, 12000, 20000]; // ~41s total budget

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function request(path, options = {}) {
  let lastNetworkError = null;

  for (let attempt = 0; attempt <= COLD_START_RETRY_DELAYS_MS.length; attempt++) {
    let res;
    try {
      res = await fetch(`${BASE_URL}${path}`, {
        headers: { "Content-Type": "application/json" },
        ...options,
      });
    } catch (networkErr) {
      // fetch() throws only on network-level failure (connection refused,
      // DNS failure, CORS block, etc) -- exactly what a cold/sleeping
      // backend looks like before it's finished booting.
      lastNetworkError = networkErr;
      if (attempt < COLD_START_RETRY_DELAYS_MS.length) {
        await sleep(COLD_START_RETRY_DELAYS_MS[attempt]);
        continue;
      }
      throw new Error(
        "Could not reach the server after several attempts. It may be waking up from sleep -- try again in a moment."
      );
    }

    if (!res.ok) {
      // Server responded (it's awake) but with an error status -- this is
      // a real error, not a cold-start symptom, so fail immediately.
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

  // unreachable, but keeps linters happy
  throw lastNetworkError;
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
    request("/allocate", {
      method: "POST",
      body: JSON.stringify({ batch_size: batchSize, budget_cap: budgetCap }),
    }),

    modelQuality: () => request("/model-quality"),

  ask: (transactionId, question) =>
    request(`/ask/${transactionId}`, {
      method: "POST",
      body: JSON.stringify({ question }),
    }),
};