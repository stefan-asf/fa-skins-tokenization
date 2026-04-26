# Deposit Multi-Select + Bot-Initiated Trade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace single-skin deposit modal with multi-select inventory grid + trade panel; bot automatically sends trade offer to user requesting selected skins; poll until accepted; mint tokens.

**Architecture:** Frontend gets 4-column scrollable inventory grid where clicking a card toggles selection (max 50). Selected skins appear in a right-column trade panel (replacing history). Clicking "Deposit" calls `POST /deposit` with all asset IDs, backend creates one Deposit record per skin with same `trade_offer_id`, Celery task sends one Steam trade offer to user via `items_from_them`, a polling task checks trade status every 10s via Steam Web API (no re-login), on acceptance queues `mint_for_deposit` per deposit.

**Tech Stack:** Vanilla JS, HTML5, CSS3 (frontend); FastAPI + SQLAlchemy + Celery (backend); steampy (Steam trade API); Steam Web API (polling, no auth needed).

---

## File Map

| File | Change |
|------|--------|
| `frontend/src/i18n/en_US.json` | Add `trade_panel.*` keys, remove `deposit_modal.*` |
| `frontend/src/i18n/ru_RU.json` | Same in Russian |
| `frontend/dist/index.html` | Replace `history-panel` with `trade-panel`, remove `deposit-modal` HTML |
| `frontend/dist/style.css` | 4-col grid + internal scroll, skin card selection state, trade panel styles |
| `frontend/src/app.js` | Multi-select state, renderTradePanel(), new submitDeposit(), pollDepositBatch() |
| `frontend/src/api.js` | `createDeposit(assets[])` → `{deposit_ids: [...]}` |
| `backend/app/api/deposit.py` | Full POST /deposit + GET /deposit/{id} implementation |
| `backend/app/services/steam_bot.py` | Add `request_items_from_user()` + `get_trade_offer_state()` |
| `backend/workers/steam_worker.py` | Add `send_deposit_trade_request` + `poll_deposit_trade_status` tasks |

No DB migration needed — existing Deposit schema fits. Status flow changes to `pending → sent → accepted → minted → failed`; "sent" (4 chars) fits VARCHAR(16).

---

## Task 1: i18n — Add trade panel keys, remove deposit_modal keys

**Files:**
- Modify: `frontend/src/i18n/en_US.json`
- Modify: `frontend/src/i18n/ru_RU.json`

- [ ] **Step 1: Update en_US.json**

Full file content:

```json
{
  "nav": {
    "connect_metamask": "Connect Wallet",
    "login_steam": "Sign in with Steam",
    "logout": "Sign out",
    "balance": "Balance"
  },
  "hero": {
    "title": "Tokenize Your Skin",
    "subtitle": "Deposit your P250 Sand Dune (Minimal Wear) — receive an ERC-20 token on Sepolia. Burn the token — get your skin back.",
    "deposit_btn": "Deposit",
    "withdraw_btn": "Withdraw"
  },
  "inventory": {
    "title": "Your Inventory",
    "empty": "No P250 Sand Dune (Minimal Wear) skins available",
    "private": "Your Steam inventory is private. Change it to public in Steam settings.",
    "not_tradable": "Not tradable",
    "tradable": "Tradable"
  },
  "trade_panel": {
    "title": "Deposit",
    "empty": "Click on skins to select for deposit",
    "count_one": "1 skin selected",
    "count_many": "{n} skins selected",
    "deposit_btn": "Send Deposit",
    "max_warning": "Maximum 50 skins per deposit",
    "no_wallet": "Connect wallet first",
    "status_pending": "Creating deposit...",
    "status_sent": "Trade offer sent — accept it in the Steam app",
    "status_accepted": "Trade accepted, minting tokens...",
    "status_minted": "Done! Tokens minted.",
    "status_failed": "Deposit failed. Please try again."
  },
  "withdraw_modal": {
    "title": "Withdraw Skin",
    "balance_label": "Your token balance",
    "trade_url_label": "Your Steam Trade URL",
    "trade_url_placeholder": "https://steamcommunity.com/tradeoffer/new/?partner=...",
    "confirm_btn": "Burn token & receive skin",
    "status_burning": "Burning token",
    "status_sending": "Bot is sending skin",
    "status_delivered": "Delivered",
    "status_failed": "Failed",
    "no_tokens": "You have no tokens to withdraw"
  },
  "trade_url": {
    "label": "Set up your Steam Trade URL to view inventory",
    "hint": "Required to send trade offers. Found in Steam → Profile → Trade offers.",
    "placeholder": "https://steamcommunity.com/tradeoffer/new/?partner=...",
    "save_btn": "Save"
  },
  "errors": {
    "metamask_not_found": "MetaMask not found. Please install it.",
    "not_logged_in": "Please sign in with Steam first",
    "no_wallet": "Please connect your wallet first",
    "inventory_load_failed": "Failed to load inventory",
    "generic": "Something went wrong"
  }
}
```

- [ ] **Step 2: Update ru_RU.json**

Full file content:

