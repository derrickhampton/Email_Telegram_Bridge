import json
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_PATH = BASE_DIR / "data" / "notifier_state.json"


def _default_state():
    return {"accounts": {}}


def load_state():
    if not STATE_PATH.exists():
        state = _default_state()
        save_state(state)
        return state

    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            raise ValueError("State file is not a JSON object")

        if "accounts" not in data or not isinstance(data["accounts"], dict):
            data["accounts"] = {}

        return data
    except Exception as e:
        print(f"Error loading state file, recreating empty state: {e}")
        state = _default_state()
        save_state(state)
        return state


def save_state(state):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def _ensure_account_bucket(state, account_name):
    accounts = state.setdefault("accounts", {})
    account_bucket = accounts.setdefault(account_name, {})
    account_bucket.setdefault("notified_keys", {})
    return account_bucket


def has_seen(state, account_name, key):
    account_bucket = _ensure_account_bucket(state, account_name)
    return key in account_bucket["notified_keys"]


def mark_seen(state, account_name, key):
    account_bucket = _ensure_account_bucket(state, account_name)
    account_bucket["notified_keys"][key] = datetime.utcnow().isoformat() + "Z"


def prune_old_entries(state, max_age_days=30):
    cutoff = datetime.utcnow() - timedelta(days=max_age_days)
    accounts = state.setdefault("accounts", {})

    for _, account_bucket in accounts.items():
        notified = account_bucket.setdefault("notified_keys", {})
        keys_to_delete = []

        for key, timestamp in notified.items():
            try:
                seen_dt = datetime.fromisoformat(timestamp.rstrip("Z"))
                if seen_dt < cutoff:
                    keys_to_delete.append(key)
            except Exception:
                keys_to_delete.append(key)

        for key in keys_to_delete:
            notified.pop(key, None)