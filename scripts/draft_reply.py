import os
from datetime import timedelta

from email.utils import parseaddr

from utils_pending_replies import (
    cleanup_expired_pending,
    generate_approval_id,
    iso_z,
    is_allowed_account,
    is_blocked_recipient,
    load_pending_replies,
    make_reply_subject,
    save_pending_replies,
    utc_now,
)

def create_pending_reply(*, account: str, source_message_id: str, sender_email: str, original_subject: str, body: str, source_email_id: str | None = None, telegram_request: str | None = None):
    cleanup_expired_pending()

    if not is_allowed_account(account):
        raise ValueError(f"Account not allowed for replies: {account}")

    recipient = parseaddr(sender_email or "")[1].strip()
    blocked, reason = is_blocked_recipient(recipient)
    if blocked:
        raise ValueError(f"Reply blocked: {reason}")

    if not source_message_id:
        raise ValueError("Missing source_message_id")

    reply_body = (body or "").strip()
    if not reply_body:
        raise ValueError("Reply body cannot be empty")

    ttl_minutes = int(os.getenv("EMAIL_REPLY_APPROVAL_TTL_MINUTES", "60"))
    now = utc_now()
    expires_at = now + timedelta(minutes=ttl_minutes)
    approval_id = generate_approval_id()

    record = {
        "approval_id": approval_id,
        "account": account,
        "source_message_id": source_message_id,
        "source_email_id": source_email_id,
        "to": recipient,
        "subject": make_reply_subject(original_subject),
        "body": reply_body,
        "created_at": iso_z(now),
        "expires_at": iso_z(expires_at),
        "status": "pending",
        "approved_at": None,
        "sent_at": None,
        "cancelled_at": None,
        "telegram_request": telegram_request,
    }

    data = load_pending_replies()
    data["pending"][approval_id] = record
    save_pending_replies(data)
    return record