```json
{
  "nav": {
    "connect_metamask": "Подключить кошелёк",
    "login_steam": "Войти через Steam",
    "logout": "Выйти",
    "balance": "Баланс"
  },
  "hero": {
    "title": "Токенизируй свой скин",
    "subtitle": "Депонируй P250 Sand Dune (Minimal Wear) — получи ERC-20 токен на Sepolia. Сожги токен — верни скин.",
    "deposit_btn": "Депозит",
    "withdraw_btn": "Вывод"
  },
  "inventory": {
    "title": "Ваш инвентарь",
    "empty": "Нет скинов P250 Sand Dune (Minimal Wear)",
    "private": "Ваш инвентарь Steam закрыт. Сделайте его публичным в настройках Steam.",
    "not_tradable": "Не торгуемый",
    "tradable": "Торгуемый"
  },
  "trade_panel": {
    "title": "Депозит",
    "empty": "Нажмите на скины для выбора",
    "count_one": "1 скин выбран",
    "count_many": "{n} скина(ов) выбрано",
    "deposit_btn": "Отправить депозит",
    "max_warning": "Максимум 50 скинов за один депозит",
    "no_wallet": "Сначала подключите кошелёк",
    "status_pending": "Создаём депозит...",
    "status_sent": "Трейд-оффер отправлен — примите его в приложении Steam",
    "status_accepted": "Трейд принят, минтим токены...",
    "status_minted": "Готово! Токены выпущены.",
    "status_failed": "Депозит не удался. Попробуйте снова."
  },
  "withdraw_modal": {
    "title": "Вывод скина",
    "balance_label": "Ваш баланс токенов",
    "trade_url_label": "Ваша Trade URL в Steam",
    "trade_url_placeholder": "https://steamcommunity.com/tradeoffer/new/?partner=...",
    "confirm_btn": "Сжечь токен и получить скин",
    "status_burning": "Сжигание токена",
    "status_sending": "Бот отправляет скин",
    "status_delivered": "Доставлено",
    "status_failed": "Ошибка",
    "no_tokens": "У вас нет токенов для вывода"
  },
  "trade_url": {
    "label": "Укажите Trade URL для просмотра инвентаря",
    "hint": "Нужен для отправки трейд-офферов. Найдите в Steam → Профиль → Трейд-офферы.",
    "placeholder": "https://steamcommunity.com/tradeoffer/new/?partner=...",
    "save_btn": "Сохранить"
  },
  "errors": {
    "metamask_not_found": "MetaMask не найден. Установите расширение.",
    "not_logged_in": "Сначала войдите через Steam",
    "no_wallet": "Сначала подключите кошелёк",
    "inventory_load_failed": "Не удалось загрузить инвентарь",
    "generic": "Что-то пошло не так"
  }
}
```

- [ ] **Step 3: Copy i18n JSON files to dist**

```bash
cp frontend/src/i18n/en_US.json frontend/dist/i18n/en_US.json
cp frontend/src/i18n/ru_RU.json frontend/dist/i18n/ru_RU.json
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/i18n/en_US.json frontend/src/i18n/ru_RU.json frontend/dist/i18n/en_US.json frontend/dist/i18n/ru_RU.json
git commit -m "i18n: add trade_panel keys, remove deposit_modal keys"
```

---

## Task 2: HTML — Replace history panel with trade panel, remove deposit modal

**Files:**
- Modify: `frontend/dist/index.html`

- [ ] **Step 1: Replace index.html**

Full file content — key changes:
- `history-panel` div → `trade-panel` div with new structure
- Remove `deposit-modal` div entirely (replaced by inline trade panel)
- Keep `withdraw-modal`

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>FA Skins</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="/style.css" />
</head>
<body>
  <div id="app">

    <!-- ── Nav ── -->
    <nav>
      <div class="nav-logo">FA<span>Skins</span></div>
      <div class="nav-right">
        <div id="lang-switcher"></div>
        <span id="nav-balance" class="hidden"></span>
        <span id="nav-wallet" class="hidden"></span>
        <button id="btn-wallet" class="btn-secondary hidden"></button>
        <button id="btn-login" class="btn-primary hidden"></button>
        <button id="btn-logout" class="btn-ghost hidden">—</button>
      </div>
    </nav>

    <!-- ── Main ── -->
    <main>

      <!-- Left column: hero + inventory -->
      <div class="left-col">
        <div class="hero">
          <div class="hero-text">
            <h1 id="hero-title"></h1>
            <p id="hero-subtitle"></p>
          </div>
          <div class="hero-actions">
            <button id="hero-withdraw-btn" class="btn-secondary" disabled></button>
          </div>
        </div>

        <!-- Inventory -->
        <section id="inventory-section" class="hidden">
          <h2 id="inventory-title"></h2>

          <!-- Trade URL setup -->
          <div id="trade-url-section" class="trade-url-section hidden">
            <p id="trade-url-label" class="trade-url-label"></p>
            <p id="trade-url-hint" class="trade-url-hint"></p>
            <div class="trade-url-row">
              <input type="url" id="trade-url-input" class="trade-url-input" />
              <button id="trade-url-save-btn" class="btn-primary"></button>
            </div>
          </div>

          <div class="inventory-grid" id="inventory-grid"></div>
          <p id="inventory-empty" class="inventory-msg hidden"></p>
          <p id="inventory-private" class="inventory-msg hidden"></p>
        </section>
      </div>

      <!-- Right column: Trade panel -->
      <div class="trade-panel" id="trade-panel">
        <div class="trade-panel-header" id="trade-panel-title"></div>

        <!-- Selected items list -->
        <div class="trade-items" id="trade-items">
          <p class="trade-empty" id="trade-empty-msg"></p>
        </div>

        <!-- Footer: count + button + status -->
        <div class="trade-footer">
          <div class="trade-count" id="trade-count"></div>
          <button id="trade-deposit-btn" class="btn-primary" disabled id="trade-deposit-btn"></button>
          <div id="trade-status" class="status-bar"></div>
        </div>
      </div>

    </main>
  </div>

  <!-- ── Overlay ── -->
  <div id="modal-overlay" class="hidden">

    <!-- Withdraw modal -->
    <div id="withdraw-modal" class="modal hidden" role="dialog">
      <div class="modal-header">
        <span class="modal-title" id="withdraw-modal-title"></span>
        <button class="modal-close" id="withdraw-modal-close">✕</button>
      </div>
      <div>
        <label id="withdraw-balance-label"></label>
        <span id="withdraw-balance-value" style="font-weight:700;color:var(--primary-color)"></span>
      </div>
      <div>
        <label id="withdraw-trade-url-label"></label>
        <input type="url" id="withdraw-trade-url" />
      </div>
      <button id="withdraw-confirm-btn" class="btn-primary"></button>
      <div id="withdraw-status" class="status-bar"></div>
    </div>

  </div>

  <script type="module" src="/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/dist/index.html
