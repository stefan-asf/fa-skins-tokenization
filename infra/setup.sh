#!/bin/bash
# setup.sh — первичная настройка сервера Ubuntu 24.04
# Запускать ОДИН РАЗ от root: bash infra/setup.sh

set -e

REPO="/var/www/fa-skins-tokenization"
DOMAIN="fa.stfnasf.tech"

echo "=== [1/7] Установка системных пакетов ==="
apt-get update -q
apt-get install -y python3 python3-venv python3-pip postgresql redis-server git curl

echo "=== [2/7] PostgreSQL — создание БД и пользователя ==="
# Запрашиваем пароль для нового пользователя БД
read -sp "Введи пароль для PostgreSQL пользователя 'faskins_user': " DB_PASS
echo ""
sudo -u postgres psql <<SQL
CREATE USER faskins_user WITH PASSWORD '$DB_PASS';
CREATE DATABASE faskins OWNER faskins_user;
GRANT ALL PRIVILEGES ON DATABASE faskins TO faskins_user;
SQL
echo "✓ БД создана"

echo "=== [3/7] Redis ==="
systemctl enable redis-server
systemctl start redis-server
echo "✓ Redis запущен"

echo "=== [4/7] Python venv ==="
cd "$REPO"
python3 -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r backend/requirements.txt
echo "✓ Python зависимости установлены"

echo "=== [5/7] Миграции БД ==="
cd "$REPO/backend"
../.venv/bin/alembic upgrade head
echo "✓ Миграции применены"

echo "=== [6/7] systemd сервисы ==="
# deploy.sh должен запускаться от root (для systemctl restart)
# поэтому добавляем www-data в sudoers только для нужных команд
cat > /etc/sudoers.d/faskins << 'SUDOERS'
www-data ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart faskins-api
www-data ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart faskins-celery
SUDOERS

cp "$REPO/infra/systemd/faskins-api.service"     /etc/systemd/system/
cp "$REPO/infra/systemd/faskins-celery.service"  /etc/systemd/system/
cp "$REPO/infra/systemd/faskins-webhook.service" /etc/systemd/system/

systemctl daemon-reload
systemctl enable faskins-api faskins-celery faskins-webhook
systemctl start  faskins-api faskins-celery faskins-webhook
echo "✓ Сервисы запущены"

echo "=== [7/7] Nginx ==="
cp "$REPO/infra/nginx/fa.stfnasf.tech.conf" /etc/nginx/sites-available/fa.stfnasf.tech
ln -sf /etc/nginx/sites-available/fa.stfnasf.tech /etc/nginx/sites-enabled/fa.stfnasf.tech
nginx -t && systemctl reload nginx
echo "✓ Nginx настроен"

echo ""
echo "=== Готово! Следующие шаги ==="
echo "1. Создай .env: cp $REPO/.env.example $REPO/.env && nano $REPO/.env"
echo "2. SSL: certbot --nginx -d $DOMAIN"
echo "3. В GitHub репозитории настрой Webhook:"
echo "   URL:         https://$DOMAIN/webhook"
echo "   Content type: application/json"
echo "   Secret:      (значение WEBHOOK_SECRET из faskins-webhook.service)"
