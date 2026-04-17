#!/bin/bash
# deploy.sh — запускается вебхуком после git pull
# Устанавливает зависимости, применяет миграции, перезапускает сервисы

set -e

REPO="/var/www/fa-skins-tokenization"
VENV="$REPO/.venv"
PYTHON="$VENV/bin/python"
PIP="$VENV/bin/pip"

echo "[deploy] $(date) — start"

# --- Python venv ---
if [ ! -d "$VENV" ]; then
  echo "[deploy] Creating venv..."
  python3 -m venv "$VENV"
fi

echo "[deploy] Installing Python dependencies..."
$PIP install --quiet --upgrade pip
$PIP install --quiet -r "$REPO/backend/requirements.txt"

# --- Alembic migrations ---
echo "[deploy] Running migrations..."
cd "$REPO/backend"
"$VENV/bin/alembic" upgrade head

# --- Frontend ---
# style.css, index.html, i18n/*.json live in dist/ and are updated by git pull.
# Only JS files that have a source in src/ need manual copying.
echo "[deploy] Syncing frontend JS..."
DIST="$REPO/frontend/dist"
SRC="$REPO/frontend/src"
cp "$SRC/app.js"       "$DIST/app.js"
cp "$SRC/api.js"       "$DIST/api.js"
cp "$SRC/metamask.js"  "$DIST/metamask.js"
cp "$SRC/i18n/index.js" "$DIST/i18n/index.js"

# --- Node inventory microservice ---
echo "[deploy] Installing Node inventory dependencies..."
cd "$REPO/infra/node-inventory"
npm install --production --silent

# Register and enable service on first deploy
if ! systemctl is-enabled faskins-inventory &>/dev/null; then
  echo "[deploy] Registering faskins-inventory service..."
  sudo cp "$REPO/infra/systemd/faskins-inventory.service" /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable faskins-inventory
fi

# --- Restart services ---
echo "[deploy] Restarting services..."
sudo systemctl restart faskins-inventory
sudo systemctl restart faskins-api
sudo systemctl restart faskins-celery

echo "[deploy] $(date) — done"
