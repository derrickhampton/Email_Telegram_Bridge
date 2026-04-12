import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "accounts.json"


def main():
    if not CONFIG_PATH.exists():
        print("accounts.json not found")
        return

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        accounts = data.get("accounts", [])

        if not accounts:
            print("No accounts configured")
            return

        for acc in accounts:
            required_fields = [
                "name",
                "email",
                "imap_host",
                "imap_port",
                "username",
                "secret_env",
            ]

            missing = [f for f in required_fields if f not in acc]

            if missing:
                print(f"Account {acc.get('name')} missing fields: {missing}")
            else:
                print(f"Account {acc.get('name')} OK")

        print("Configuration validation passed")

    except Exception as e:
        print(f"Error reading config: {e}")


if __name__ == "__main__":
    main()