import { initI18n, t, setLocale, getLocale, SUPPORTED_LOCALES } from "./i18n/index.js";
import { api } from "./api.js";
import { connectMetaMask } from "./metamask.js";

// ── State ────────────────────────────────────────────────────────────────────
let state = {
  user: null,       // { steam_id, wallet_address, created_at }
  balance: 0,
  inventory: [],
  depositId: null,
  withdrawalId: null,
  activeModal: null, // "deposit" | "withdraw" | null
  selectedAsset: null,
  pollingTimer: null,
};

// ── DOM refs ─────────────────────────────────────────────────────────────────
const $ = (id) => document.getElementById(id);

// ── Render ───────────────────────────────────────────────────────────────────
function renderAll() {
  renderNav();
  renderHero();
  renderInventory();
}

function renderNav() {
  const loginBtn = $("btn-login");
  const walletBtn = $("btn-wallet");
  const logoutBtn = $("btn-logout");
  const balanceEl = $("nav-balance");
  const walletEl = $("nav-wallet");

  if (state.user) {
    loginBtn.classList.add("hidden");
    logoutBtn.classList.remove("hidden");
    balanceEl.classList.remove("hidden");
    balanceEl.textContent = `${state.balance} P250SD`;

    if (state.user.wallet_address) {
      walletBtn.classList.add("hidden");
      walletEl.classList.remove("hidden");
      const a = state.user.wallet_address;
      walletEl.textContent = a.slice(0, 6) + "..." + a.slice(-4);
    } else {
      walletBtn.classList.remove("hidden");
      walletEl.classList.add("hidden");
      walletBtn.textContent = t("nav.connect_metamask");
    }
  } else {
    loginBtn.classList.remove("hidden");
    loginBtn.textContent = t("nav.login_steam");
    walletBtn.classList.add("hidden");
    walletEl.classList.add("hidden");
    logoutBtn.classList.add("hidden");
    balanceEl.classList.add("hidden");
  }
}

function renderHero() {
  $("hero-title").textContent = t("hero.title");
  $("hero-subtitle").textContent = t("hero.subtitle");
  $("hero-deposit-btn").textContent = t("hero.deposit_btn");
  $("hero-withdraw-btn").textContent = t("hero.withdraw_btn");

  const canDeposit = state.user && state.user.wallet_address;
  const canWithdraw = state.user && state.user.wallet_address && state.balance > 0;

  $("hero-deposit-btn").disabled = !canDeposit;
  $("hero-withdraw-btn").disabled = !canWithdraw;
}

function renderInventory() {
  const section = $("inventory-section");
  const grid = $("inventory-grid");
  const emptyMsg = $("inventory-empty");
  const privateMsg = $("inventory-private");

  if (!state.user) {
    section.classList.add("hidden");
    return;
  }

  section.classList.remove("hidden");
  $("inventory-title").textContent = t("inventory.title");

  grid.innerHTML = "";
  emptyMsg.classList.add("hidden");
  privateMsg.classList.add("hidden");

  if (state.inventoryError === "private") {
    privateMsg.textContent = t("inventory.private");
    privateMsg.classList.remove("hidden");
    return;
  }

  if (state.inventory.length === 0) {
    emptyMsg.textContent = t("inventory.empty");
    emptyMsg.classList.remove("hidden");
    return;
  }

  state.inventory.forEach((item) => {
    const card = document.createElement("div");
    card.className = "skin-card";
    card.innerHTML = `
      <img src="${item.icon_url}" alt="${item.name}" />
      <div class="skin-card-name">${item.name}</div>
      <div class="skin-card-tag ${item.tradable ? "tradable" : "not-tradable"}">
        ${item.tradable ? t("inventory.tradable") : t("inventory.not_tradable")}
      </div>
      <button class="btn-primary skin-deposit-btn" data-asset="${item.asset_id}" ${!item.tradable ? "disabled" : ""}>
        ${t("inventory.deposit_btn")}
      </button>
    `;
    grid.appendChild(card);
  });
}

// ── Modal: Deposit ───────────────────────────────────────────────────────────
function openDepositModal(assetId) {
  state.selectedAsset = assetId;
  const m = $("deposit-modal");
  $("deposit-modal-title").textContent = t("deposit_modal.title");
  $("deposit-step1").textContent = t("deposit_modal.step1");
  $("deposit-step2").textContent = t("deposit_modal.step2");
  $("deposit-confirm-btn").textContent = t("deposit_modal.confirm_btn");
  $("deposit-status").textContent = "";
  $("deposit-status").className = "status-bar";
  $("deposit-confirm-btn").disabled = false;
  m.classList.remove("hidden");
  $("modal-overlay").classList.remove("hidden");
}

