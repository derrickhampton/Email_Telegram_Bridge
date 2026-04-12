#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_EXAMPLE_FILE="$SKILL_DIR/.env.example"
CONFIG_DIR="$SKILL_DIR/config"
ENV_FILE="$CONFIG_DIR/.env"

mkdir -p "$CONFIG_DIR"

if [[ ! -f "$ENV_EXAMPLE_FILE" ]]; then
  echo "Error: missing template file:"
  echo "  $ENV_EXAMPLE_FILE"
  exit 1
fi

cp "$ENV_EXAMPLE_FILE" "$ENV_FILE"
chmod 600 "$ENV_FILE"

echo "Created local env file:"
echo "  $ENV_FILE"
echo
echo "To load it into your current shell:"
echo "  set -a"
echo "  source \"$ENV_FILE\""
echo "  set +a"
echo
echo "To verify variables are present:"
echo "  grep -E '^(EMAIL_ACCOUNT_SECRET|TELEGRAM_BOT_TOKEN|TELEGRAM_CHAT_ID)=' \"$ENV_FILE\""