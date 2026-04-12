# AUTOMATION for email_telegram_bridge

## Polling and Deduplication
Polling runs in a loop or via cron. Uses `load_state()` and `save_state()` for deduplication.
Emails are tracked via Message-ID or fallback key.

## Run Modes
- Run once:
  python3 scripts/poll_and_notify.py --once
- Continuous polling:
  python3 scripts/poll_and_notify.py --interval 300

## Examples
# Run once
python3 scripts/poll_and_notify.py --once

# Poll every 5 mins
python3 scripts/poll_and_notify.py --interval 300

## Optional: Cron example
* * * * * /home/clawd/.openclaw/skills/email_telegram_bridge/scripts/run_notifier.sh

## Notes
Adjust interval as needed; ensure environment variables are set.