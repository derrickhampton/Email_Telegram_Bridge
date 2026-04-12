#!/usr/bin/env bash
set -euo pipefail

SERVICE_DIR="${HOME}/.config/systemd/user"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-/usr/bin/python3}"

MAINT_SERVICE="${SERVICE_DIR}/email-telegram-maintenance.service"
MAINT_TIMER="${SERVICE_DIR}/email-telegram-maintenance.timer"

mkdir -p "$SERVICE_DIR"

cat > "$MAINT_SERVICE" <<EOF
[Unit]
Description=Email Telegram Bridge Maintenance
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=${SKILL_DIR}
ExecStart=${PYTHON_BIN} -u scripts/maintenance.py --pending-days 7 --ignored-days 30 --recent-max 500
EOF

cat > "$MAINT_TIMER" <<EOF
[Unit]
Description=Run Email Telegram Bridge Maintenance Daily

[Timer]
OnCalendar=daily
Persistent=true
Unit=email-telegram-maintenance.service

[Install]
WantedBy=timers.target
EOF

chmod 644 "$MAINT_SERVICE" "$MAINT_TIMER"

systemctl --user daemon-reload
systemctl --user enable --now email-telegram-maintenance.timer

echo
echo "Created:"
echo "  $MAINT_SERVICE"
echo "  $MAINT_TIMER"
echo
echo "Timer status:"
systemctl --user --no-pager --full status email-telegram-maintenance.timer || true
echo
echo "Next runs:"
systemctl --user list-timers --all | grep email-telegram-maintenance || true
echo
echo "To run maintenance immediately:"
echo "  systemctl --user start email-telegram-maintenance.service"
echo
echo "To follow maintenance logs:"
echo "  journalctl --user -u email-telegram-maintenance.service -f"