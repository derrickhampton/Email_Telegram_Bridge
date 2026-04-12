<<<<<<< HEAD
# email_telegram_bridge

## Overview
A secure, lightweight email fetcher and Telegram reply bridge supporting multiple accounts with minimal dependencies.

## What It Is

Email Telegram Bridge is a self-hosted multi-account email-to-Telegram workflow tool. It monitors inboxes, sends new-email notifications to Telegram, and supports approval-gated email replies using SMTP.

## Who It Is For

This project is for developers, operators, and self-hosters who want a lightweight human-in-the-loop email workflow that can run locally on Linux and integrate email notifications and reply handling into Telegram.

## Why It Is Useful

It helps you:
- receive new email alerts in Telegram
- create quick or context-aware draft replies
- approve replies before anything is sent
- manage multiple inboxes from one workflow
- keep email automation lightweight and locally controlled

## How It Is Different

Email Telegram Bridge is designed around:
- approval-gated replies instead of auto-send
- a Telegram-first workflow for inbox triage and reply handling
- optional local Ollama support for Deep Think draft generation
- multi-account reply profiles for account-aware behavior
- a self-hosted, lightweight architecture with minimal dependencies
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

## Use Cases
- Send new email notifications to Telegram for one or more inboxes
- Review, approve, or cancel email replies directly from Telegram
- Use local Ollama models to generate guarded Deep Think email drafts
- Manage multiple inboxes with account-aware reply profiles and SMTP sending
- Run a lightweight self-hosted human-in-the-loop email assistant on Linux

