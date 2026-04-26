import { initI18n, t, setLocale, getLocale, SUPPORTED_LOCALES } from "./i18n/index.js";
import { api } from "./api.js";
import { connectMetaMask } from "./metamask.js";

// ── Constants ────────────────────────────────────────────────────────────────
const MAX_SELECTION = 50;

// ── State ────────────────────────────────────────────────────────────────────
let state = {
  user: null,           // { steam_id, wallet_address, steam_trade_url }
  balance: 0,
  inventory: [],        // [{asset_id, name, icon_url, tradable}]
  inventoryError: null,
  selectedAssets: [],   // [{asset_id, name, icon_url}]
  depositIds: [],       // [1, 2, ...] — IDs being polled
  pollingTimer: null,
  depositInProgress: false,
};

// ── DOM refs ─────────────────────────────────────────────────────────────────
const $ = (id) => document.getElementById(id);

// ── Render ───────────────────────────────────────────────────────────────────
function renderAll() {
  renderNav();
  renderHero();
  renderInventory();
  renderTradePanel();
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
  $("hero-withdraw-btn").textContent = t("hero.withdraw_btn");

  const canWithdraw = state.user && state.user.wallet_address && state.balance > 0;
  $("hero-withdraw-btn").disabled = !canWithdraw;
}

function renderInventory() {
  const section = $("inventory-section");
  const grid = $("inventory-grid");
  const emptyMsg = $("inventory-empty");
  const privateMsg = $("inventory-private");
  const tradeUrlSection = $("trade-url-section");

  if (!state.user) {
    section.classList.add("hidden");
    return;
  }

  section.classList.remove("hidden");
  $("inventory-title").textContent = t("inventory.title");

  if (!state.user.steam_trade_url) {
    tradeUrlSection.classList.remove("hidden");
    $("trade-url-label").textContent = t("trade_url.label");
    $("trade-url-hint").textContent = t("trade_url.hint");
    $("trade-url-input").placeholder = t("trade_url.placeholder");
    $("trade-url-save-btn").textContent = t("trade_url.save_btn");
    grid.innerHTML = "";
    emptyMsg.classList.add("hidden");
    privateMsg.classList.add("hidden");
    return;
  }

  tradeUrlSection.classList.add("hidden");
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

  const selectedIds = new Set(state.selectedAssets.map((a) => a.asset_id));

  state.inventory.forEach((item) => {
    const card = document.createElement("div");
    const isSelected = selectedIds.has(item.asset_id);
    card.className =
      "skin-card" +
      (isSelected ? " selected" : "") +
      (!item.tradable ? " not-tradable" : "");
    card.dataset.asset = item.asset_id;
    card.innerHTML = `
      <img src="${item.icon_url}" alt="${item.name}" loading="lazy" />
      <div class="skin-card-name">${item.name}</div>
      <div class="skin-card-tag ${item.tradable ? "tradable" : "not-tradable"}">
        ${item.tradable ? t("inventory.tradable") : t("inventory.not_tradable")}
      </div>
    `;
    grid.appendChild(card);
  });
}

function renderTradePanel() {
  $("trade-panel-title").textContent = t("trade_panel.title");

  const items = state.selectedAssets;
  const itemsContainer = $("trade-items");
  const depositBtn = $("trade-deposit-btn");
  const countEl = $("trade-count");

  depositBtn.textContent = t("trade_panel.deposit_btn");

  // Rebuild items list
  itemsContainer.innerHTML = "";

  if (items.length === 0) {
    const empty = document.createElement("p");
    empty.className = "trade-empty";
    empty.textContent = t("trade_panel.empty");
    itemsContainer.appendChild(empty);
    countEl.textContent = "";
    depositBtn.disabled = true;
    return;
  }

  items.forEach((item) => {
    const row = document.createElement("div");
    row.className = "trade-item";
    row.innerHTML = `
      <img src="${item.icon_url}" alt="${item.name}" />
      <div class="trade-item-name">${item.name}</div>
      <button class="trade-item-remove" data-asset="${item.asset_id}" title="Remove">✕</button>
    `;
    itemsContainer.appendChild(row);
  });

  // Count label
  const countText =
    items.length === 1
      ? t("trade_panel.count_one")
      : t("trade_panel.count_many").replace("{n}", items.length);
  countEl.textContent = countText;

  // Max warning
  const existingWarn = $("trade-footer").querySelector(".trade-max-warning");
  if (existingWarn) existingWarn.remove();
  if (items.length >= MAX_SELECTION) {
    const warn = document.createElement("div");
    warn.className = "trade-max-warning";
    warn.textContent = t("trade_panel.max_warning");
    $("trade-footer").insertBefore(warn, depositBtn);
  }

  // Deposit button state
  const canDeposit =
    state.user &&
    state.user.wallet_address &&
    !state.depositInProgress;
  depositBtn.disabled = !canDeposit;

  if (!state.user?.wallet_address) {
    countEl.textContent = t("trade_panel.no_wallet");
  }
}