git commit -m "html: replace history panel with trade panel, remove deposit modal"
```

---

## Task 3: CSS — Inventory grid + trade panel styles

**Files:**
- Modify: `frontend/dist/style.css`

- [ ] **Step 1: Read current style.css line count to find where to append**

```bash
wc -l frontend/dist/style.css
```

- [ ] **Step 2: Replace inventory grid section and add trade panel styles**

Find the existing `.inventory-grid` rule (search for it) and replace it. Also find `.skin-card` rules. Then add trade panel rules. Apply the following targeted edits:

**2a. Left column — make inventory scroll internally (not page)**

Find and replace `main` layout rules. The left col needs `overflow: hidden` + flex column so inventory-section can scroll:

```css
/* ── Layout ─────────────────────────────────────────────────────────────────── */
#app {
  display: flex;
  flex-direction: column;
  height: 100vh;
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 24px;
}

main {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr 320px;
  gap: 24px;
  overflow: hidden;
  padding: 24px 0;
}

.left-col {
  display: flex;
  flex-direction: column;
  gap: 20px;
  overflow: hidden;
}

#inventory-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  gap: 12px;
}

#inventory-section h2 {
  flex-shrink: 0;
}
```

**2b. Inventory grid — 4 columns, internal scroll**

```css
.inventory-grid {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  overflow-y: auto;
  align-content: start;
  padding-right: 4px;
  scrollbar-width: thin;
  scrollbar-color: var(--border) transparent;
}

.inventory-grid::-webkit-scrollbar {
  width: 4px;
}

.inventory-grid::-webkit-scrollbar-thumb {
  background: var(--border);
  border-radius: 4px;
}
```

**2c. Skin card — selectable, no deposit button per card**

```css
.skin-card {
  background: var(--bg-card);
  border: 1.5px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  cursor: pointer;
  transition: border-color var(--transition), background var(--transition), transform var(--transition);
  user-select: none;
  position: relative;
}

.skin-card:hover {
  background: var(--bg-card-hover);
  border-color: rgba(51, 179, 178, 0.4);
  transform: translateY(-1px);
}

.skin-card.selected {
  border-color: var(--primary-color);
  background: rgba(51, 179, 178, 0.08);
}

.skin-card.selected::after {
  content: "✓";
  position: absolute;
  top: 6px;
  right: 8px;
  font-size: 12px;
  font-weight: 700;
  color: var(--primary-color);
  background: rgba(51, 179, 178, 0.15);
  border-radius: 50%;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 20px;
  text-align: center;
}

.skin-card.not-tradable {
  opacity: 0.5;
  cursor: not-allowed;
}

.skin-card img {
  width: 100%;
  aspect-ratio: 1;
  object-fit: contain;
}

.skin-card-name {
  font-size: 11px;
  font-weight: 500;
  color: var(--text-primary);
  line-height: 1.3;
  word-break: break-word;
}

.skin-card-tag {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 4px;
  width: fit-content;
}

.skin-card-tag.tradable {
  color: var(--success);
  background: rgba(76, 175, 125, 0.12);
}

.skin-card-tag.not-tradable {
  color: var(--text-muted);
  background: rgba(74, 80, 104, 0.2);
}
```

**2d. Trade panel**

```css
/* ── Trade Panel ─────────────────────────────────────────────────────────────── */
.trade-panel {
  display: flex;
  flex-direction: column;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}

