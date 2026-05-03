#!/bin/bash

SRC="/root/test_bot/"
DST="/root/bot/"

echo "🚀 Деплой: $SRC → $DST"

rsync -av --checksum \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude 'venv/' \
  --exclude 'files/' \
  --exclude 'eSIM/' \
  --exclude '*.db' \
  --exclude '*.log' \
  --exclude '.env' \
  "$SRC" "$DST"

echo ""
echo "🔄 Перезапуск бота..."
systemctl restart bot.service

echo ""
echo "📋 Статус:"
systemctl status bot.service --no-pager -l
