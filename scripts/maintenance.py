import argparse
import json
import os
from datetime import datetime, timedelta, timezone

from env_loader import load_env_file
from log_utils import log_event

load_env_file()

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(SKILL_DIR, "data")

PENDING_REPLIES_PATH = os.path.join(DATA_DIR, "pending_replies.json")
IGNORED_EMAILS_PATH = os.path.join(DATA_DIR, "ignored_emails.json")
RECENT_EMAILS_PATH = os.path.join(DATA_DIR, "recent_emails.json")


def utc_now():
    return datetime.now(timezone.utc)


def parse_iso(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def load_json_file(path, default):
    ensure_data_dir()
    if not os.path.exists(path):
        return default

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
        return default
    except Exception as e:
        log_event(
            "maintenance_load_json_failed",
            path=path,
            error=str(e),
        )
        return default


def save_json_file(path, data):
    ensure_data_dir()
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, path)


def prune_pending_replies(days=7, dry_run=False):
    data = load_json_file(PENDING_REPLIES_PATH, {"pending": {}})
    pending = data.get("pending", {})
    if not isinstance(pending, dict):
        pending = {}

    cutoff = utc_now() - timedelta(days=days)

    kept = {}
    removed = []

    for approval_id, item in pending.items():
        if not isinstance(item, dict):
            removed.append({
                "approval_id": approval_id,
                "reason": "invalid_record",
            })
            continue

        status = (item.get("status") or "").strip().lower()

        if status == "pending":
            kept[approval_id] = item
            continue

        timestamp = (
            item.get("sent_at")
            or item.get("cancelled_at")
            or item.get("expires_at")
            or item.get("approved_at")
            or item.get("created_at")
        )

        dt = parse_iso(timestamp)
        if dt is None:
            kept[approval_id] = item
            continue

        if dt < cutoff:
            removed.append({
                "approval_id": approval_id,
                "status": status,
                "timestamp": timestamp,
                "to": item.get("to"),
                "subject": item.get("subject"),
            })
        else:
            kept[approval_id] = item

    result = {
        "path": PENDING_REPLIES_PATH,
        "before_count": len(pending),
        "after_count": len(kept),
        "removed_count": len(removed),
        "removed": removed,
        "dry_run": dry_run,
    }

    if not dry_run:
        data["pending"] = kept
        save_json_file(PENDING_REPLIES_PATH, data)

    log_event(
        "maintenance_prune_pending_replies",
        path=PENDING_REPLIES_PATH,
        before_count=result["before_count"],
        after_count=result["after_count"],
        removed_count=result["removed_count"],
        dry_run=dry_run,
        retention_days=days,
    )

    return result


def prune_ignored_emails(days=30, dry_run=False):
    data = load_json_file(IGNORED_EMAILS_PATH, {"ignored": {}})
    ignored = data.get("ignored", {})
    if not isinstance(ignored, dict):
        ignored = {}

    cutoff = utc_now() - timedelta(days=days)

    kept = {}
    removed = []

    for message_id, item in ignored.items():
        if not isinstance(item, dict):
            removed.append({
                "message_id": message_id,
                "reason": "invalid_record",
            })
            continue

        timestamp = item.get("ignored_at")
        dt = parse_iso(timestamp)

        if dt is None:
            kept[message_id] = item
            continue

        if dt < cutoff:
            removed.append({
                "message_id": message_id,
                "timestamp": timestamp,
                "account": item.get("account"),
                "from_email": item.get("from_email"),
                "subject": item.get("subject"),
            })
        else:
            kept[message_id] = item

    result = {
        "path": IGNORED_EMAILS_PATH,
        "before_count": len(ignored),
        "after_count": len(kept),
        "removed_count": len(removed),
        "removed": removed,
        "dry_run": dry_run,
    }

    if not dry_run:
        data["ignored"] = kept
        save_json_file(IGNORED_EMAILS_PATH, data)

    log_event(
        "maintenance_prune_ignored_emails",
        path=IGNORED_EMAILS_PATH,
        before_count=result["before_count"],
        after_count=result["after_count"],
        removed_count=result["removed_count"],
        dry_run=dry_run,
        retention_days=days,
    )

    return result