.trade-panel-header {
  padding: 16px 20px;
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.trade-items {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  scrollbar-width: thin;
  scrollbar-color: var(--border) transparent;
}

.trade-empty {
  color: var(--text-muted);
  font-size: 13px;
  text-align: center;
  padding: 40px 16px;
  line-height: 1.5;
}

.trade-item {
  display: flex;
  align-items: center;
  gap: 10px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 8px 10px;
}

.trade-item img {
  width: 40px;
  height: 40px;
  object-fit: contain;
  flex-shrink: 0;
}

.trade-item-name {
  flex: 1;
  font-size: 11px;
  font-weight: 500;
  color: var(--text-primary);
  line-height: 1.3;
}

.trade-item-remove {
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 14px;
  line-height: 1;
  padding: 2px 4px;
  border-radius: 4px;
  transition: color var(--transition);
  flex-shrink: 0;
}

.trade-item-remove:hover {
  color: var(--failed);
}

.trade-footer {
  padding: 16px;
  border-top: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 10px;
  flex-shrink: 0;
}

.trade-count {
  font-size: 12px;
  color: var(--text-secondary);
  text-align: center;
}

.trade-footer .btn-primary {
  width: 100%;
}

.trade-max-warning {
  font-size: 11px;
  color: var(--failed);
  text-align: center;
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/dist/style.css
git commit -m "css: 4-col inventory grid with scroll, skin selection state, trade panel"
```

---

## Task 4: api.js — Update createDeposit signature

**Files:**
- Modify: `frontend/src/api.js`

- [ ] **Step 1: Replace createDeposit**

Old:
```js
createDeposit: (asset_id) =>
  req("/deposit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ asset_id }),
  }),
```

New — accepts array of `{asset_id, skin_name}`, returns `{deposit_ids: [...]}`:
```js
createDeposit: (assets) =>
  req("/deposit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ assets }),
  }),
```

- [ ] **Step 2: Copy api.js to dist**

```bash
cp frontend/src/api.js frontend/dist/api.js
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api.js frontend/dist/api.js
git commit -m "api: createDeposit accepts asset array, returns deposit_ids"
```

---

## Task 5: app.js — Multi-select, trade panel, new deposit flow

**Files:**
- Modify: `frontend/src/app.js`

- [ ] **Step 1: Write new app.js**

Full replacement:

```js
import { initI18n, t, setLocale, getLocale, SUPPORTED_LOCALES } from "./i18n/index.js";
import { api } from "./api.js";
import { connectMetaMask } from "./metamask.js";

// ── State ────────────────────────────────────────────────────────────────────
const MAX_SELECTION = 50;

let state = {
  user: null,         // { steam_id, wallet_address, steam_trade_url }
  balance: 0,
  inventory: [],      // [{asset_id, name, icon_url, tradable}]
  inventoryError: null,
  selectedAssets: [], // [{asset_id, name, icon_url}]
  depositIds: [],     // [1, 2, 3] — being polled
  pollingTimer: null,
  depositDone: false,
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
  const panel = $("trade-panel");

  $("trade-panel-title").textContent = t("trade_panel.title");
  $("trade-empty-msg").textContent = t("trade_panel.empty");

  const items = state.selectedAssets;
  const itemsContainer = $("trade-items");
  const depositBtn = $("trade-deposit-btn");

  depositBtn.textContent = t("trade_panel.deposit_btn");

  // Clear items, rebuild
  itemsContainer.innerHTML = "";

  if (items.length === 0) {
    const empty = document.createElement("p");
    empty.className = "trade-empty";
    empty.id = "trade-empty-msg";
    empty.textContent = t("trade_panel.empty");
    itemsContainer.appendChild(empty);
    depositBtn.disabled = true;
    $("trade-count").textContent = "";
  } else {
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

    const countText =
      items.length === 1
        ? t("trade_panel.count_one")
        : t("trade_panel.count_many").replace("{n}", items.length);
    $("trade-count").textContent = countText;

    const canDeposit = state.user && state.user.wallet_address && !state.depositDone;
    depositBtn.disabled = !canDeposit;

    if (!state.user?.wallet_address) {
      $("trade-count").textContent = t("trade_panel.no_wallet");
    }
  }

  if (items.length >= MAX_SELECTION) {
    const warn = document.createElement("div");
    warn.className = "trade-max-warning";
    warn.textContent = t("trade_panel.max_warning");
    $("trade-footer").insertBefore(warn, depositBtn);
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
  if (state.selectedAssets.length === 0) return;

  const btn = $("trade-deposit-btn");
  btn.disabled = true;
  state.depositDone = false;
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
    btn.disabled = false;
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
      const allAccepted = statuses.every((d) =>
        ["accepted", "minted"].includes(d.status)
      );

      if (allMinted) {
        setTradeStatus(t("trade_panel.status_minted"), "success");
        clearInterval(state.pollingTimer);
        state.depositDone = true;
        state.selectedAssets = [];
        await refreshBalance();
        renderAll();
      } else if (anyFailed) {
        setTradeStatus(t("trade_panel.status_failed"), "failed");
        clearInterval(state.pollingTimer);
        $("trade-deposit-btn").disabled = false;
      } else if (allAccepted) {
        setTradeStatus(t("trade_panel.status_accepted"), "pending");
      }
      // else: still "sent" / pending — keep waiting
    } catch {}
  }, 5000);
}

