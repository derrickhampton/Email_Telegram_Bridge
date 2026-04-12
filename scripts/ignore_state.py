import json
import os
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(SKILL_DIR, "data")
IGNORED_EMAILS_PATH = os.path.join(DATA_DIR, "ignored_emails.json")


def _utc_now_iso():
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def load_ignored_emails():
    _ensure_data_dir()
    if not os.path.exists(IGNORED_EMAILS_PATH):
        return {"ignored": {}}

    try:
        with open(IGNORED_EMAILS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {"ignored": {}}

    if not isinstance(data, dict):
        return {"ignored": {}}

    if not isinstance(data.get("ignored"), dict):
        data["ignored"] = {}

    return data


def save_ignored_emails(data):
    _ensure_data_dir()
    tmp_path = IGNORED_EMAILS_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, IGNORED_EMAILS_PATH)


def mark_ignored(message_id, account="", from_email="", subject="", reason="user_ignore_button"):
    message_id = (message_id or "").strip()
    if not message_id:
        raise ValueError("message_id is required")

    data = load_ignored_emails()
    data["ignored"][message_id] = {
        "message_id": message_id,
        "account": (account or "").strip(),
        "from_email": (from_email or "").strip(),
        "subject": (subject or "").strip(),
        "reason": reason,
        "ignored_at": _utc_now_iso(),
    }
    save_ignored_emails(data)
    return data["ignored"][message_id]


def is_ignored(message_id):
    message_id = (message_id or "").strip()
    if not message_id:
        return False
    data = load_ignored_emails()
    return message_id in data.get("ignored", {})