// ── Selection ────────────────────────────────────────────────────────────────
function toggleAsset(item) {
  if (!item.tradable) return;

  const idx = state.selectedAssets.findIndex((a) => a.asset_id === item.asset_id);
  if (idx >= 0) {
    state.selectedAssets.splice(idx, 1);
  } else {
    if (state.selectedAssets.length >= MAX_SELECTION) return;
    state.selectedAssets.push({
      asset_id: item.asset_id,
      name: item.name,
      icon_url: item.icon_url,
    });
  }

  renderInventory();
  renderTradePanel();
}

function removeAsset(assetId) {
  state.selectedAssets = state.selectedAssets.filter((a) => a.asset_id !== assetId);
  renderInventory();
  renderTradePanel();
}

// ── Deposit ──────────────────────────────────────────────────────────────────
async function submitDeposit() {
  if (state.selectedAssets.length === 0 || state.depositInProgress) return;

  state.depositInProgress = true;
  $("trade-deposit-btn").disabled = true;
  setTradeStatus(t("trade_panel.status_pending"), "pending");

  try {
    const assets = state.selectedAssets.map((a) => ({
      asset_id: a.asset_id,
      skin_name: a.name,
    }));
    const result = await api.createDeposit(assets);
    state.depositIds = result.deposit_ids;
    setTradeStatus(t("trade_panel.status_sent"), "pending");
    pollDepositBatch(result.deposit_ids);
  } catch (e) {
    setTradeStatus(e.message, "failed");
    state.depositInProgress = false;
    $("trade-deposit-btn").disabled = false;
  }
}

function setTradeStatus(text, cls) {
  const el = $("trade-status");
  el.textContent = text;
  el.className = "status-bar status-" + cls;
}

function pollDepositBatch(depositIds) {
  if (state.pollingTimer) clearInterval(state.pollingTimer);

  state.pollingTimer = setInterval(async () => {
    try {
      const statuses = await Promise.all(depositIds.map((id) => api.getDeposit(id)));

      const allMinted = statuses.every((d) => d.status === "minted");
      const anyFailed = statuses.some((d) => d.status === "failed");
      const anyAccepted = statuses.some((d) =>
        ["accepted", "minted"].includes(d.status)
      );

      if (allMinted) {
        setTradeStatus(t("trade_panel.status_minted"), "success");
        clearInterval(state.pollingTimer);
        state.depositInProgress = false;
        state.selectedAssets = [];
        state.depositIds = [];
        await refreshBalance();
        renderAll();
      } else if (anyFailed) {
        setTradeStatus(t("trade_panel.status_failed"), "failed");
        clearInterval(state.pollingTimer);
        state.depositInProgress = false;
        $("trade-deposit-btn").disabled = false;
      } else if (anyAccepted) {
        setTradeStatus(t("trade_panel.status_accepted"), "pending");
      }
      // else: still "sent" — keep polling
    } catch {}
  }, 5000);
}

// ── Withdraw ─────────────────────────────────────────────────────────────────
function openWithdrawModal() {
  $("withdraw-modal-title").textContent = t("withdraw_modal.title");
  $("withdraw-balance-label").textContent = t("withdraw_modal.balance_label");
  $("withdraw-balance-value").textContent = `${state.balance} P250SD`;
  $("withdraw-quantity-label").textContent = t("withdraw_modal.quantity_label");
  $("withdraw-trade-url-info").textContent = t("withdraw_modal.trade_url_info");
  $("withdraw-confirm-btn").textContent = t("withdraw_modal.confirm_btn");
  $("withdraw-status").textContent = "";
  $("withdraw-status").className = "status-bar";

  const qInput = $("withdraw-quantity");
  qInput.max = state.balance;
  qInput.value = Math.min(1, state.balance);

  $("withdraw-confirm-btn").disabled = state.balance === 0;
  $("withdraw-modal").classList.remove("hidden");
  $("modal-overlay").classList.remove("hidden");
}

