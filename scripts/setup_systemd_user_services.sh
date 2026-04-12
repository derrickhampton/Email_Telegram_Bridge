#!/usr/bin/env bash
set -euo pipefail

SERVICE_DIR="${HOME}/.config/systemd/user"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-/usr/bin/python3}"

POLL_SERVICE="${SERVICE_DIR}/email-telegram-poll-notify.service"
CMD_SERVICE="${SERVICE_DIR}/email-telegram-command-loop.service"

mkdir -p "$SERVICE_DIR"

cat > "$POLL_SERVICE" <<EOF
[Unit]
Description=Email Telegram Bridge Poll and Notify
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${SKILL_DIR}
ExecStart=${PYTHON_BIN} -u scripts/poll_and_notify.py --interval 30 --limit 10
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
EOF

cat > "$CMD_SERVICE" <<EOF
[Unit]
Description=Email Telegram Bridge Command Loop
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${SKILL_DIR}
ExecStart=${PYTHON_BIN} -u scripts/telegram_command_loop.py
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
EOF

chmod 644 "$POLL_SERVICE" "$CMD_SERVICE"

systemctl --user daemon-reload
systemctl --user enable --now email-telegram-poll-notify.service
systemctl --user enable --now email-telegram-command-loop.service

if command -v loginctl >/dev/null 2>&1; then
  loginctl enable-linger "$USER" || true
fi

echo
echo "Created services:"
echo "  $POLL_SERVICE"
echo "  $CMD_SERVICE"
echo
echo "Current status:"
systemctl --user --no-pager --full status email-telegram-poll-notify.service || true
systemctl --user --no-pager --full status email-telegram-command-loop.service || true
echo
echo "Follow logs with:"
echo "  journalctl --user -u email-telegram-poll-notify.service -f"
echo "  journalctl --user -u email-telegram-command-loop.service -f"