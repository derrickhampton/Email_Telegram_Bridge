import json
import os
import re
import urllib.error
import urllib.request

from log_utils import log_event
from env_loader import load_env_file
load_env_file()


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
ACCOUNTS_PATH = os.path.join(SKILL_DIR, "config", "accounts.json")

OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("EMAIL_DEEPTHINK_MODEL", "phi4-mini:latest")
OLLAMA_TEMPERATURE = float(os.getenv("EMAIL_DEEPTHINK_TEMPERATURE", "0.45"))


def load_accounts_config():
    with open(ACCOUNTS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("accounts", [])


def get_account_config(account_name):
    for account in load_accounts_config():
        if account.get("name") == account_name:
            return account
    return None


def get_account_reply_profile(account_name):
    account = get_account_config(account_name) or {}

    reply_profile = account.get("reply_profile") or {}
    if not isinstance(reply_profile, dict):
        reply_profile = {}

    email_address = (account.get("email") or "").strip()
    sending_domain = ""
    if "@" in email_address:
        sending_domain = email_address.split("@", 1)[1].strip().lower()

    style_notes = reply_profile.get("style_notes")
    if not isinstance(style_notes, list):
        style_notes = []

    return {
        "account_name": (account.get("name") or "").strip(),
        "email": email_address,
        "business_name": (reply_profile.get("business_name") or "").strip(),
        "sending_domain": (reply_profile.get("sending_domain") or sending_domain).strip(),
        "mailbox_role": (reply_profile.get("mailbox_role") or "general_info").strip(),
        "tone": (reply_profile.get("tone") or "professional, warm, concise").strip(),
        "allow_emojis": bool(reply_profile.get("allow_emojis", False)),
        "max_words": int(reply_profile.get("max_words") or 90),
        "default_signoff": (reply_profile.get("default_signoff") or "").strip(),
        "style_notes": [str(x).strip() for x in style_notes if str(x).strip()],
    }

def _join_sentences(parts):
    return " ".join(part.strip() for part in parts if part and part.strip()).strip()


def _maybe_signoff(body, reply_profile):
    default_signoff = (reply_profile.get("default_signoff") or "").strip()
    if default_signoff:
        return f"{body}\n\n{default_signoff}"
    return body


def build_simple_draft_body(email_obj, account_name=None):
    account_name = account_name or (email_obj.get("account") or "").strip()
    reply_profile = get_account_reply_profile(account_name)

    subject = (email_obj.get("subject") or "").strip()
    snippet = (email_obj.get("snippet") or "").strip()
    combined = f"{subject}\n{snippet}".lower()

    business_name = (reply_profile.get("business_name") or "").strip()
    mailbox_role = (reply_profile.get("mailbox_role") or "general_info").strip().lower()
    tone = (reply_profile.get("tone") or "professional, warm, concise").strip().lower()
    allow_emojis = bool(reply_profile.get("allow_emojis"))
    max_words = int(reply_profile.get("max_words") or 90)

    greeting = "Hi,"
    thanks = "thanks for reaching out."
    if business_name:
        thanks = f"thanks for reaching out to {business_name}."

    if allow_emojis:
        greeting = "Hi 👋,"
        thanks = f"thanks for reaching out{f' to {business_name}' if business_name else ''}. ✉️"

    if mailbox_role in {"support", "product_support"}:
        if _contains_any(combined, ["issue", "problem", "error", "bug", "help", "not working", "broken"]):
            body = _join_sentences([
                greeting,
                thanks,
                "We received your message and are taking a closer look at the details.",
                "We’ll follow up after review.",
            ])
        else:
            body = _join_sentences([
                greeting,
                thanks,
                "We received your message and will follow up after review.",
            ])

    elif mailbox_role in {"sales", "general_info", "info"}:
        if _contains_any(combined, ["price", "pricing", "quote", "cost", "how much", "rate", "rates"]):
            body = _join_sentences([
                greeting,
                thanks,
                "We received your pricing inquiry and will follow up after review.",
            ])
        else:
            body = _join_sentences([
                greeting,
                thanks,
                "We received your message and will follow up shortly.",
            ])

    elif mailbox_role in {"billing", "payments"}:
        if _contains_any(combined, ["invoice", "payment", "receipt", "billing", "refund"]):
            body = _join_sentences([
                greeting,
                thanks,
                "We received your message and are reviewing the details you sent.",
                "We’ll follow up after review.",
            ])
        else:
            body = _join_sentences([
                greeting,
                thanks,
                "We received your message and will follow up after review.",
            ])

    else:
        body = _join_sentences([
            greeting,
            thanks,
            "We received your message and will follow up after review.",
        ])

    # Tone shaping
    if "concise" in tone and len(body.split()) > max_words:
        words = body.split()
        body = " ".join(words[:max_words]).strip()

    body = _maybe_signoff(body, reply_profile)
    return body

def _trim_text(value, max_len):
    value = (value or "").strip()
    if len(value) <= max_len:
        return value
    return value[: max_len - 3].rstrip() + "..."


def _contains_any(text, terms):
    text = (text or "").lower()
    return any(term in text for term in terms)


def _word_count(text):
    return len(re.findall(r"\b\S+\b", text or ""))


def build_deepthink_prompt(email_obj, reply_profile):
    from_email = _trim_text(email_obj.get("from_email") or "", 200)
    subject = _trim_text(email_obj.get("subject") or "", 240)
    snippet = _trim_text(email_obj.get("snippet") or "", 700)

    business_name = reply_profile.get("business_name") or ""
    account_email = reply_profile.get("email") or ""
    sending_domain = reply_profile.get("sending_domain") or ""
    mailbox_role = reply_profile.get("mailbox_role") or "general_info"
    tone = reply_profile.get("tone") or "professional, warm, concise"
    allow_emojis = "yes" if reply_profile.get("allow_emojis") else "no"
    max_words = int(reply_profile.get("max_words") or 90)
    default_signoff = reply_profile.get("default_signoff") or ""
    style_notes = reply_profile.get("style_notes") or []

    style_notes_block = ""
    if style_notes:
        style_notes_block = "\n".join(f"- {note}" for note in style_notes)

    signoff_instruction = "Do not add a sign-off."
    if default_signoff:
        signoff_instruction = f'If a sign-off is appropriate, use exactly this sign-off: "{default_signoff}"'

    return f"""You are drafting a short email reply for a business inbox.

You are replying as:
Business name: {business_name}
Mailbox account: {account_email}
Sending domain: {sending_domain}
Mailbox role: {mailbox_role}
Tone: {tone}
Emojis allowed: {allow_emojis}

Write as this business account.
Do not mention or imply a different brand, company, or domain.
Keep the wording appropriate for the mailbox role.

Write a concise reply to the sender.
Use a professional, warm, human tone.
Make the reply feel thoughtful and context-aware.
Acknowledge the likely topic naturally based on the subject and snippet.

Do not invent facts.
Do not promise timelines, pricing, refunds, availability, or actions unless explicitly stated in the source email.
Do not make commitments on behalf of the business.
Do not over-explain.
Do not state that an order, booking, refund, quote, account change, or support action has been processed unless the source email explicitly says so.
Do not confirm receipt of attachments, screenshots, documents, or prior messages unless they are clearly present in the source email.
Do not ask for payment, personal data, login credentials, or sensitive information.
Do not reference internal systems, internal review, internal staff discussions, or backend processes.
Do not apologize for delays, mistakes, outages, billing issues, or service problems unless the source email explicitly indicates them.
Do not imply approval, acceptance, eligibility, availability, shipment, reservation, or completion unless stated in the source email.
Do not mention discounts, pricing details, next steps, or estimated response windows unless explicitly stated in the source email.
Do not sound overly certain when the sender’s request is ambiguous.
If details are unclear, acknowledge the message briefly without guessing.
Do not use emojis unless emojis are allowed for this mailbox.
Keep the tone measured and business-appropriate.
{signoff_instruction}

Additional style notes:
{style_notes_block if style_notes_block else "- Keep replies short and clear."}

Keep it under {max_words} words.
Do not include a subject line.
Do not include placeholders.
Do not include commentary or explanation.
Return only the reply body text.

Sender: {from_email}
Subject: {subject}
Snippet: {snippet}
"""


def normalize_llm_reply(text):
    text = (text or "").strip()

    if not text:
        return ""

    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 3:
            text = parts[1]
            if "\n" in text:
                text = text.split("\n", 1)[1]

    text = text.strip()

    if text.startswith('"') and text.endswith('"') and len(text) >= 2:
        text = text[1:-1].strip()

    if text.lower().startswith("subject:"):
        lines = text.splitlines()
        lines = [line for line in lines if not line.lower().startswith("subject:")]
        text = "\n".join(lines).strip()

    prefixes_to_strip = [
        "reply:",
        "draft:",
        "email reply:",
        "response:",
    ]
    lowered = text.lower()
    for prefix in prefixes_to_strip:
        if lowered.startswith(prefix):
            text = text[len(prefix):].strip()
            lowered = text.lower()

    cleaned_lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            if cleaned_lines and cleaned_lines[-1] != "":
                cleaned_lines.append("")
            continue
        cleaned_lines.append(stripped)

    text = "\n".join(cleaned_lines).strip()

    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    if len(text) > 1200:
        text = text[:1200].rstrip()

    return text


def validate_llm_reply(text, email_obj, reply_profile):
    text = (text or "").strip()
    if not text:
        return False, "empty reply"

    max_words = int(reply_profile.get("max_words") or 90)
    if _word_count(text) > max_words + 10:
        return False, f"reply too long ({_word_count(text)} words)"

    lowered = text.lower()

    disallowed_prefixes = [
        "subject:",
        "explanation:",
        "note:",
    ]
    if any(lowered.startswith(prefix) for prefix in disallowed_prefixes):
        return False, "contains non-body formatting"

    if not reply_profile.get("allow_emojis"):
        # Broad emoji/symbol range guard
        if re.search(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", text):
            return False, "contains emojis but mailbox policy disallows them"

    # Guardrails against risky invented commitments
    risky_patterns = [
        r"\bi have processed\b",
        r"\bwe have processed\b",
        r"\byour refund has been\b",
        r"\byour order has been\b",
        r"\byour booking has been\b",
        r"\bwe approved\b",
        r"\byou are approved\b",
        r"\bit is available\b",
        r"\bit will be shipped\b",
        r"\bwe will send you pricing shortly\b",
        r"\bwe will get back to you within\b",
        r"\bby tomorrow\b",
        r"\bwithin \d+ (hour|hours|day|days|business days)\b",
    ]
    for pattern in risky_patterns:
        if re.search(pattern, lowered):
            return False, f"contains risky pattern: {pattern}"

    if "internal review" in lowered or "our internal team" in lowered or "backend" in lowered:
        return False, "mentions internal process"

    # Avoid brand/domain drift
    sending_domain = (reply_profile.get("sending_domain") or "").strip().lower()
    if sending_domain:
        domain_mentions = re.findall(r"\b[a-z0-9.-]+\.[a-z]{2,}\b", lowered)
        for domain in domain_mentions:
            if domain != sending_domain and not domain.endswith(sending_domain):
                return False, f"mentions different domain: {domain}"

    return True, ""


def build_deepthink_fallback_body(email_obj, reply_profile):
    subject = (email_obj.get("subject") or "").strip()
    snippet = _trim_text(email_obj.get("snippet") or "", 260)
    combined = f"{subject}\n{snippet}".lower()

    business_name = (reply_profile.get("business_name") or "").strip()
    mailbox_role = (reply_profile.get("mailbox_role") or "general_info").strip()
    allow_emojis = bool(reply_profile.get("allow_emojis"))

    greeting = "Hi,"
    thanks = "thanks for your email"
    if business_name:
        thanks = f"thanks for reaching out to {business_name.lower()}"
    if allow_emojis:
        greeting = "Hi 👋,"

    if _contains_any(combined, ["price", "pricing", "quote", "cost", "how much", "rate", "rates"]):
        body = (
            f"{greeting} {thanks}. "
            "I received your message about pricing and appreciate the inquiry. "
            "I’ll follow up after reviewing the details."
        )
    elif _contains_any(combined, ["support", "issue", "problem", "error", "bug", "not working", "broken", "help"]):
        body = (
            f"{greeting} {thanks}. "
            "I received your note and reviewed the details you shared. "
            "I’ll follow up after taking a closer look."
        )
    elif _contains_any(combined, ["order", "invoice", "payment", "receipt", "billing", "refund"]):
        body = (
            f"{greeting} {thanks}. "
            "I received your message and am reviewing the information you sent. "
            "I’ll follow up after review."
        )
    elif mailbox_role in {"support", "product_support"}:
        body = (
            f"{greeting} {thanks}. "
            "I received your message and am taking a closer look at the details. "
            "I’ll follow up after review."
        )
    elif subject:
        body = (
            f"{greeting} {thanks} about {subject}. "
            "I received your message and will follow up after reviewing it."
        )
    else:
        body = (
            f"{greeting} {thanks}. "
            "I received your message and will follow up after reviewing it."
        )

    default_signoff = (reply_profile.get("default_signoff") or "").strip()
    if default_signoff:
        body = f"{body}\n\n{default_signoff}"

    return body.strip()


def call_ollama_generate(prompt, model=None, temperature=None):
    model = model or OLLAMA_MODEL
    temperature = OLLAMA_TEMPERATURE if temperature is None else temperature
    url = f"{OLLAMA_URL}/api/generate"

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": 220,
        },
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=90) as resp:
        raw = resp.read().decode("utf-8", errors="replace")

    data = json.loads(raw)
    return (data.get("response") or "").strip()