function closeModal() {
  $("deposit-modal").classList.add("hidden");
  $("withdraw-modal").classList.add("hidden");
  $("modal-overlay").classList.add("hidden");
  if (state.pollingTimer) clearInterval(state.pollingTimer);
}

async function submitDeposit() {
  const btn = $("deposit-confirm-btn");
  btn.disabled = true;
  setDepositStatus(t("deposit_modal.status_waiting"), "pending");

  try {
    const dep = await api.createDeposit(state.selectedAsset);
    state.depositId = dep.id;
    pollDepositStatus(dep.id);
  } catch (e) {
    setDepositStatus(e.message, "failed");
    btn.disabled = false;
  }
}

function setDepositStatus(text, cls) {
  const el = $("deposit-status");
  el.textContent = text;
  el.className = "status-bar status-" + cls;
}

function pollDepositStatus(id) {
  if (state.pollingTimer) clearInterval(state.pollingTimer);
  state.pollingTimer = setInterval(async () => {
    try {
      const dep = await api.getDeposit(id);
      if (dep.status === "minted") {
        setDepositStatus(t("deposit_modal.status_minted"), "success");
        clearInterval(state.pollingTimer);
        await refreshBalance();
        renderHero();
      } else if (dep.status === "accepted") {
        setDepositStatus(t("deposit_modal.status_accepted"), "pending");
      } else if (dep.status === "failed") {
        setDepositStatus(t("deposit_modal.status_failed"), "failed");
        clearInterval(state.pollingTimer);
      }
    } catch {}
  }, 5000);
}

// ── Modal: Withdraw ──────────────────────────────────────────────────────────
function openWithdrawModal() {
  const m = $("withdraw-modal");
  $("withdraw-modal-title").textContent = t("withdraw_modal.title");
  $("withdraw-balance-label").textContent = t("withdraw_modal.balance_label");
  $("withdraw-balance-value").textContent = `${state.balance} P250SD`;
  $("withdraw-trade-url-label").textContent = t("withdraw_modal.trade_url_label");
  $("withdraw-trade-url").placeholder = t("withdraw_modal.trade_url_placeholder");
  $("withdraw-confirm-btn").textContent = t("withdraw_modal.confirm_btn");
  $("withdraw-status").textContent = "";
  $("withdraw-status").className = "status-bar";
  $("withdraw-confirm-btn").disabled = state.balance === 0;
  m.classList.remove("hidden");
  $("modal-overlay").classList.remove("hidden");
}

function setWithdrawStatus(text, cls) {
  const el = $("withdraw-status");
  el.textContent = text;
  el.className = "status-bar status-" + cls;
}

async function submitWithdraw() {
  const tradeUrl = $("withdraw-trade-url").value.trim();
  if (!tradeUrl) return;
  const btn = $("withdraw-confirm-btn");
  btn.disabled = true;
  setWithdrawStatus(t("withdraw_modal.status_burning"), "pending");

  try {
    const w = await api.createWithdrawal(tradeUrl);
    state.withdrawalId = w.id;
    pollWithdrawStatus(w.id);
  } catch (e) {
    setWithdrawStatus(e.message, "failed");
    btn.disabled = false;
  }
}

function pollWithdrawStatus(id) {
  if (state.pollingTimer) clearInterval(state.pollingTimer);
  state.pollingTimer = setInterval(async () => {
    try {
      const w = await api.getWithdrawal(id);
      if (w.status === "sending") {
        setWithdrawStatus(t("withdraw_modal.status_sending"), "pending");
      } else if (w.status === "delivered") {
        setWithdrawStatus(t("withdraw_modal.status_delivered"), "success");
        clearInterval(state.pollingTimer);
        await refreshBalance();
        renderHero();
      } else if (w.status === "failed") {
        setWithdrawStatus(t("withdraw_modal.status_failed"), "failed");
        clearInterval(state.pollingTimer);
      }
    } catch {}
  }, 5000);
}

// ── History ──────────────────────────────────────────────────────────────────
async function renderHistory() {
  $("history-title").textContent = t("history.title");
  $("history-col-type").textContent = t("history.col_type");
  $("history-col-skin").textContent = t("history.col_skin");
  $("history-col-status").textContent = t("history.col_status");
  $("history-col-date").textContent = t("history.col_date");
  $("history-col-tx").textContent = t("history.col_tx");

  const tbody = $("history-tbody");
  if (!state.user) return;
  try {
    const items = await api.getHistory();
    tbody.innerHTML = "";
    if (!items.length) {
      tbody.innerHTML = `<tr><td colspan="5" class="history-empty">${t("history.empty")}</td></tr>`;
      return;
    }
    items.forEach((item) => {
      const tr = document.createElement("tr");
      const tx = item.tx_hash
        ? `<a href="https://sepolia.etherscan.io/tx/${item.tx_hash}" target="_blank">${item.tx_hash.slice(0, 8)}…</a>`
        : "—";
      const date = new Date(item.created_at).toLocaleDateString();
      const type = item.type === "deposit" ? t("history.type_deposit") : t("history.type_withdraw");
      tr.innerHTML = `<td>${type}</td><td>P250 Sand Dune MW</td><td class="status-${item.status}">${item.status}</td><td>${date}</td><td>${tx}</td>`;
      tbody.appendChild(tr);
    });
  } catch {}
}

