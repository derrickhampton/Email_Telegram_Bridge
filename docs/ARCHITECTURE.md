# Architecture

## Overview
`email_telegram_bridge` is a lightweight email-to-Telegram workflow system that:

1. polls one or more email inboxes
2. sends new-email notifications to Telegram
3. lets the user choose:
   - Simple Draft
   - Deep Think Draft
   - Ignore
4. requires explicit approval before any email reply is sent
5. stores local state for notifications, drafts, ignores, and Telegram offsets
6. runs continuously via user services and performs periodic cleanup

The design favors:
- explicit approval before sending
- local state files instead of a database
- account-aware drafting
- simple operational tooling
- public-safe templating for config and secrets

---

## High-Level Flow

### Incoming email flow
1. `poll_and_notify.py` checks configured inboxes for unread messages
2. unseen messages are normalized and stored in `recent_emails.json`
3. a Telegram message is sent with inline buttons:
   - `Simple Draft`
   - `Deep Think Draft`
   - `Ignore`
4. the message is marked as seen only after Telegram notification succeeds

### Drafting flow
1. user taps a Telegram button
2. `telegram_command_loop.py` receives the callback
3. `telegram_commands.py` resolves the stored email record by token
4. based on the action:
   - `Simple Draft` builds a deterministic account-aware reply
   - `Deep Think Draft` generates an account-aware LLM draft with fallback
   - `Ignore` records the message as intentionally ignored
5. for draft actions, a pending reply is created in `pending_replies.json`
6. Telegram message is edited to show the draft preview and:
   - `Approve`
   - `Cancel`

### Send flow
1. user taps `Approve`
2. `telegram_commands.py` calls `send_reply.py`
3. `send_reply.py` loads the correct SMTP settings for the originating account
4. the message is sent with reply headers (`In-Reply-To`, `References`) when available
5. the pending item is marked as sent
6. Telegram updates the message to reflect success

### Ignore flow
1. user taps `Ignore`
2. the message ID is stored in `ignored_emails.json`
3. Telegram message is updated to show that no draft was created

---

## Main Components

## 1. Poller
### File
`scripts/poll_and_notify.py`

### Responsibilities
- load configured accounts
- fetch unread emails
- filter out messages already seen
- store recent email metadata and message token mappings
- choose Telegram button layout based on sender eligibility
- send Telegram notifications
- mark notifications as seen after successful delivery

### Key behavior
- runs once or continuously via `--interval`
- only unseen messages are notified
- UI-level gating can hide draft buttons for obvious non-reply/system senders
- notification state is persisted locally

---

## 2. Telegram Command Loop
### File
`scripts/telegram_command_loop.py`

### Responsibilities
- poll Telegram Bot API for:
  - text messages
  - callback queries
- validate the allowed chat
- dispatch events to command/callback handlers
- persist the Telegram update offset

### Key behavior
- long-polling loop for Telegram updates
- supports both text commands and button-based UX
- ignores unauthorized chat IDs
- persists `telegram_offset.json` so old updates are not reprocessed

---

## 3. Telegram Command Handlers
### File
`scripts/telegram_commands.py`

### Responsibilities
- parse manual text commands:
  - `/draft_reply`
  - `/approve_reply`
  - `/cancel_reply`
- handle callback actions:
  - `draft_simple:<token>`
  - `draft_deep:<token>`
  - `ignore:<token>`
  - `approve:<approval_id>`
  - `cancel:<approval_id>`
- create pending drafts
- update Telegram messages and callback responses

### Key behavior
- acts as the main orchestration layer between Telegram actions and local state
- keeps manual commands as fallback
- edits existing Telegram messages to keep UX compact

---

## 4. Draft Generation
### File
`scripts/ollama_drafts.py`

### Responsibilities
- load account reply profile information
- generate account-aware Simple Drafts
- generate account-aware Deep Think Drafts
- build safe LLM prompts
- normalize and validate LLM output
- fall back to deterministic templates when the model fails or returns weak output

### Drafting modes

#### Simple Draft
- deterministic
- fast
- low-risk
- account-aware
- role-aware
- respects emoji/signoff policy

#### Deep Think Draft
- uses local Ollama
- uses account-aware reply profile
- subject/snippet aware
- safety constrained
- fallback-safe

### Why it exists separately
Drafting quality and policy are easier to evolve when isolated from Telegram and SMTP code.

---

## 5. Reply Sender
### File
`scripts/send_reply.py`

### Responsibilities
- resolve SMTP settings from the originating account
- validate pending approval state
- enforce recipient blocking rules
- send approved replies
- update pending reply status to sent or cancelled

### Key behavior
- only sends replies after explicit approval
- uses account-specific SMTP config
- does not rely on one global sender
- preserves reply threading when source message ID is available

---

## 6. Pending Reply Utilities
### File
`scripts/utils_pending_replies.py`

### Responsibilities
- manage `pending_replies.json`
- generate approval IDs
- normalize timestamps
- enforce reply blocking rules
- expire stale pending replies

### Key behavior
- approval is one-time and stateful
- expired drafts cannot be approved later
- system senders such as `noreply` are blocked

---

## 7. Recent Email Store
### File
`scripts/recent_email_store.py`

### Responsibilities
- store normalized recent email metadata
- maintain mappings:
  - `message_id -> email record`
  - `message_token -> message_id`
- provide lookup by full message ID or short token

### Why it exists
Telegram inline callback data must stay short, so the app uses local tokens rather than raw full message IDs in button payloads.

---

## 8. Ignore State
### File
`scripts/ignore_state.py`

### Responsibilities
- store intentionally ignored messages
- preserve operator intent
- support future reporting or pruning

---

## 9. Maintenance
### File
`scripts/maintenance.py`

### Responsibilities
- prune old sent/cancelled/expired pending replies
- prune old ignored messages
- prune old recent email/token mappings

### Why it exists
The system is long-running and file-backed, so maintenance keeps local state bounded and healthy.

---

## 10. Environment Loader
### File
`scripts/env_loader.py`

### Responsibilities
- auto-load `.env` values from local env files
- reduce runtime errors caused by missing sourced shell variables

### Why it exists
This makes services and scripts more portable and easier to operate.

---

## Configuration Model

## Account configuration
### File
`config/accounts.json` (local runtime file)
`config/accounts.example.json` (public-safe template)

Each account defines:
- IMAP settings
- SMTP settings
- auth method
- secret env var name
- notification policy
- reply profile

### Reply profile
The `reply_profile` makes drafts account-aware.

Typical fields:
- `business_name`
- `sending_domain`
- `mailbox_role`
- `tone`
- `allow_emojis`
- `max_words`
- `default_signoff`
- `style_notes`

This is used heavily by:
- Simple Draft
- Deep Think Draft

---

## Environment configuration
### Files
- `config/.env`
- `.env`
- `.env.example`

Typical variables:
- mailbox secret variables such as `EMAIL_ACCOUNT_SECRET`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `OLLAMA_BASE_URL`
- `EMAIL_DEEPTHINK_MODEL`
- `EMAIL_DEEPTHINK_TEMPERATURE`

### Important rule
`secret_env` in account config is the **name of the environment variable**, not the secret itself.

Example:

```json
"secret_env": "EMAIL_ACCOUNT_SECRET"