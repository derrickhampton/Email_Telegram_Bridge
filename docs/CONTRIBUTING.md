# Contributing

Thanks for contributing to `email_telegram_bridge`.

This project handles email, Telegram bot actions, SMTP sending, local state, and optional LLM-assisted drafting. Please keep changes safe, reviewable, and public-repo friendly.

---

## Ground Rules

- Do not commit secrets
- Do not commit live account config
- Do not commit runtime state
- Do not commit local-only `.env` files
- Do not commit generated logs, caches, or temp files
- Keep pull requests focused and small when possible
- Update docs when behavior or setup changes

---

## Do Not Commit

These files should stay local only:

- `.env`
- `config/.env`
- `config/accounts.json`
- `data/*`

Safe tracked templates include:

- `.env.example`
- `config/accounts.example.json`
- `data/.gitkeep`

If you accidentally add a local file, remove it from the index before committing.

---

## Branching Workflow

Please do not commit directly to `main`.

Use a feature branch:

```bash
git checkout -b feature/my-change