// ── Withdraw ─────────────────────────────────────────────────────────────────
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
  const tradeUrl = $("withdraw-trade-url").value.trim();
  if (!tradeUrl) return;
  const btn = $("withdraw-confirm-btn");
  btn.disabled = true;
  setWithdrawStatus(t("withdraw_modal.status_burning"), "pending");

  try {
    const w = await api.createWithdrawal(tradeUrl);
    pollWithdrawStatus(w.id);
  } catch (e) {
    setWithdrawStatus(e.message, "failed");
    btn.disabled = false;
  }
}

function pollWithdrawStatus(id) {
  const timer = setInterval(async () => {
    try {
      const w = await api.getWithdrawal(id);
      if (w.status === "sending") {
        setWithdrawStatus(t("withdraw_modal.status_sending"), "pending");
      } else if (w.status === "delivered") {
        setWithdrawStatus(t("withdraw_modal.status_delivered"), "success");
        clearInterval(timer);
        await refreshBalance();
        renderHero();
      } else if (w.status === "failed") {
        setWithdrawStatus(t("withdraw_modal.status_failed"), "failed");
        clearInterval(timer);
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

  // Trade panel — remove item button
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
```

- [ ] **Step 2: Copy app.js to dist**

```bash
cp frontend/src/app.js frontend/dist/app.js
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app.js frontend/dist/app.js
git commit -m "feat: multi-select inventory, trade panel, inline deposit flow"
```

---

## Task 6: Backend — Implement POST /deposit and GET /deposit/{id}

**Files:**
- Modify: `backend/app/api/deposit.py`

- [ ] **Step 1: Write deposit.py**

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List

from app.api.deps import get_current_user
from app.db import SessionLocal
from app.models.deposit import Deposit
from app.models.user import User

router = APIRouter(prefix="/deposit", tags=["deposit"])


class AssetInput(BaseModel):
    asset_id: str = Field(..., min_length=1, max_length=32)
    skin_name: str = Field(..., min_length=1, max_length=256)


class DepositRequest(BaseModel):
    assets: List[AssetInput] = Field(..., min_items=1, max_items=50)


@router.post("")
def create_deposit(body: DepositRequest, user: User = Depends(get_current_user)):
    if not user.wallet_address:
        raise HTTPException(status_code=400, detail="Wallet address not set")
    if not user.steam_trade_url:
        raise HTTPException(status_code=400, detail="Steam trade URL not set")

    db = SessionLocal()
    try:
        deposit_ids = []
        for asset in body.assets:
            dep = Deposit(
                steam_id=user.steam_id,
                wallet_address=user.wallet_address,
                asset_id=asset.asset_id,
                skin_name=asset.skin_name,
                status="pending",
            )
            db.add(dep)
            db.flush()  # get dep.id before commit
            deposit_ids.append(dep.id)

        db.commit()

        # Queue Celery task: bot sends trade offer to user
        from workers.steam_worker import send_deposit_trade_request
        send_deposit_trade_request.delay(deposit_ids)

        return {"deposit_ids": deposit_ids}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.get("/{deposit_id}")
def get_deposit(deposit_id: int, user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        dep = db.query(Deposit).filter(
            Deposit.id == deposit_id,
            Deposit.steam_id == user.steam_id,
        ).first()
        if not dep:
            raise HTTPException(status_code=404, detail="Deposit not found")
        return {
            "id": dep.id,
            "asset_id": dep.asset_id,
            "skin_name": dep.skin_name,
            "status": dep.status,
            "trade_offer_id": dep.trade_offer_id,
            "tx_hash": dep.tx_hash,
            "created_at": dep.created_at.isoformat(),
        }
    finally:
        db.close()
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/api/deposit.py
git commit -m "feat: implement POST /deposit (multi-asset) and GET /deposit/{id}"
```

---

## Task 7: Steam bot — Add request_items_from_user() and get_trade_offer_state()

**Files:**
- Modify: `backend/app/services/steam_bot.py`

- [ ] **Step 1: Write steam_bot.py**

```python
import logging
import requests as http_requests
from steampy.client import SteamClient
from steampy.models import GameOptions
from app.config import settings

logger = logging.getLogger(__name__)

GAME = GameOptions.CS
_NODE_INVENTORY_URL = "http://127.0.0.1:8081/inventory"


def get_client() -> SteamClient:
    """Создаёт и возвращает авторизованный SteamClient."""
    from app.services.steam_inventory import _get_mafile_path
    client = SteamClient(settings.steam_api_key or "")
    client.login(
        username=settings.steam_login,
        password=settings.steam_password,
        steam_guard=_get_mafile_path(),
    )
    logger.info("Steam bot logged in as %s", settings.steam_login)
    return client


def get_bot_inventory(client: SteamClient) -> list[dict]:
    """Возвращает список предметов CS2 в инвентаре бота."""
    raw = client.get_my_inventory(GAME)
    items = []
    for asset_id, item in raw.items():
        items.append({
            "asset_id": asset_id,
            "name": item.get("market_hash_name", "Unknown"),
            "tradable": bool(item.get("tradable", 0)),
        })
    return items


def request_items_from_user(
    client: SteamClient,
    trade_url: str,
    user_steam_id: str,
    asset_ids: list[str],
    message: str = "FA Skins — deposit request",
) -> str:
    """
    Бот запрашивает скины из инвентаря пользователя в обмен на ничто.
    Отправляет трейд-оффер с items_from_me=[], items_from_them=[скины юзера].
    Возвращает trade_offer_id.
    """
    # Fetch user's CS2 inventory via Node.js microservice
    resp = http_requests.get(
        _NODE_INVENTORY_URL,
        params={"steamid": user_steam_id},
        timeout=20,
    )
    if resp.status_code == 403:
        raise ValueError("User Steam inventory is private")
    resp.raise_for_status()
    data = resp.json()

    # Build lookup: assetid → asset object
    asset_lookup = {a["assetid"]: a for a in data.get("assets", [])}

    items_to_receive = []
    for asset_id in asset_ids:
        if asset_id not in asset_lookup:
            raise ValueError(f"Asset {asset_id} not found in user's inventory")
        a = asset_lookup[asset_id]
        items_to_receive.append({
            "appid": int(a["appid"]),
            "contextid": str(a["contextid"]),
            "amount": 1,
            "assetid": str(a["assetid"]),
        })

    offer = client.make_offer_with_url(
        items_from_me=[],
        items_from_them=items_to_receive,
        trade_offer_url=trade_url,
        message=message,
    )
    trade_offer_id = offer["tradeofferid"]
    logger.info("Deposit trade request sent: %s (%d items)", trade_offer_id, len(asset_ids))
    return trade_offer_id


def get_trade_offer_state(trade_offer_id: str) -> int:
    """
    Проверяет статус трейд-оффера через Steam Web API без логина.
    Возвращает trade_offer_state (int):
      2 = Active, 3 = Accepted, 5 = Expired,
      6 = Canceled, 7 = Declined, 8 = InvalidItems
    """
    resp = http_requests.get(
        "https://api.steampowered.com/IEconService/GetTradeOffer/v1/",
        params={
            "key": settings.steam_api_key,
            "tradeofferid": trade_offer_id,
            "language": "english",
        },
        timeout=10,
    )
    resp.raise_for_status()
    offer = resp.json().get("response", {}).get("offer", {})
    state = offer.get("trade_offer_state", 0)
    logger.debug("Trade offer %s state: %s", trade_offer_id, state)
    return state


def send_trade_offer(
    client: SteamClient,
    trade_url: str,
    asset_ids: list[str],
    message: str = "FA Skins withdrawal",
) -> str:
    """
    Отправляет трейд-оффер пользователю с указанными скинами (вывод).
    Возвращает trade_offer_id.
    """
    my_inventory = client.get_my_inventory(GAME)

    my_items = []
    for asset_id in asset_ids:
        if asset_id in my_inventory:
            my_items.append(my_inventory[asset_id])
        else:
            raise ValueError(f"Asset {asset_id} not found in bot inventory")

    offer = client.make_offer_with_url(
        items_from_me=my_items,
        items_from_them=[],
        trade_offer_url=trade_url,
        message=message,
    )
    trade_offer_id = offer["tradeofferid"]
    logger.info("Withdrawal trade offer sent: %s", trade_offer_id)
    return trade_offer_id


def get_incoming_trade_offers(client: SteamClient) -> list[dict]:
    """Возвращает список входящих трейд-офферов."""
    offers = client.get_trade_offers(merge=False)
    incoming = offers.get("response", {}).get("trade_offers_received", [])
    return incoming


def accept_trade_offer(client: SteamClient, trade_offer_id: str) -> bool:
    """Принимает входящий трейд-оффер. Возвращает True при успехе."""
    try:
        client.accept_trade_offer(trade_offer_id)
        logger.info("Trade offer %s accepted", trade_offer_id)
        return True
    except Exception as e:
        logger.error("Failed to accept trade offer %s: %s", trade_offer_id, e)
        return False
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/steam_bot.py
git commit -m "feat: add request_items_from_user() and get_trade_offer_state() to steam_bot"
```

---

## Task 8: Celery — send_deposit_trade_request + poll_deposit_trade_status

**Files:**
- Modify: `backend/workers/steam_worker.py`

- [ ] **Step 1: Write steam_worker.py**

```python
"""
Steam Worker — Celery задачи для работы с трейд-офферами.

Запуск:
    cd backend
    celery -A workers.celery_app worker --loglevel=info -Q steam
"""
import logging
from workers.celery_app import celery_app
from app.services.steam_bot import (
    get_client,
    accept_trade_offer,
    send_trade_offer,
    request_items_from_user,
    get_trade_offer_state,
)
from app.db import SessionLocal
from app.models.deposit import Deposit
from app.models.user import User
from app.models.withdrawal import Withdrawal
from app.models.trade_log import TradeLog

logger = logging.getLogger(__name__)

# Steam trade offer states
STATE_ACCEPTED = 3
STATE_TERMINAL = {4, 5, 6, 7, 8, 10}  # Countered/Expired/Canceled/Declined/Invalid/CanceledBy2FA


def _log(db, operation_type: str, operation_id: int, event: str, details: str = None):
    db.add(TradeLog(
        operation_type=operation_type,
        operation_id=operation_id,
        event=event,
        details=details,
    ))
    db.commit()


@celery_app.task(name="steam.send_deposit_trade_request", bind=True, max_retries=3)
def send_deposit_trade_request(self, deposit_ids: list):
    """
    Бот отправляет трейд-оффер пользователю, запрашивая его скины.
    Все deposit_ids → один трейд-оффер → одно ожидание принятия.
    Статус: pending → sent.
    """
    db = SessionLocal()
    try:
        deposits = db.query(Deposit).filter(Deposit.id.in_(deposit_ids)).all()
        if not deposits:
            logger.error("No deposits found for ids: %s", deposit_ids)
            return

        first = deposits[0]

        # Get user's trade URL
        user = db.query(User).filter(User.steam_id == first.steam_id).first()
        if not user or not user.steam_trade_url:
            logger.error("No trade URL for user %s", first.steam_id)
            for d in deposits:
                d.status = "failed"
            db.commit()
            _log(db, "deposit", first.id, "error", "No trade URL for user")
            return

        client = get_client()
        asset_ids = [d.asset_id for d in deposits]

        trade_offer_id = request_items_from_user(
            client=client,
            trade_url=user.steam_trade_url,
            user_steam_id=first.steam_id,
            asset_ids=asset_ids,
        )

        for d in deposits:
            d.trade_offer_id = trade_offer_id
            d.status = "sent"
        db.commit()

        _log(db, "deposit", first.id, "trade_request_sent", trade_offer_id)
        logger.info("Deposit trade sent: offer=%s deposits=%s", trade_offer_id, deposit_ids)

        # Queue polling (start after 10s)
        poll_deposit_trade_status.apply_async(
            args=[trade_offer_id, deposit_ids],
            countdown=10,
        )

    except Exception as exc:
        logger.error("send_deposit_trade_request error: %s", exc)
        db2 = SessionLocal()
        try:
            for dep_id in deposit_ids:
                dep = db2.query(Deposit).filter(Deposit.id == dep_id).first()
                if dep:
                    dep.status = "failed"
            db2.commit()
            _log(db2, "deposit", deposit_ids[0], "error", str(exc))
        finally:
            db2.close()
        raise self.retry(exc=exc, countdown=30)
    finally:
        db.close()


@celery_app.task(name="steam.poll_deposit_trade_status", bind=True, max_retries=60)
def poll_deposit_trade_status(self, trade_offer_id: str, deposit_ids: list):
    """
    Проверяет статус трейд-оффера каждые 10 секунд.
    max_retries=60 → максимум 10 минут ожидания.
    Использует Steam Web API напрямую (без повторного логина).
    """
    db = SessionLocal()
    try:
        state = get_trade_offer_state(trade_offer_id)

        if state == STATE_ACCEPTED:
            deposits = db.query(Deposit).filter(Deposit.id.in_(deposit_ids)).all()
            for d in deposits:
                d.status = "accepted"
            db.commit()

            for d in deposits:
                _log(db, "deposit", d.id, "trade_accepted", trade_offer_id)
                from workers.blockchain_worker import mint_for_deposit
                mint_for_deposit.delay(d.id)

            logger.info("Deposit trade %s accepted, mint queued for %s", trade_offer_id, deposit_ids)

        elif state in STATE_TERMINAL:
            deposits = db.query(Deposit).filter(Deposit.id.in_(deposit_ids)).all()
            for d in deposits:
                d.status = "failed"
            db.commit()
            _log(db, "deposit", deposit_ids[0], "trade_declined_or_cancelled", str(state))
            logger.warning("Deposit trade %s terminal state: %s", trade_offer_id, state)

        else:
            # Still active (state 2) or needs confirmation (state 9) — retry in 10s
            logger.debug("Trade %s state %s — retrying in 10s", trade_offer_id, state)
            raise self.retry(countdown=10)

    except self.MaxRetriesExceededError:
        # 10 minutes passed, user didn't accept
        logger.warning("Trade %s timed out after max retries", trade_offer_id)
        db2 = SessionLocal()
        try:
            for dep_id in deposit_ids:
                dep = db2.query(Deposit).filter(Deposit.id == dep_id).first()
                if dep and dep.status == "sent":
                    dep.status = "failed"
            db2.commit()
            _log(db2, "deposit", deposit_ids[0], "trade_timed_out", trade_offer_id)
        finally:
            db2.close()
    except Exception as exc:
        if not hasattr(exc, 'when'):  # not a Retry exception
            logger.error("poll_deposit_trade_status error: %s", exc)
        raise self.retry(exc=exc, countdown=10)
    finally:
        db.close()


@celery_app.task(name="steam.send_withdrawal_trade", bind=True, max_retries=3)
def send_withdrawal_trade(self, withdrawal_id: int):
    """
    Отправляет скин пользователю (вывод).
    Вызывается blockchain_worker'ом после события TokensBurned.
    """
    db = SessionLocal()
    try:
        withdrawal = db.query(Withdrawal).filter(Withdrawal.id == withdrawal_id).first()
        if not withdrawal:
            logger.error("Withdrawal %d not found", withdrawal_id)
            return

        client = get_client()
        trade_offer_id = send_trade_offer(
            client=client,
            trade_url=withdrawal.trade_url,
            asset_ids=[withdrawal.asset_id],
            message="FA Skins — your skin withdrawal",
        )

        withdrawal.trade_offer_id = trade_offer_id
        withdrawal.status = "sending"
        db.commit()
        _log(db, "withdrawal", withdrawal_id, "trade_sent", trade_offer_id)
        logger.info("Withdrawal %d trade sent: %s", withdrawal_id, trade_offer_id)

    except Exception as exc:
        logger.error("send_withdrawal_trade error: %s", exc)
        db.query(Withdrawal).filter(Withdrawal.id == withdrawal_id).update({"status": "failed"})
        db.commit()
        _log(db, "withdrawal", withdrawal_id, "error", str(exc))
        raise self.retry(exc=exc, countdown=30)
    finally:
        db.close()


@celery_app.task(name="steam.accept_deposit_trade", bind=True, max_retries=3)
def accept_deposit_trade(self, deposit_id: int, trade_offer_id: str):
    """
    Legacy task — принимает входящий трейд (старый флоу, оставлен для совместимости).
    """
    db = SessionLocal()
    try:
        client = get_client()
        success = accept_trade_offer(client, trade_offer_id)

        deposit = db.query(Deposit).filter(Deposit.id == deposit_id).first()
        if not deposit:
            return

        if success:
            deposit.status = "accepted"
            db.commit()
            _log(db, "deposit", deposit_id, "trade_accepted", trade_offer_id)
            from workers.blockchain_worker import mint_for_deposit
            mint_for_deposit.delay(deposit_id)
        else:
            deposit.status = "failed"
            db.commit()
            _log(db, "deposit", deposit_id, "trade_accept_failed", trade_offer_id)

    except Exception as exc:
        logger.error("accept_deposit_trade error: %s", exc)
        _log(db, "deposit", deposit_id, "error", str(exc))
        raise self.retry(exc=exc, countdown=30)
    finally:
        db.close()
```

- [ ] **Step 2: Commit**

```bash
git add backend/workers/steam_worker.py
git commit -m "feat: send_deposit_trade_request + poll_deposit_trade_status Celery tasks"
```

---

## Task 9: Deploy to Server

- [ ] **Step 1: Push all commits**

```bash
git push origin main
```

- [ ] **Step 2: Ask user to run on server**

Ask user to run:
```bash
cd /var/www/fa-skins-tokenization && git pull && bash deploy.sh
```

Expected output includes:
```
[deploy] Installing Python dependencies...
[deploy] Running migrations...
[deploy] Syncing frontend JS...
[deploy] Installing Node inventory dependencies...
[deploy] Restarting services...
```

- [ ] **Step 3: Ask user to verify services are running**

```bash
systemctl status faskins-api faskins-celery faskins-inventory --no-pager
```

Expected: all three `active (running)`.

- [ ] **Step 4: Smoke test deposit flow**

1. Open site, log in via Steam
2. Open inventory — verify 4-column grid, no per-card deposit button
3. Click a P250 Sand Dune card — verify it highlights (teal border + ✓), appears in right trade panel
4. Click same card again — verify deselected, removed from trade panel
5. Select 2-3 skins, click "Send Deposit" — verify status changes to "Trade offer sent"
6. Check Steam app on phone — verify incoming trade offer from bot requesting those skins
7. Accept trade in Steam — verify within 10s status changes to "minting tokens"
8. Wait for mint — verify balance updates in nav bar

---

## Self-Review

### Spec coverage

| Requirement | Covered by |
|-------------|-----------|
| 4-col grid, no page scroll | Task 3 CSS |
| Click to select/deselect | Task 5 JS `toggleAsset()` |
| Selected → trade panel (right column) | Task 2 HTML + Task 5 JS |
| Max 50 skins | Task 5 JS `MAX_SELECTION` constant |
| "Deposit" button in trade panel | Task 2 HTML + Task 5 JS |
| POST /deposit with array | Task 4 api.js + Task 6 backend |
| Bot sends trade offer to user | Task 7 `request_items_from_user()` |
| Poll trade status every 10s | Task 8 `poll_deposit_trade_status` |
| On acceptance → mint tokens | Task 8 → calls `mint_for_deposit.delay()` |
| Deploy to server | Task 9 |

### No placeholders

All code is complete. No TBD/TODO.

### Type consistency

- `api.createDeposit(assets)` → assets = `[{asset_id, skin_name}]` — matches Task 6 `AssetInput` model ✓
- `result.deposit_ids` from API → used in `pollDepositBatch(result.deposit_ids)` ✓
- `send_deposit_trade_request.delay(deposit_ids)` — matches task signature `(self, deposit_ids: list)` ✓
- `poll_deposit_trade_status.apply_async(args=[trade_offer_id, deposit_ids])` — matches `(self, trade_offer_id: str, deposit_ids: list)` ✓
- `get_trade_offer_state(trade_offer_id)` returns `int` — compared to `STATE_ACCEPTED = 3` ✓
