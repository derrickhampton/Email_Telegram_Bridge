# Deployment Guide

## Overview
This project runs as two long-lived user services:
- poll and notify
- Telegram command loop

An optional maintenance timer performs cleanup daily.

## Prerequisites
- Python 3
- IMAP/SMTP-capable email account
- Telegram bot token and chat ID
- Optional Ollama for Deep Think Drafts
- systemd user services available

## Local files required
- `config/accounts.json`
- `config/.env` or `.env`

## Install steps
1. Copy `config/accounts.example.json` to `config/accounts.json`
2. Copy `.env.example` to `config/.env`
3. Fill in local values
4. Validate config
5. Test poller once
6. Test Telegram loop
7. Install user services
8. Install maintenance timer

## Service install
Commands for:
- poller service
- command loop service
- maintenance timer

## Restart commands
```bash
systemctl --user restart email-telegram-poll-notify.service
systemctl --user restart email-telegram-command-loop.service
systemctl --user restart email-telegram-maintenance.timer