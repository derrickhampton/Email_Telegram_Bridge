# Security Policy

## Overview
`email_telegram_bridge` processes live email, Telegram bot events, SMTP credentials, and optional local LLM output. Because it handles real communications and secrets, operators should treat it as a security-sensitive system.

This document explains:
- what not to commit
- how to handle secrets
- safe operating practices
- reply safety expectations
- how to report vulnerabilities

---

## Supported Use
This project is designed for local or self-managed deployment.

Operators are responsible for:
- protecting mailbox credentials
- protecting Telegram bot credentials
- reviewing AI-generated replies before sending
- configuring safe reply policies
- securing the host machine where the bridge runs

---

## Secrets Handling

## Do not commit secrets
Never commit any of the following:
- `.env`
- `config/.env`
- `config/accounts.json`
- runtime state in `data/`
- logs containing live account data

Only commit public-safe templates such as:
- `.env.example`
- `config/accounts.example.json`

## Store secrets locally
Secrets should live only in local environment files or environment variables.

Examples:
- mailbox passwords
- app passwords
- SMTP credentials
- Telegram bot token
- Telegram chat ID

## Use least-privilege credentials when possible
Where supported:
- use app passwords instead of primary passwords
- use mailbox credentials with only the access needed
- use a dedicated Telegram bot for this project
- avoid sharing the same secrets across unrelated systems

---

## Config Safety

## Local-only files
These files are intended for local runtime only:
- `config/accounts.json`
- `.env`
- `config/.env`
- `data/*`

## Public-safe files
These files are intended for publishing:
- `.env.example`
- `config/accounts.example.json`
- docs and setup scripts with placeholders

## Account config guidance
Use placeholder values in example configs such as:
- `your.email@example.com`
- `imap.example.com`
- `smtp.example.com`
- `EMAIL_EXAMPLE_SECRET`

Do not publish real:
- mailbox addresses
- provider hosts tied to private infrastructure
- secret variable values
- business-specific internal notes unless intentionally public

---

## Reply Safety Model

## No auto-send
This project is designed around an approval gate:
1. create a draft
2. approve explicitly
3. then send

Do not modify the project to auto-send drafts unless you fully understand the risks.

## Review AI-generated replies
Deep Think Draft uses a local LLM path with guardrails and fallback logic, but generated text should still be treated as untrusted until approved.

Operators should verify that generated replies do not:
- invent facts
- promise timelines, pricing, refunds, availability, or actions not explicitly supported
- make commitments on behalf of the business
- reveal internal process details
- use the wrong tone or brand identity

## Block obvious system senders
Maintain blocking for obvious non-reply/system senders such as:
- `noreply`
- `no-reply`
- `donotreply`
- `mailer-daemon`
- bulk/list/bounce/newsletter patterns where appropriate

---

## Telegram Security

## Restrict bot usage
Configure the bot so only the intended chat can control the system.

The bridge should ignore unauthorized chat IDs.

## Protect callback-driven actions
Telegram buttons such as:
- `Simple Draft`
- `Deep Think Draft`
- `Ignore`
- `Approve`
- `Cancel`

should only work for the authorized operator chat.

## Treat Telegram as an operational control plane
Anyone who can control the authorized Telegram bot/chat can potentially create and approve replies. Protect that access accordingly.

---

## Host and Runtime Security

## Protect the host machine
The machine running the bridge should be treated as sensitive because it may have:
- mailbox credentials
- Telegram credentials
- recent email metadata
- pending draft content
- reply state and logs

Recommended practices:
- use a dedicated user account where practical
- restrict local file permissions
- keep the OS updated
- restrict shell access
- monitor service logs

## File permissions
Recommended:
- `.env` and `config/.env` should be readable only by the local operator account
- service setup scripts should not expose secrets
- runtime state should not be world-readable

---

## Logging and Data Exposure

## Logs may contain sensitive metadata
Structured logs can include:
- account names
- sender email addresses
- subjects
- message tokens
- approval IDs
- error context

Treat logs as operationally sensitive.

## Avoid leaking secrets in logs
Do not log:
- raw passwords
- bot tokens
- full secret values
- full environment dumps

Mask or omit sensitive values in any future logging changes.

---

## Maintenance and Data Retention

## Runtime state should be bounded
The bridge uses local JSON files to persist operational state. Maintenance pruning should remain enabled so state files do not grow indefinitely.

Typical cleanup targets:
- sent/cancelled/expired pending replies
- old ignored entries
- old recent email/token entries

## Do not publish runtime state
Never push `data/*` to a public repo.

---

## Public Release Guidance

Before publishing the project publicly:
- remove or untrack live `config/accounts.json`
- remove or untrack `.env` and `config/.env`
- ensure `.gitignore` excludes runtime state and secret files
- replace live config with example templates
- remove hardcoded local machine paths
- review docs for private domains, users, emails, or deployment assumptions

---

## Vulnerability Reporting

If you discover a security issue in this project:
- do not disclose secrets publicly
- provide a minimal reproduction when possible
- describe:
  - affected file(s)
  - risk level
  - likely impact
  - suggested fix if known

If a public repository is later created, add a project-specific security contact or reporting channel here.

---

## Safe Defaults Summary
Operators should keep these defaults:
- explicit approval before sending
- blocked system senders
- restricted Telegram chat access
- local-only secret storage
- no committed runtime state
- maintenance cleanup enabled