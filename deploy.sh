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

# --- Restart services ---
echo "[deploy] Restarting services..."
sudo systemctl restart faskins-api
sudo systemctl restart faskins-celery

echo "[deploy] $(date) — done"
