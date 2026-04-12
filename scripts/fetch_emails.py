import argparse
import email
import imaplib
import json
import os
import re
import ssl
from datetime import datetime, timedelta
from pathlib import Path

from email_utils import (
    decode_header_value,
    extract_text_body,
    format_email_date,
    is_important,
    make_snippet,
    sanitize_for_external_output,
)
from env_loader import load_env_file
load_env_file()
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "accounts.json"


def load_accounts():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("accounts", [])


def create_ssl_context():
    context = ssl.create_default_context()
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    return context


def build_search_criteria(mode="unread", hours=None):
    if mode == "unread":
        return "UNSEEN"
    if mode == "recent" and hours:
        since_date = (datetime.now() - timedelta(hours=hours)).strftime("%d-%b-%Y")
        return f'(SINCE "{since_date}")'
    return "ALL"


def extract_uid_from_fetch_response(fetch_response_meta):
    if not fetch_response_meta:
        return ""

    meta_text = (
        fetch_response_meta.decode(errors="ignore")
        if isinstance(fetch_response_meta, bytes)
        else str(fetch_response_meta)
    )
    match = re.search(r"UID (\d+)", meta_text)
    return match.group(1) if match else ""


def extract_literal_from_fetch_data(msg_data):
    for item in msg_data:
        if isinstance(item, tuple) and len(item) >= 2 and item[1]:
            return item[1]
    return b""


def fetch_header_message(mail, eid):
    header_fields = (
        "SUBJECT FROM DATE MESSAGE-ID "
        "CONTENT-TYPE CONTENT-TRANSFER-ENCODING MIME-VERSION"
    )
    typ, msg_data = mail.fetch(
        eid,
        f"(UID BODY.PEEK[HEADER.FIELDS ({header_fields})])",
    )
    if typ != "OK" or not msg_data:
        return "", None, b""

    uid = ""
    for item in msg_data:
        if isinstance(item, tuple) and len(item) >= 2:
            uid = extract_uid_from_fetch_response(item[0]) or uid

    header_bytes = extract_literal_from_fetch_data(msg_data)
    if not header_bytes:
        return uid, None, b""

    msg = email.message_from_bytes(header_bytes)
    return uid, msg, header_bytes


def fetch_body_text(mail, eid, header_bytes):
    typ, msg_data = mail.fetch(eid, "(BODY.PEEK[TEXT])")
    if typ != "OK" or not msg_data:
        return ""

    body_bytes = extract_literal_from_fetch_data(msg_data)
    if not body_bytes:
        return ""

    try:
        reconstructed = header_bytes + b"\r\n" + body_bytes
        msg = email.message_from_bytes(reconstructed)
        return extract_text_body(msg)
    except Exception:
        return ""


def fetch_emails(account, mode="unread", hours=None, limit=10):
    results = []
    mail = None

    try:
        host = account["imap_host"]
        port = int(account.get("imap_port", 993))
        username = account["username"]
        env_var = account["secret_env"]
        password = os.environ.get(env_var)

        if not password:
            print(f"Secret env var {env_var} not set")
            return []

        ssl_context = create_ssl_context()
        mail = imaplib.IMAP4_SSL(host, port, ssl_context=ssl_context)
        mail.login(username, password)
        mail.select(account.get("folder", "INBOX"), readonly=True)

        criteria = build_search_criteria(mode=mode, hours=hours)
        typ, data = mail.search(None, criteria)

        if typ != "OK" or not data or not data[0]:
            return []

        email_ids = data[0].split()
        if limit and limit > 0:
            email_ids = email_ids[-limit:]
        email_ids = list(reversed(email_ids))

        for eid in email_ids:
            try:
                uid, header_msg, header_bytes = fetch_header_message(mail, eid)
                if header_msg is None:
                    continue

                message_id = sanitize_for_external_output(
                    (header_msg.get("Message-ID") or "").strip() or eid.decode(),
                    max_length=200,
                )
                subject = decode_header_value(
                    header_msg.get("Subject", ""),
                    max_length=300,
                )
                from_ = decode_header_value(
                    header_msg.get("From", ""),
                    max_length=200,
                )
                date_formatted = format_email_date(header_msg.get("Date", ""))

                body_text = ""
                try:
                    body_text = fetch_body_text(mail, eid, header_bytes)
                except Exception as body_error:
                    print(
                        f"Error fetching body text for email ID {eid!r} "
                        f"for account {account.get('name')}: {body_error}"
                    )

                snippet = make_snippet(body_text, max_length=220)

                results.append(
                    {
                        "account": sanitize_for_external_output(
                            account["name"], max_length=80
                        ),
                        "from": from_,
                        "subject": subject,
                        "date": date_formatted,
                        "snippet": snippet,
                        "important": is_important(subject, from_),
                        "message_id": message_id,
                        "uid": uid or eid.decode(),
                    }
                )
            except Exception as e:
                print(
                    f"Error fetching email ID {eid!r} for account "
                    f"{account.get('name')}: {e}"
                )

    except Exception as e:
        print(f"Error fetching emails for account {account.get('name')}: {e}")
    finally:
        if mail is not None:
            try:
                mail.logout()
            except Exception:
                pass

    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["unread", "recent"], default="unread")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--hours", type=int, default=None)
    parser.add_argument("--account", type=str, default=None)
    args = parser.parse_args()

    accounts = [a for a in load_accounts() if a.get("enabled", True)]

    for acc in accounts:
        if args.account and acc.get("name") != args.account:
            continue

        emails = fetch_emails(acc, mode=args.mode, hours=args.hours, limit=args.limit)
        for item in emails:
            print(json.dumps(item, ensure_ascii=False))


if __name__ == "__main__":
    main()