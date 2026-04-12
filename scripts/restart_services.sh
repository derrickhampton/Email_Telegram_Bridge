#!/usr/bin/env bash
set -euo pipefail

SERVICES=(
  email-telegram-poll-notify.service
  email-telegram-command-loop.service
  email-telegram-maintenance.timer
)

echo "Restarting Email Telegram Bridge services..."

for service in "${SERVICES[@]}"; do
  echo "-> restarting ${service}"
  systemctl --user restart "${service}"
done

echo
echo "Current status:"
for service in "${SERVICES[@]}"; do
  echo "==== ${service} ===="
  systemctl --user --no-pager --full status "${service}" || true
  echo
done

echo "Done."