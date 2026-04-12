import argparse
import time

from fetch_emails import fetch_emails, load_accounts
from state_store import load_state, save_state, has_seen, mark_seen, prune_old_entries
from telegram_client import send_telegram_message
from email_utils import sanitize_for_external_output
from recent_email_store import store_recent_email
from log_utils import log_event
from env_loader import load_env_file
load_env_file()

DEFAULT_MAX_MESSAGES_PER_RUN = 5
DEFAULT_SEND_DELAY_SECONDS = 0.2


def is_reply_ui_blocked(from_email):
    """
    UI-level button gating only.

    This is intentionally lighter than send-time validation:
    - block obvious system/non-reply senders
    - do not block merely because the domain is not in the send allowlist

    Final enforcement still happens later during draft/send creation.
    """
    from_email = (from_email or "").strip().lower()
    if not from_email or "@" not in from_email:
        return True, "invalid recipient"

    local, _domain = from_email.split("@", 1)

    blocked_prefixes = {
        "noreply",
        "no-reply",
        "donotreply",
        "mailer-daemon",
    }
    if local in blocked_prefixes:
        return True, f"blocked sender prefix: {local}"

    bulk_hints = ["list-", "bounce", "newsletter", "notifications", "announce"]
    if any(hint in local for hint in bulk_hints):
        return True, "bulk/system sender blocked"

    return False, ""


def build_notification_reply_markup(item):
    message_token = sanitize_for_external_output(item.get("message_token", ""), max_length=64)
    from_email = (item.get("from_email") or "").strip()
    subject = sanitize_for_external_output(item.get("subject", ""), max_length=300)

    if not message_token:
        print("[poll_and_notify] no message_token available; no buttons will be shown")
        return None

    blocked, blocked_reason = is_reply_ui_blocked(from_email)

    log_event(
        "notification_buttons_built",
        from_email=from_email,
        subject=subject,
        blocked_result=blocked,
        blocked_reason=blocked_reason,
        message_token=message_token,
    )

    if blocked:
        return {
            "inline_keyboard": [
                [
                    {"text": "🚫 Ignore", "callback_data": f"ignore:{message_token}"},
                ],
            ]
        }

    return {
        "inline_keyboard": [
            [
                {"text": "✉️ Simple Draft", "callback_data": f"draft_simple:{message_token}"},
                {"text": "🧠 Deep Think Draft", "callback_data": f"draft_deep:{message_token}"},
            ],
            [
                {"text": "🚫 Ignore", "callback_data": f"ignore:{message_token}"},
            ],
        ]
    }


def build_message(item):
    account = sanitize_for_external_output(item.get("account", ""), max_length=80)
    from_ = sanitize_for_external_output(item.get("from", ""), max_length=200)
    subject = sanitize_for_external_output(item.get("subject", ""), max_length=300)
    snippet = sanitize_for_external_output(item.get("snippet", ""), max_length=500)
    date = sanitize_for_external_output(item.get("date", ""), max_length=80)
    from_email = (item.get("from_email") or "").strip()

    prefix = "🔴 Important Email\n" if item.get("important") else "📬 New Email\n"

    blocked, _reason = is_reply_ui_blocked(from_email)
    action_note = "Choose an action below."
    if blocked:
        action_note = "Replies are disabled for this sender. You can ignore this message."

    return (
        f"{prefix}"
        f"Account: {account}\n"
        f"From: {from_}\n"
        f"Subject: {subject}\n"
        f"Date: {date}\n"
        f"Snippet: {snippet}\n\n"
        f"{action_note}"
    )


