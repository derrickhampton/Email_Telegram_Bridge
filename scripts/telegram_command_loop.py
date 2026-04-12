import json
import os
import time

from recent_email_store import lookup_email_by_message_id, lookup_email_by_token
from telegram_client import (
    answer_callback_query,
    edit_telegram_message_text,
    extract_telegram_events,
    get_telegram_updates,
    is_allowed_chat,
    send_telegram_message,
)
from telegram_commands import (
    handle_telegram_callback,
    handle_telegram_command,
)
from log_utils import log_event
from env_loader import load_env_file
load_env_file()

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(SKILL_DIR, "data")
OFFSET_PATH = os.path.join(DATA_DIR, "telegram_offset.json")


def load_offset():
    try:
        with open(OFFSET_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("offset")
    except Exception:
        return None


def save_offset(offset):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp_path = OFFSET_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump({"offset": offset}, f, indent=2)
    os.replace(tmp_path, OFFSET_PATH)


def main():
    offset = load_offset()
    log_event("telegram_loop_start", offset=offset)

while True:
try:
                log_event("telegram_poll_start", offset=offset)            payload = get_telegram_updates(
                offset=offset,
                timeout=20,
                allowed_updates=["message", "callback_query"],
            )

if not payload:
            log_event("telegram_poll_start", offset=offset)                time.sleep(3)
continue

events = extract_telegram_events(payload)
log_event("telegram_poll_complete",
                  offset=offset, event_count=len(events))
for event in events:
                update_id = event.get("update_id")
                if update_id is not None:
                    offset = int(update_id) + 1
                log_event("telegram_offset_saved", offset=offset)
                chat_id = event.get("chat_id")
                kind = event.get("kind")

                log_event(
                    "telegram_event_received",
                    kind=kind,
                    update_id=event.get("update_id"),
                    chat_id=event.get("chat_id"),
                    message_id=event.get("message_id"),
                    callback_query_id=event.get("callback_query_id"),
                    data=event.get("data"),
                    text=event.get("text"),
                )
                if not is_allowed_chat(chat_id):
                    log_event(
                        "telegram_event_unauthorized",
                        kind=kind,
                        chat_id=chat_id,
                    )
                    continue

if kind == "message":
                    text = event.get("text", "")
                    handled = handle_telegram_command(
                        text=text,
                        lookup_email_by_message_id=lookup_email_by_message_id,
                        telegram_send_message=send_telegram_message,
                    )
log_event(
                            "telegram_callback_handled",
                            handled=handled,
                            chat_id=chat_id,
                            message_id=event.get("message_id"),
                            callback_query_id=event.get("callback_query_id"),
                            data=event.get("data"),
                        )
if not handled:
                        send_telegram_message(
                            "Unknown command.\n\n"
                            "Supported commands:\n"
                            "draft_reply <message_id> <text>\n"
                            "approve_reply <approval_id>\n"
                            "cancel_reply <approval_id>"
                        )

elif kind == "callback_query":
                    handled = handle_telegram_callback(
                        callback_data=event.get("data", ""),
                        callback_query_id=event.get("callback_query_id"),
                        callback_message_chat_id=event.get("chat_id"),
                        callback_message_id=event.get("message_id"),
                        telegram_answer_callback_query=answer_callback_query,
                        telegram_edit_message_text=edit_telegram_message_text,
                        lookup_email_by_message_id=lookup_email_by_message_id,
                        lookup_email_by_token=lookup_email_by_token,
                    )
                    log_event(
                        "telegram_callback_handled",
                        handled=handled,
                        chat_id=chat_id,
                        message_id=event.get("message_id"),
                        callback_query_id=event.get("callback_query_id"),
                        data=event.get("data"),
                    )

else:
                    log_event("telegram_event_unknown", kind=kind, event=event)

save_offset(offset)
log_event("telegram_offset_saved", offset=offset)

except KeyboardInterrupt:
log_event("telegram_loop_stopping", reason="KeyboardInterrupt")
raise
except Exception as e:
log_event("telegram_loop_error", error=str(e))
time.sleep(5)


if __name__ == "__main__":
    main()