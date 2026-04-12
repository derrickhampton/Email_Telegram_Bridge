import json
import os
import smtplib
from email.message import EmailMessage

from utils_pending_replies import (
    cleanup_expired_pending,
    iso_z,
    is_allowed_account,
    is_blocked_recipient,
    parse_iso_z,
    save_pending_replies,
    utc_now,
)
from log_utils import log_event
from env_loader import load_env_file
load_env_file()

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
ACCOUNTS_PATH = os.path.join(SKILL_DIR, "config", "accounts.json")


def load_accounts_config():
    with open(ACCOUNTS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("accounts", [])


def get_account_config(account_name):
    for account in load_accounts_config():
        if account.get("name") == account_name:
            return account
    return None


def get_account_smtp_settings(account_name):
    account = get_account_config(account_name)
    if not account:
        raise RuntimeError(f"Account not found in accounts.json: {account_name}")

    smtp_host = (account.get("smtp_host") or "").strip()
    smtp_port = int(account.get("smtp_port") or 587)
    smtp_username = (account.get("username") or account.get("email") or "").strip()
    smtp_from = (account.get("email") or smtp_username).strip()

    secret_env = (account.get("secret_env") or "").strip()
    smtp_password = os.getenv(secret_env, "").strip() if secret_env else ""

    smtp_use_tls = True
    if "smtp_use_tls" in account:
        smtp_use_tls = bool(account.get("smtp_use_tls"))

    return {
        "smtp_host": smtp_host,
        "smtp_port": smtp_port,
        "smtp_username": smtp_username,
        "smtp_password": smtp_password,
        "smtp_from": smtp_from,
        "smtp_use_tls": smtp_use_tls,
    }


def send_pending_reply(approval_id: str):
    data = cleanup_expired_pending()
    pending = data["pending"].get(approval_id)

    if not pending:
        raise ValueError("Approval ID not found")

    if pending.get("status") != "pending":
        raise ValueError(f"Approval is not pending; current status: {pending.get('status')}")

    expires_at = pending.get("expires_at")
    if not expires_at or parse_iso_z(expires_at) < utc_now():
        pending["status"] = "expired"
        save_pending_replies(data)
        raise ValueError("Approval expired")

    account = pending.get("account", "")
    if not is_allowed_account(account):
        raise ValueError(f"Account no longer allowed: {account}")

    to_addr = (pending.get("to") or "").strip()
    blocked, reason = is_blocked_recipient(to_addr)
    if blocked:
        raise ValueError(f"Recipient blocked at send time: {reason}")

    smtp_settings = get_account_smtp_settings(account)

    smtp_host = smtp_settings["smtp_host"]
    smtp_port = smtp_settings["smtp_port"]
    smtp_username = smtp_settings["smtp_username"]
    smtp_password = smtp_settings["smtp_password"]
    smtp_from = smtp_settings["smtp_from"]
    smtp_use_tls = smtp_settings["smtp_use_tls"]

    log_event(
    "smtp_config_checked",
    account=account,
    smtp_host_present=bool(smtp_host),
    smtp_port=smtp_port,
    smtp_username_present=bool(smtp_username),
    smtp_password_present=bool(smtp_password),
    smtp_from_present=bool(smtp_from),
    smtp_use_tls=smtp_use_tls,
)

    if not smtp_host or not smtp_username or not smtp_password or not smtp_from:
        raise RuntimeError(f"SMTP is not fully configured for account: {account}")

    msg = EmailMessage()
    msg["From"] = smtp_from
    msg["To"] = to_addr
    msg["Subject"] = pending["subject"]

    source_message_id = (pending.get("source_message_id") or "").strip()
    if source_message_id:
        msg["In-Reply-To"] = source_message_id
        msg["References"] = source_message_id

    msg.set_content(pending["body"])

    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
        server.ehlo()
        if smtp_use_tls:
            server.starttls()
            server.ehlo()
        server.login(smtp_username, smtp_password)
        server.send_message(msg)

    now_iso = iso_z(utc_now())
    pending["status"] = "sent"
    pending["approved_at"] = now_iso
    pending["sent_at"] = now_iso
    save_pending_replies(data)
    return pending


def cancel_pending_reply(approval_id: str):
    data = cleanup_expired_pending()
    pending = data["pending"].get(approval_id)

    if not pending:
        raise ValueError("Approval ID not found")

    if pending.get("status") != "pending":
        raise ValueError(f"Cannot cancel approval in status: {pending.get('status')}")

    pending["status"] = "cancelled"
    pending["cancelled_at"] = iso_z(utc_now())
    save_pending_replies(data)
    return pending