def process_accounts(
    account_name=None,
    important_only=False,
    fetch_limit=10,
    max_messages_per_run=DEFAULT_MAX_MESSAGES_PER_RUN,
    send_delay_seconds=DEFAULT_SEND_DELAY_SECONDS,
):
    state = load_state()
    prune_old_entries(state, max_age_days=14)

    accounts = [a for a in load_accounts() if a.get("enabled", True)]
    total_sent = 0

    log_event(
            "poll_accounts_loaded",
            accounts=[a.get("name") for a in accounts],
            account_count=len(accounts),
        )
        
    for account in accounts:
        if account_name and account.get("name") != account_name:
            continue

        if total_sent >= max_messages_per_run:
            break

        try:
            log_event(
                "poll_fetch_start",
                account=account.get("name"),
                fetch_limit=fetch_limit,
                mode="unread",
            )
            emails = fetch_emails(
                account,
                mode="unread",
                hours=None,
                limit=fetch_limit,
            )
            log_event(
                "poll_fetch_complete",
                account=account.get("name"),
                fetched_count=len(emails),
            )
        except Exception as e:
            print(f"Notifier error for account {account.get('name')}: {e}")
            continue

        unseen_items = []
        for item in emails:
            key = item.get("message_id") or item.get("uid")
            if not key:
                continue

            try:
                if has_seen(state, account["name"], key):
                    continue
            except Exception as e:
                print(
                    f"State check error for account {account.get('name')} "
                    f"message {key}: {e}"
                )
                continue

            unseen_items.append(item)

        if important_only:
            unseen_items = [item for item in unseen_items if item.get("important")]

        log_event(
            "poll_unseen_items",
            account=account.get("name"),
            unseen_count=len(unseen_items),
            important_only=important_only,
        )

        remaining_capacity = max_messages_per_run - total_sent
        if remaining_capacity <= 0:
            break

        items_to_send = unseen_items[:remaining_capacity]

        for item in items_to_send:
            key = item.get("message_id") or item.get("uid")
            if not key:
                continue

            try:
                stored_item = store_recent_email(item) or item
                reply_markup = build_notification_reply_markup(stored_item)

                log_event(
                    "telegram_notification_send_start",
                    account=account.get("name"),
                    key=key,
                    message_id=stored_item.get("message_id"),
                    message_token=stored_item.get("message_token"),
                    from_email=stored_item.get("from_email"),
                    subject=stored_item.get("subject"),
                )

                sent = send_telegram_message(
                    build_message(stored_item),
                    reply_markup=reply_markup,
                )

                if sent:
                    
                    log_event(
                        "telegram_notification_send_success",
                        account=account.get("name"),
                        key=key,
                        message_id=stored_item.get("message_id"),
                        message_token=stored_item.get("message_token"),
                    )
                    mark_seen(state, account["name"], key)
                    total_sent += 1

                    if send_delay_seconds and send_delay_seconds > 0:
                        time.sleep(send_delay_seconds)
                else:
                    log_event(
                        "telegram_notification_send_failed",
                        account=account.get("name"),
                        key=key,
                        message_id=stored_item.get("message_id"),
                        message_token=stored_item.get("message_token"),
                    )
            except Exception as e:
                log_event(
                    "poll_processing_error",
                    account=account.get("name"),
                    key=key,
                    message_id=item.get("message_id"),
                    error=str(e),
                )

    save_state(state)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=int, default=None)
    parser.add_argument("--account", type=str, default=None)
    parser.add_argument("--important-only", action="store_true")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument(
        "--max-messages-per-run",
        type=int,
        default=DEFAULT_MAX_MESSAGES_PER_RUN,
    )
    parser.add_argument(
        "--send-delay-seconds",
        type=float,
        default=DEFAULT_SEND_DELAY_SECONDS,
    )
    args = parser.parse_args()

    if args.once or not args.interval:
        process_accounts(
            account_name=args.account,
            important_only=args.important_only,
            fetch_limit=args.limit,
            max_messages_per_run=args.max_messages_per_run,
            send_delay_seconds=args.send_delay_seconds,
        )
        return

    while True:
        process_accounts(
            account_name=args.account,
            important_only=args.important_only,
            fetch_limit=args.limit,
            max_messages_per_run=args.max_messages_per_run,
            send_delay_seconds=args.send_delay_seconds,
        )
        time.sleep(args.interval)


if __name__ == "__main__":
    main()