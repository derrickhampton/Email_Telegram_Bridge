import json
import os
import secrets
from datetime import datetime, timezone
from email.utils import parseaddr

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(SKILL_DIR, "data")
PENDING_REPLIES_PATH = os.path.join(DATA_DIR, "pending_replies.json")


def utc_now():
    return datetime.now(timezone.utc)


def iso_z(dt):
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso_z(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def load_pending_replies():
    ensure_data_dir()
    if not os.path.exists(PENDING_REPLIES_PATH):
        return {"pending": {}}

    try:
        with open(PENDING_REPLIES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {"pending": {}}

    if "pending" not in data or not isinstance(data["pending"], dict):
        data["pending"] = {}

    return data


def save_pending_replies(data):
    ensure_data_dir()
    tmp_path = PENDING_REPLIES_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, PENDING_REPLIES_PATH)


def generate_approval_id():
    return f"apr_{secrets.token_hex(6)}"


def normalize_email_address(value):
    _, addr = parseaddr(value or "")
    return (addr or "").strip().lower()


def split_csv_env(name):
    raw = os.getenv(name, "").strip()
    if not raw:
        return []
    return [x.strip().lower() for x in raw.split(",") if x.strip()]


def is_blocked_recipient(email_address):
    addr = normalize_email_address(email_address)
    if not addr or "@" not in addr:
        return True, "invalid recipient"

    local, _domain = addr.split("@", 1)

    blocked_prefixes = split_csv_env("EMAIL_REPLY_BLOCKED_LOCALPART_PREFIXES") or [
        "noreply",
        "no-reply",
        "donotreply",
        "mailer-daemon",
    ]
    if local in blocked_prefixes:
        return True, f"blocked sender prefix: {local}"

    if os.getenv("EMAIL_REPLY_BLOCK_BULK", "true").lower() == "true":
        bulk_hints = ["list-", "bounce", "newsletter", "notifications", "announce"]
        if any(hint in local for hint in bulk_hints):
            return True, "bulk/system sender blocked"

    return False, ""
def is_allowed_account(account_name):
    allowed_accounts = split_csv_env("EMAIL_REPLY_ALLOWED_ACCOUNTS")
    if not allowed_accounts:
        return True
    return (account_name or "").strip().lower() in allowed_accounts


def make_reply_subject(original_subject):
    subject = (original_subject or "").strip()
    if not subject:
        return "Re:"
    if subject.lower().startswith("re:"):
        return subject
    return f"Re: {subject}"


def cleanup_expired_pending():
    data = load_pending_replies()
    now = utc_now()
    changed = False

    for item in data["pending"].values():
        if item.get("status") != "pending":
            continue

        expires_at = item.get("expires_at")
        if not expires_at:
            continue

        try:
            if parse_iso_z(expires_at) < now:
                item["status"] = "expired"
                changed = True
        except Exception:
            item["status"] = "expired"
            changed = True

    if changed:
        save_pending_replies(data)

    return data