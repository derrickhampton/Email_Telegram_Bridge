import re

from draft_reply import create_pending_reply
from ignore_state import mark_ignored
from log_utils import log_event
from send_reply import send_pending_reply, cancel_pending_reply
from ollama_drafts import build_simple_draft_body, generate_deepthink_draft

CMD_PREFIX = r"(?:/)?"
CMD_SUFFIX = r"(?:@\w+)?"

DRAFT_CMD_RE = re.compile(
    rf"^\s*{CMD_PREFIX}(?:reply|draft_reply){CMD_SUFFIX}\s+(\S+)\s+([\s\S]+?)\s*$",
    re.IGNORECASE,
)

APPROVE_CMD_RE = re.compile(
    rf"^\s*{CMD_PREFIX}approve_reply{CMD_SUFFIX}\s+(\S+)\s*$",
    re.IGNORECASE,
)

CANCEL_CMD_RE = re.compile(
    rf"^\s*{CMD_PREFIX}cancel_reply{CMD_SUFFIX}\s+(\S+)\s*$",
    re.IGNORECASE,
)


def build_draft_preview_text(source_message_id, pending):
    return "\n".join([
        f"Draft prepared for {source_message_id}",
        f"Approval ID: {pending['approval_id']}",
        f"Account: {pending['account']}",
        f"To: {pending['to']}",
        f"Subject: {pending['subject']}",
        f"Expires: {pending['expires_at']}",
        "",
        "Body:",
        pending["body"],
    ])


def build_draft_preview_reply_markup(approval_id):
    return {
        "inline_keyboard": [
            [
                {"text": "✅ Approve", "callback_data": f"approve:{approval_id}"},
                {"text": "❌ Cancel", "callback_data": f"cancel:{approval_id}"},
            ]
        ]
    }


def build_sent_text(approval_id, sent):
    return "\n".join([
        f"✅ Reply sent",
        f"Approval ID: {approval_id}",
        f"To: {sent['to']}",
        f"Subject: {sent['subject']}",
        f"Sent at: {sent['sent_at']}",
    ])


def build_cancelled_text(approval_id, cancelled):
    return "\n".join([
        f"❌ Reply cancelled",
        f"Approval ID: {approval_id}",
        f"To: {cancelled['to']}",
        f"Status: {cancelled['status']}",
    ])


def build_ignored_text(email_obj):
    return "\n".join([
        "🚫 Ignored",
        f"From: {email_obj.get('from_email', '')}",
        f"Subject: {email_obj.get('subject', '')}",
        "",
        "No draft was created.",
    ])



def _trim_snippet(snippet, max_len=220):
    snippet = (snippet or "").strip()
    if len(snippet) <= max_len:
        return snippet
    return snippet[: max_len - 3].rstrip() + "..."


def build_deep_think_draft_body(email_obj):
    sender = (email_obj.get("from_email") or "").strip()
    subject = (email_obj.get("subject") or "").strip()
    snippet = _trim_snippet(email_obj.get("snippet") or "")

    opener = "👋 Thanks for your email."
    if sender:
        opener = f"👋 Thanks for reaching out."

    lines = [opener]

    if subject:
        lines.append(f"We received your note about “{subject}.”")

    if snippet:
        lines.append("We’ve reviewed your message and appreciate the details.")

    lines.append("📩 We’ll follow up after review.")

    body = generate_deepthink_draft(email_obj, account_name=email_obj.get("account"))

    return body


def create_pending_reply_from_email_obj(email_obj, body, telegram_request):
    return create_pending_reply(
        account=email_obj["account"],
        source_message_id=email_obj["message_id"],
        source_email_id=email_obj.get("id"),
        sender_email=email_obj["from_email"],
        original_subject=email_obj.get("subject", ""),
        body=body,
        telegram_request=telegram_request,
    )


def handle_telegram_command(
    text,
    lookup_email_by_message_id,
    telegram_send_message,
):
    text = (text or "").strip()
    log_event("telegram_command_received", text=text)
    m = DRAFT_CMD_RE.match(text)
    if m:
        source_message_id = m.group(1).strip()
        body = m.group(2).strip()
        log_event(
                "telegram_draft_command_matched",
                source_message_id=source_message_id,
                body_preview=body[:120],
            )

        email_obj = lookup_email_by_message_id(source_message_id)
        log_event("telegram_email_lookup_complete", email_found=bool(email_obj))

        if not email_obj:
            telegram_send_message(
                f"Could not find email for message_id: {source_message_id}"
            )
            return True

        try:
            pending = create_pending_reply_from_email_obj(
                email_obj=email_obj,
                body=body,
                telegram_request=text,
            )
        except Exception as e:
            log_event("telegram_draft_creation_failed", source_message_id=source_message_id, error=str(e))
            telegram_send_message(f"Draft creation failed for {source_message_id}: {e}")
            return True

        preview_text = build_draft_preview_text(source_message_id, pending)
        reply_markup = build_draft_preview_reply_markup(pending["approval_id"])
        ok = telegram_send_message(preview_text, reply_markup=reply_markup)
        log_event(
            "telegram_draft_preview_sent",
            draft_preview_sent=ok,
            approval_id=pending["approval_id"],
        )
        return True

    m = APPROVE_CMD_RE.match(text)
    if m:
        approval_id = m.group(1).strip()
        log_event("telegram_approve_command_matched", approval_id=approval_id)
        try:
            sent = send_pending_reply(approval_id)
            telegram_send_message(build_sent_text(approval_id, sent))
        except Exception as e:
            log_event("telegram_approve_failed", approval_id=approval_id, error=str(e))
            telegram_send_message(f"approve_reply failed for {approval_id}: {e}")
        return True

    m = CANCEL_CMD_RE.match(text)
    if m:
        approval_id = m.group(1).strip()
        log_event("telegram_cancel_command_matched", approval_id=approval_id)
        try:
            cancelled = cancel_pending_reply(approval_id)
            telegram_send_message(build_cancelled_text(approval_id, cancelled))
        except Exception as e:
            log_event("telegram_cancel_failed", approval_id=approval_id, error=str(e))
            telegram_send_message(f"cancel_reply failed for {approval_id}: {e}")
        return True

    log_event("telegram_command_unmatched", text=text)
    return False


