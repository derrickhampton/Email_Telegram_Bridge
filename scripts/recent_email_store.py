import hashlib
import json
import os
from email.utils import parseaddr
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(SKILL_DIR, "data")
RECENT_EMAILS_PATH = os.path.join(DATA_DIR, "recent_emails.json")

DEFAULT_MAX_MESSAGES = 500


def _utc_now_iso():
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def load_recent_emails():
    _ensure_data_dir()
    if not os.path.exists(RECENT_EMAILS_PATH):
        return {"messages": {}, "tokens": {}}

    try:
        with open(RECENT_EMAILS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {"messages": {}, "tokens": {}}

    if not isinstance(data, dict):
        return {"messages": {}, "tokens": {}}

    if not isinstance(data.get("messages"), dict):
        data["messages"] = {}

    if not isinstance(data.get("tokens"), dict):
        data["tokens"] = {}

    return data


def save_recent_emails(data):
    _ensure_data_dir()
    tmp_path = RECENT_EMAILS_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, RECENT_EMAILS_PATH)


def _extract_from_email(from_value):
    _, addr = parseaddr(from_value or "")
    return (addr or "").strip().lower()


def _normalize_message_id(message_id):
    value = (message_id or "").strip()
    return value if value else ""


def _safe_str(value, max_length=1000):
    if value is None:
        return ""
    value = str(value).strip()
    if len(value) > max_length:
        return value[:max_length]
    return value


def _make_token(account, message_id):
    seed = f"{account}|{message_id}".encode("utf-8", errors="ignore")
    digest = hashlib.sha256(seed).hexdigest()[:12]
    return f"em_{digest}"


def store_recent_email(item, max_messages=DEFAULT_MAX_MESSAGES):
    message_id = _normalize_message_id(item.get("message_id"))
    if not message_id:
        return None

    data = load_recent_emails()
    messages = data["messages"]
    tokens = data["tokens"]

    uid = _safe_str(item.get("uid"), max_length=200)
    account = _safe_str(item.get("account"), max_length=200)
    from_raw = _safe_str(item.get("from"), max_length=500)
    from_email = _extract_from_email(from_raw)
    subject = _safe_str(item.get("subject"), max_length=500)
    date = _safe_str(item.get("date"), max_length=200)
    snippet = _safe_str(item.get("snippet"), max_length=1000)
    token = _make_token(account, message_id)

    record = {
        "id": f"{account}:{uid}" if account and uid else uid or message_id,
        "account": account,
        "message_id": message_id,
        "message_token": token,
        "uid": uid,
        "from": from_raw,
        "from_email": from_email,
        "subject": subject,
        "date": date,
        "snippet": snippet,
        "important": bool(item.get("important")),
        "stored_at": _utc_now_iso(),
    }

    messages[message_id] = record
    tokens[token] = message_id

    if len(messages) > max_messages:
        ordered = sorted(
            messages.items(),
            key=lambda kv: kv[1].get("stored_at", ""),
            reverse=True,
        )
        kept_messages = dict(ordered[:max_messages])
        kept_ids = set(kept_messages.keys())
        kept_tokens = {
            tok: mid for tok, mid in tokens.items()
            if mid in kept_ids
        }
        data["messages"] = kept_messages
        data["tokens"] = kept_tokens

    save_recent_emails(data)
    return record


def lookup_email_by_message_id(message_id):
    message_id = _normalize_message_id(message_id)
    if not message_id:
        return None

    data = load_recent_emails()
    record = data.get("messages", {}).get(message_id)
    if not isinstance(record, dict):
        return None
    return record


def lookup_email_by_token(message_token):
    token = (message_token or "").strip()
    if not token:
        return None

    data = load_recent_emails()
    message_id = data.get("tokens", {}).get(token)
    if not message_id:
        return None

    record = data.get("messages", {}).get(message_id)
    if not isinstance(record, dict):
        return None
    return record