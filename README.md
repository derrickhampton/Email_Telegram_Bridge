<<<<<<< HEAD
# email_telegram_bridge

## Overview
A secure, lightweight email fetcher and Telegram reply bridge supporting multiple accounts with minimal dependencies.

## Features
- Multi-account IMAP support
- Check unread, recent, and important emails
- Summarize emails for quick review
- Secrets loaded from env vars or a local `.env`
- Send summaries to terminal or Telegram
- Telegram inline actions for:
  - Simple Draft
  - Deep Think Draft
  - Ignore
- Explicit approval gate before sending replies
- SMTP reply sending with account-based configuration
- Local state persistence for:
  - seen emails
  - recent emails
  - ignored emails
  - pending replies

## Project Structure
- `config/`: account templates and local `.env`
- `scripts/`: fetch, notify, reply, maintenance, and utility scripts
- `data/`: local runtime state
- `docs/`: documentation
- `SKILL.md`

## Public Repo Safety
This project is intended to be published with templates, not live runtime data.

Do not commit:
- `config/accounts.json`
- `.env`
- `config/.env`
- `data/*`

Use these public-safe templates instead:
- `config/accounts.example.json`
- `.env.example`

## Local Setup
1. Copy the account template:
   ```bash
   cp config/accounts.example.json config/accounts.json
