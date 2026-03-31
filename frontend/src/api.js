const BASE = "/api";

async function req(path, options = {}) {
  const res = await fetch(BASE + path, { credentials: "include", ...options });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

export const api = {
  getMe: () => req("/auth/me"),
  setWallet: (wallet_address) =>
    req("/auth/wallet", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ wallet_address }),
    }),
  getBalance: () => req("/auth/balance"),
  getInventory: () => req("/inventory"),
  createDeposit: (asset_id) =>
    req("/deposit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ asset_id }),
    }),
  getDeposit: (id) => req(`/deposit/${id}`),
  createWithdrawal: (trade_url) =>
    req("/withdraw", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ trade_url }),
    }),
  getWithdrawal: (id) => req(`/withdraw/${id}`),
  getHistory: () => req("/history"),
};