def handle_telegram_callback(
    callback_data,
    callback_query_id,
    callback_message_chat_id,
    callback_message_id,
    telegram_answer_callback_query,
    telegram_edit_message_text,
    lookup_email_by_message_id,
    lookup_email_by_token,
):
    callback_data = (callback_data or "").strip()
    log_event("telegram_callback_received", data=callback_data)

    if ":" not in callback_data:
        telegram_answer_callback_query(callback_query_id, text="Unknown action", show_alert=False)
        return True

    action, value = callback_data.split(":", 1)
    action = action.strip().lower()
    value = value.strip()

    log_event("telegram_callback_matched", action=action, value=value)

    if action == "draft_simple":
        email_obj = lookup_email_by_token(value)
        if not email_obj:
            telegram_answer_callback_query(callback_query_id, text="Email not found", show_alert=True)
            return True

        try:
            body = build_simple_draft_body(
                    email_obj,
                    account_name=email_obj.get("account"),
                )
            pending = create_pending_reply_from_email_obj(
                email_obj=email_obj,
                body=body,
                telegram_request=f"callback:draft_simple:{value}",
            )
            telegram_answer_callback_query(callback_query_id, text="Simple draft created", show_alert=False)
            telegram_edit_message_text(
                chat_id=callback_message_chat_id,
                message_id=callback_message_id,
                text=build_draft_preview_text(email_obj.get("message_id", ""), pending),
                reply_markup=build_draft_preview_reply_markup(pending["approval_id"]),
            )
        except Exception as e:
            log_event("telegram_draft_creation_failed", source_message_id=email_obj.get("message_id", ""), error=str(e))
            telegram_answer_callback_query(callback_query_id, text=f"Simple draft failed: {e}", show_alert=True)
        return True

    if action == "draft_deep":
        email_obj = lookup_email_by_token(value)
        if not email_obj:
            telegram_answer_callback_query(callback_query_id, text="Email not found", show_alert=True)
            return True

        try:
            body = build_deep_think_draft_body(email_obj)
            pending = create_pending_reply_from_email_obj(
                email_obj=email_obj,
                body=body,
                telegram_request=f"callback:draft_deep:{value}",
            )
            telegram_answer_callback_query(callback_query_id, text="Deep draft created", show_alert=False)
            telegram_edit_message_text(
                chat_id=callback_message_chat_id,
                message_id=callback_message_id,
                text=build_draft_preview_text(email_obj.get("message_id", ""), pending),
                reply_markup=build_draft_preview_reply_markup(pending["approval_id"]),
            )
        except Exception as e:
            log_event("telegram_draft_creation_failed", source_message_id=email_obj.get("message_id", ""), error=str(e))
            telegram_answer_callback_query(callback_query_id, text=f"Deep draft failed: {e}", show_alert=True)
        return True

    if action == "ignore":
        email_obj = lookup_email_by_token(value)
        if not email_obj:
            telegram_answer_callback_query(callback_query_id, text="Email not found", show_alert=True)
            return True

        try:
            mark_ignored(
                message_id=email_obj.get("message_id", ""),
                account=email_obj.get("account", ""),
                from_email=email_obj.get("from_email", ""),
                subject=email_obj.get("subject", ""),
                reason="telegram_ignore_button",
            )
            telegram_answer_callback_query(callback_query_id, text="Ignored", show_alert=False)
            telegram_edit_message_text(
                chat_id=callback_message_chat_id,
                message_id=callback_message_id,
                text=build_ignored_text(email_obj),
                reply_markup=None,
            )
        except Exception as e:
            log_event("telegram_ignore_failed", error=str(e))
            telegram_answer_callback_query(callback_query_id, text=f"Ignore failed: {e}", show_alert=True)
        return True

    if action == "approve":
        try:
            sent = send_pending_reply(value)
            telegram_answer_callback_query(callback_query_id, text="Reply sent", show_alert=False)
            telegram_edit_message_text(
                chat_id=callback_message_chat_id,
                message_id=callback_message_id,
                text=build_sent_text(value, sent),
                reply_markup=None,
            )
        except Exception as e:
            log_event("telegram_callback_approve_failed", error=str(e))
            telegram_answer_callback_query(callback_query_id, text=f"Approve failed: {e}", show_alert=True)
        return True

    if action == "cancel":
        try:
            cancelled = cancel_pending_reply(value)
            telegram_answer_callback_query(callback_query_id, text="Reply cancelled", show_alert=False)
            telegram_edit_message_text(
                chat_id=callback_message_chat_id,
                message_id=callback_message_id,
                text=build_cancelled_text(value, cancelled),
                reply_markup=None,
            )
        except Exception as e:
            log_event("telegram_callback_cancel_failed", error=str(e))
            telegram_answer_callback_query(callback_query_id, text=f"Cancel failed: {e}", show_alert=True)
        return True

    telegram_answer_callback_query(callback_query_id, text="Unknown action", show_alert=False)
    return True