# ONBOARDING for email_telegram_bridge

## Adding Accounts
Use `manage_accounts.py`:
  python3 scripts/manage_accounts.py
Select add, then input account details.

## Secrets
Secrets are stored in environment variables, e.g., `EMAIL_SECRET`.
Set env vars before running.

## Workflow Example
1. Add account
2. Set env vars
3. Validate config: `python3 scripts/test_config.py`
4. Run fetch (`--once`) or start notifier.

## Common Mistakes
- Missing env vars
- Missing or incorrect account details
- Not setting secrets in env