function closeModal() {
  $("withdraw-modal").classList.add("hidden");
  $("modal-overlay").classList.add("hidden");
}

function setWithdrawStatus(text, cls) {
  const el = $("withdraw-status");
  el.textContent = text;
  el.className = "status-bar status-" + cls;
}

async function submitWithdraw() {
  const quantity = Math.max(1, parseInt($("withdraw-quantity").value) || 1);
  if (quantity > state.balance) return;

  const btn = $("withdraw-confirm-btn");
  btn.disabled = true;
  setWithdrawStatus(t("withdraw_modal.status_burning"), "pending");

  try {
    const w = await api.createWithdrawal(quantity);
    pollWithdrawBatch(w.ids || [w.id]);
  } catch (e) {
    setWithdrawStatus(e.message, "failed");
    btn.disabled = false;
  }
}

function pollWithdrawBatch(ids) {
  const timer = setInterval(async () => {
    try {
      const statuses = await Promise.all(ids.map((id) => api.getWithdrawal(id)));
      const allDelivered = statuses.every((w) => w.status === "delivered");
      const anyFailed = statuses.some((w) => w.status === "failed");
      const anySending = statuses.some((w) => w.status === "sending");

      if (allDelivered) {
        setWithdrawStatus(t("withdraw_modal.status_delivered"), "success");
        clearInterval(timer);
        await refreshBalance();
        renderHero();
      } else if (anyFailed) {
        setWithdrawStatus(t("withdraw_modal.status_failed"), "failed");
        clearInterval(timer);
        $("withdraw-confirm-btn").disabled = false;
      } else if (anySending) {
        setWithdrawStatus(t("withdraw_modal.status_sending"), "pending");
      }
    } catch {}
  }, 5000);
}

// ── Trade URL ─────────────────────────────────────────────────────────────────
async function saveTradeUrl() {
  const input = $("trade-url-input");
  const btn = $("trade-url-save-btn");
  const url = input.value.trim();
  if (!url) return;
  btn.disabled = true;
  try {
    await api.saveTradeUrl(url);
    state.user.steam_trade_url = url;
    await loadInventory();
    renderAll();
  } catch (e) {
    alert(e.message);
    btn.disabled = false;
  }
}

// ── Helpers ──────────────────────────────────────────────────────────────────
async function refreshBalance() {
  if (!state.user) return;
  try {
    const b = await api.getBalance();
    state.balance = b.balance;
  } catch {}
}

async function loadInventory() {
  if (!state.user || !state.user.steam_trade_url) {
    state.inventory = [];
    state.inventoryError = null;
    return;
  }
  try {
    const data = await api.getInventory();
    state.inventory = data.items;
    state.inventoryError = null;
  } catch (e) {
    state.inventory = [];
    state.inventoryError = e.message.includes("private") ? "private" : "error";
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

  $("hero-withdraw-btn").addEventListener("click", openWithdrawModal);
  $("withdraw-confirm-btn").addEventListener("click", submitWithdraw);
  $("modal-overlay").addEventListener("click", closeModal);
  $("withdraw-modal-close").addEventListener("click", closeModal);

  $("trade-url-save-btn").addEventListener("click", saveTradeUrl);
  $("trade-deposit-btn").addEventListener("click", submitDeposit);

  // Inventory card click — toggle selection
  $("inventory-grid").addEventListener("click", (e) => {
    const card = e.target.closest(".skin-card");
    if (!card) return;
    const assetId = card.dataset.asset;
    const item = state.inventory.find((i) => i.asset_id === assetId);
    if (item) toggleAsset(item);
  });

  // Trade panel — remove item
  $("trade-items").addEventListener("click", (e) => {
    const btn = e.target.closest(".trade-item-remove");
    if (!btn) return;
    removeAsset(btn.dataset.asset);
  });

  document.addEventListener("localechange", () => {
    renderAll();
    renderLangSwitcher();
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
}

init();