def prune_recent_emails(max_messages=500, dry_run=False):
    data = load_json_file(RECENT_EMAILS_PATH, {"messages": {}, "tokens": {}})
    messages = data.get("messages", {})
    tokens = data.get("tokens", {})

    if not isinstance(messages, dict):
        messages = {}
    if not isinstance(tokens, dict):
        tokens = {}

    ordered = sorted(
        messages.items(),
        key=lambda kv: kv[1].get("stored_at", "") if isinstance(kv[1], dict) else "",
        reverse=True,
    )

    kept_messages = dict(ordered[:max_messages])
    kept_message_ids = set(kept_messages.keys())

    kept_tokens = {}
    removed_tokens = []

    for token, message_id in tokens.items():
        if message_id in kept_message_ids:
            kept_tokens[token] = message_id
        else:
            removed_tokens.append({
                "message_token": token,
                "message_id": message_id,
            })

    removed_messages = [
        {
            "message_id": message_id,
            "message_token": item.get("message_token") if isinstance(item, dict) else None,
            "account": item.get("account") if isinstance(item, dict) else None,
            "from_email": item.get("from_email") if isinstance(item, dict) else None,
            "subject": item.get("subject") if isinstance(item, dict) else None,
            "stored_at": item.get("stored_at") if isinstance(item, dict) else None,
        }
        for message_id, item in ordered[max_messages:]
    ]

    result = {
        "path": RECENT_EMAILS_PATH,
        "before_message_count": len(messages),
        "after_message_count": len(kept_messages),
        "removed_message_count": len(removed_messages),
        "before_token_count": len(tokens),
        "after_token_count": len(kept_tokens),
        "removed_token_count": len(removed_tokens),
        "removed_messages": removed_messages,
        "removed_tokens": removed_tokens,
        "dry_run": dry_run,
    }

    if not dry_run:
        data["messages"] = kept_messages
        data["tokens"] = kept_tokens
        save_json_file(RECENT_EMAILS_PATH, data)

    log_event(
        "maintenance_prune_recent_emails",
        path=RECENT_EMAILS_PATH,
        before_message_count=result["before_message_count"],
        after_message_count=result["after_message_count"],
        removed_message_count=result["removed_message_count"],
        before_token_count=result["before_token_count"],
        after_token_count=result["after_token_count"],
        removed_token_count=result["removed_token_count"],
        dry_run=dry_run,
        max_messages=max_messages,
    )

    return result


def run_maintenance(
    pending_days=7,
    ignored_days=30,
    recent_max=500,
    dry_run=False,
):
    results = {
        "pending_replies": prune_pending_replies(days=pending_days, dry_run=dry_run),
        "ignored_emails": prune_ignored_emails(days=ignored_days, dry_run=dry_run),
        "recent_emails": prune_recent_emails(max_messages=recent_max, dry_run=dry_run),
    }

    log_event(
        "maintenance_run_complete",
        dry_run=dry_run,
        pending_removed=results["pending_replies"]["removed_count"],
        ignored_removed=results["ignored_emails"]["removed_count"],
        recent_messages_removed=results["recent_emails"]["removed_message_count"],
        recent_tokens_removed=results["recent_emails"]["removed_token_count"],
    )

    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--pending-days", type=int, default=7)
    parser.add_argument("--ignored-days", type=int, default=30)
    parser.add_argument("--recent-max", type=int, default=500)
    parser.add_argument(
        "--task",
        type=str,
        choices=["all", "pending", "ignored", "recent"],
        default="all",
    )
    args = parser.parse_args()

    if args.task == "pending":
        result = prune_pending_replies(days=args.pending_days, dry_run=args.dry_run)
    elif args.task == "ignored":
        result = prune_ignored_emails(days=args.ignored_days, dry_run=args.dry_run)
    elif args.task == "recent":
        result = prune_recent_emails(max_messages=args.recent_max, dry_run=args.dry_run)
    else:
        result = run_maintenance(
            pending_days=args.pending_days,
            ignored_days=args.ignored_days,
            recent_max=args.recent_max,
            dry_run=args.dry_run,
        )

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()