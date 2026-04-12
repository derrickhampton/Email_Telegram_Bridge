import json
from getpass import getpass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "accounts.json"


def load_config():
    if not CONFIG_PATH.exists():
        return {"accounts": []}

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading config: {e}")
        return {"accounts": []}


def save_config(config):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def list_accounts(config):
    accounts = config.get("accounts", [])
    if not accounts:
        print("No accounts configured.")
        return

    for acc in accounts:
        print(f"- {acc.get('name')} ({acc.get('email')})")


def add_account(config):
    name = input("Account name: ").strip()
    email = input("Email address: ").strip()
    username = input("Username: ").strip()
    imap_host = input("IMAP host: ").strip()
    imap_port = int(input("IMAP port (default 993): ") or 993)
    secret_env = input("Env var for password (e.g. EMAIL_MAIN): ").strip()

    account = {
        "name": name,
        "provider": "imap",
        "email": email,
        "imap_host": imap_host,
        "imap_port": imap_port,
        "username": username,
        "secret_env": secret_env,
        "auth_type": "password",
        "folder": "INBOX",
        "enabled": True,
    }

    config.setdefault("accounts", []).append(account)
    save_config(config)

    print("Account added.")


def main():
    config = load_config()

    print("1) List accounts")
    print("2) Add account")

    choice = input("Select option: ").strip()

    if choice == "1":
        list_accounts(config)
    elif choice == "2":
        add_account(config)
    else:
        print("Invalid option")


if __name__ == "__main__":
    main()