// ── Helpers ──────────────────────────────────────────────────────────────────
async function refreshBalance() {
  if (!state.user) return;
  try {
    const b = await api.getBalance();
    state.balance = b.balance;
  } catch {}
}

const SKIN_NAME = "P250 | Sand Dune (Minimal Wear)";

async function fetchSteamInventory(steamId) {
  const url = `https://steamcommunity.com/inventory/${steamId}/730/2?l=english&count=5000`;
  const resp = await fetch(url);
  if (resp.status === 403) throw new Error("private");
  if (!resp.ok) throw new Error("unavailable");
  const data = await resp.json();
  if (!data || !data.success) throw new Error("private");

  const descMap = {};
  for (const d of data.descriptions || []) {
    descMap[`${d.classid}_${d.instanceid}`] = d;
  }

  const items = [];
  for (const asset of data.assets || []) {
    const desc = descMap[`${asset.classid}_${asset.instanceid}`];
    if (!desc) continue;
    if (desc.market_hash_name !== SKIN_NAME) continue;
    items.push({
      asset_id: asset.assetid,
      name: desc.name || SKIN_NAME,
      market_hash_name: SKIN_NAME,
      icon_url: desc.icon_url
        ? `https://community.akamai.steamstatic.com/economy/image/${desc.icon_url}`
        : null,
      tradable: desc.tradable === 1,
    });
  }
  return items;
}

async function loadInventory() {
  if (!state.user) return;
  try {
    const items = await fetchSteamInventory(state.user.steam_id);
    state.inventory = items;
    state.inventoryError = null;
  } catch (e) {
    state.inventory = [];
    state.inventoryError = e.message === "private" ? "private" : "error";
  }
}

// ── Lang switcher ─────────────────────────────────────────────────────────────
function renderLangSwitcher() {
  const el = $("lang-switcher");
  el.innerHTML = "";
  SUPPORTED_LOCALES.forEach((loc) => {
    const btn = document.createElement("button");
    btn.className = "lang-btn" + (loc === getLocale() ? " active" : "");
    btn.textContent = loc === "en_US" ? "EN" : "RU";
    btn.addEventListener("click", async () => {
      await setLocale(loc);
    });
    el.appendChild(btn);
  });
}

// ── Event listeners ──────────────────────────────────────────────────────────
function bindEvents() {
  $("btn-login").addEventListener("click", () => {
    window.location.href = "/api/auth/steam";
  });

  $("btn-logout").addEventListener("click", async () => {
    await fetch("/api/auth/logout", { method: "POST", credentials: "include" });
    window.location.reload();
  });

  $("btn-wallet").addEventListener("click", async () => {
    try {
      const addr = await connectMetaMask();
      state.user.wallet_address = addr;
      renderAll();
    } catch (e) {
      alert(e.message);
    }
  });

  $("hero-deposit-btn").addEventListener("click", () => {
    if (state.inventory.length > 0) {
      openDepositModal(state.inventory[0].asset_id);
    }
  });

  $("hero-withdraw-btn").addEventListener("click", openWithdrawModal);

  $("deposit-confirm-btn").addEventListener("click", submitDeposit);
  $("withdraw-confirm-btn").addEventListener("click", submitWithdraw);
  $("modal-overlay").addEventListener("click", closeModal);
  $("deposit-modal-close").addEventListener("click", closeModal);
  $("withdraw-modal-close").addEventListener("click", closeModal);

  document.addEventListener("click", (e) => {
    if (e.target.classList.contains("skin-deposit-btn")) {
      const assetId = e.target.dataset.asset;
      openDepositModal(assetId);
    }
  });

  document.addEventListener("localechange", () => {
    renderAll();
    renderLangSwitcher();
    renderHistory();
  });
}

// ── Init ─────────────────────────────────────────────────────────────────────
async function init() {
  await initI18n();
  bindEvents();
  renderLangSwitcher();

  try {
    state.user = await api.getMe();
    await Promise.all([refreshBalance(), loadInventory()]);
  } catch {
    state.user = null;
  }

  renderAll();
  renderHistory();
}

init();