def generate_deepthink_draft(email_obj, account_name=None, model=None, temperature=None):
    """
    Generate a draft email reply using an LLM based on the provided email object and account profile.

    If LLM generation fails or produces invalid output, the function falls back to a template draft
    and logs the error.

    Args:
        email_obj (dict): The email object containing details for the reply.
        account_name (str, optional): The account name to use for the reply profile.
        model (str, optional): The LLM model to use.
        temperature (float, optional): The temperature setting for the LLM.

    Returns:
        str: The generated or fallback draft reply body.
    """
    account_name = account_name or (email_obj.get("account") or "").strip()
    reply_profile = get_account_reply_profile(account_name)

    prompt = build_deepthink_prompt(email_obj, reply_profile)

    try:
        raw = call_ollama_generate(
            prompt=prompt,
            model=model,
            temperature=temperature,
        )
        cleaned = normalize_llm_reply(raw)
        is_valid, reason = validate_llm_reply(cleaned, email_obj, reply_profile)

        if cleaned and is_valid:
            log_event(
    "deepthink_generated",
    account=account_name,
    model=model or OLLAMA_MODEL,
    used_fallback=False,
    word_count=_word_count(cleaned),
    business_name=reply_profile.get("business_name"),
    mailbox_role=reply_profile.get("mailbox_role"),
)
            return cleaned

        raise ValueError(reason or "invalid model output")
    except Exception as e:
        log_event(
            "deepthink_fallback_used",
            account=account_name,
            model=model or OLLAMA_MODEL,
            error=str(e),
        )
        return build_deepthink_fallback_body(email_obj, reply_profile)