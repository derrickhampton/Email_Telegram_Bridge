import json
import os
import urllib.error
import urllib.parse
import urllib.request

from env_loader import load_env_file
load_env_file()

def _get_bot_token():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN env variable")
    return token


def _get_allowed_chat_id():
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not chat_id:
        raise RuntimeError("Missing TELEGRAM_CHAT_ID env variable")
    return str(chat_id).strip()


def is_allowed_chat(chat_id):
    try:
        allowed_chat_id = _get_allowed_chat_id()
    except Exception:
        return False
    return str(chat_id).strip() == allowed_chat_id


def _telegram_api_post(method_name, data):
    token = _get_bot_token()
    url = f"https://api.telegram.org/bot{token}/{method_name}"

    body = json.dumps(data).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
    }

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")

    with urllib.request.urlopen(req, timeout=30) as response:
        raw = response.read().decode("utf-8", errors="replace")

    payload = json.loads(raw)
    if not payload.get("ok"):
        raise RuntimeError(f"Telegram API {method_name} returned not ok: {payload}")

    return payload


def send_telegram_message(text, reply_markup=None):
    try:
        chat_id = _get_allowed_chat_id()
        data = {
            "chat_id": chat_id,
            "text": text,
        }
        if reply_markup is not None:
            data["reply_markup"] = reply_markup

        _telegram_api_post("sendMessage", data)
        return True
    except urllib.error.HTTPError as e:
        error_body = ""
        try:
            error_body = e.read().decode("utf-8", errors="replace")
        except Exception:
            error_body = "<unable to read response body>"
        print(f"Failed to send Telegram message: HTTP {e.code} {e.reason} - {error_body}")
        return False
    except urllib.error.URLError as e:
        print(f"Failed to send Telegram message: URL error - {e}")
        return False
    except Exception as e:
        print(f"Failed to send Telegram message: {e}")
        return False


def answer_callback_query(callback_query_id, text=None, show_alert=False):
    try:
        data = {
            "callback_query_id": callback_query_id,
            "show_alert": bool(show_alert),
        }
        if text:
            data["text"] = text
        _telegram_api_post("answerCallbackQuery", data)
        return True
    except Exception as e:
        print(f"Failed to answer callback query: {e}")
        return False


def edit_telegram_message_text(chat_id, message_id, text, reply_markup=None):
    try:
        data = {
            "chat_id": str(chat_id).strip(),
            "message_id": int(message_id),
            "text": text,
        }
        if reply_markup is not None:
            data["reply_markup"] = reply_markup
        _telegram_api_post("editMessageText", data)
        return True
    except Exception as e:
        print(f"Failed to edit Telegram message text: {e}")
        return False


def get_telegram_updates(offset=None, timeout=20, allowed_updates=None):
    try:
        token = _get_bot_token()
    except Exception as e:
        print(f"Error: {e}")
        return None

    url = f"https://api.telegram.org/bot{token}/getUpdates"
    params = {
        "timeout": int(timeout),
    }

    if offset is not None:
        params["offset"] = int(offset)

    if allowed_updates is not None:
        params["allowed_updates"] = json.dumps(allowed_updates)

    query = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{url}?{query}", method="GET")

    try:
        with urllib.request.urlopen(req, timeout=timeout + 10) as response:
            raw = response.read().decode("utf-8", errors="replace")
        payload = json.loads(raw)
        if not payload.get("ok"):
            print(f"Telegram getUpdates returned not ok: {payload}")
            return None
        return payload
    except urllib.error.HTTPError as e:
        error_body = ""
        try:
            error_body = e.read().decode("utf-8", errors="replace")
        except Exception:
            error_body = "<unable to read response body>"
        print(f"Failed to get Telegram updates: HTTP {e.code} {e.reason} - {error_body}")
        return None
    except urllib.error.URLError as e:
        print(f"Failed to get Telegram updates: URL error - {e}")
        return None
    except Exception as e:
        print(f"Failed to get Telegram updates: {e}")
        return None


def extract_telegram_events(updates_payload):
    events = []
    if not updates_payload or not isinstance(updates_payload, dict):
        return events

    for item in updates_payload.get("result", []):
        if not isinstance(item, dict):
            continue

        update_id = item.get("update_id")

        message = item.get("message") or item.get("edited_message")
        if isinstance(message, dict):
            chat = message.get("chat", {})
            chat_id = chat.get("id")
            text = message.get("text")

            if chat_id is not None and text:
                events.append({
                    "kind": "message",
                    "update_id": update_id,
                    "chat_id": str(chat_id).strip(),
                    "text": text.strip(),
                    "from_username": ((message.get("from") or {}).get("username") or "").strip(),
                    "message_id": message.get("message_id"),
                })

        callback_query = item.get("callback_query")
        if isinstance(callback_query, dict):
            message = callback_query.get("message") or {}
            chat = message.get("chat") or {}
            chat_id = chat.get("id")
            message_id = message.get("message_id")
            callback_data = callback_query.get("data")
            callback_query_id = callback_query.get("id")

            if chat_id is not None and message_id is not None and callback_data and callback_query_id:
                events.append({
                    "kind": "callback_query",
                    "update_id": update_id,
                    "chat_id": str(chat_id).strip(),
                    "message_id": message_id,
                    "callback_query_id": callback_query_id,
                    "data": str(callback_data).strip(),
                    "from_username": ((callback_query.get("from") or {}).get("username") or "").strip(),
                })

    return events