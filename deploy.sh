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
echo "[deploy] Syncing frontend..."
DIST="$REPO/frontend/dist"
SRC="$REPO/frontend/src"
cp "$SRC/style.css" "$DIST/style.css"
cp "$SRC/app.js" "$DIST/app.js"
cp "$SRC/api.js" "$DIST/api.js"
cp "$SRC/metamask.js" "$DIST/metamask.js"
mkdir -p "$DIST/i18n"
cp "$SRC/i18n/en_US.json" "$DIST/i18n/en_US.json"
cp "$SRC/i18n/ru_RU.json" "$DIST/i18n/ru_RU.json"

# --- Restart services ---
echo "[deploy] Restarting services..."
sudo systemctl restart faskins-api
sudo systemctl restart faskins-celery

echo "[deploy] $(date) — done"
