import email
import html
import re
import unicodedata
from email.header import decode_header


def sanitize_for_external_output(text, max_length=None):
    if text is None:
        text = ""

    text = str(text)
    text = text.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    invisible_chars = {
        "\u200b",
        "\u200c",
        "\u200d",
        "\u2060",
        "\ufeff",
        "\u00ad",
        "\u034f",
        "\u180e",
    }
    text = "".join(ch for ch in text if ch not in invisible_chars)

    text = "".join(
        ch for ch in text
        if unicodedata.category(ch) not in {"Cf", "Cc"}
    )

    text = re.sub(r"\s+", " ", text).strip()

    if max_length is not None and max_length > 0 and len(text) > max_length:
        text = text[:max_length].rstrip() + "..."

    return text

def decode_header_value(header_value, max_length=None):
    if not header_value:
        return ""

    decoded_parts = []
    for value, charset in decode_header(header_value):
        if isinstance(value, bytes):
            encodings_to_try = [charset, "utf-8", "latin-1"]
            decoded = None
            for enc in encodings_to_try:
                if not enc:
                    continue
                try:
                    decoded = value.decode(enc, errors="replace")
                    break
                except Exception:
                    continue
            if decoded is None:
                decoded = value.decode("utf-8", errors="replace")
            decoded_parts.append(decoded)
        else:
            decoded_parts.append(str(value))

    combined = "".join(decoded_parts)
    combined = combined.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    combined = re.sub(r"\s+", " ", combined).strip()
    return sanitize_for_external_output(combined, max_length=max_length)


def _decode_payload(part):
    payload = part.get_payload(decode=True)
    if payload is None:
        raw = part.get_payload()
        return raw if isinstance(raw, str) else ""

    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except Exception:
        try:
            return payload.decode("utf-8", errors="replace")
        except Exception:
            return payload.decode("latin-1", errors="replace")


def _html_to_text(html_text):
    if not html_text:
        return ""

    text = re.sub(r"(?is)<style\b.*?>.*?</style>", " ", html_text)
    text = re.sub(r"(?is)<script\b.*?>.*?</script>", " ", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p\s*>", "\n", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return sanitize_for_external_output(text)


def extract_text_body(msg):
    plain_candidates = []
    html_candidates = []

    if msg.is_multipart():
        for part in msg.walk():
            content_disposition = (part.get("Content-Disposition") or "").lower()
            if "attachment" in content_disposition:
                continue

            ctype = part.get_content_type()

            try:
                decoded = _decode_payload(part)
            except Exception:
                continue

            if not decoded:
                continue

            if ctype == "text/plain":
                plain_candidates.append(decoded)
            elif ctype == "text/html":
                html_candidates.append(decoded)
    else:
        ctype = msg.get_content_type()
        try:
            decoded = _decode_payload(msg)
        except Exception:
            decoded = ""

        if decoded:
            if ctype == "text/plain":
                plain_candidates.append(decoded)
            elif ctype == "text/html":
                html_candidates.append(decoded)

    for candidate in plain_candidates:
        cleaned = sanitize_for_external_output(candidate)
        if cleaned:
            return cleaned

    for candidate in html_candidates:
        cleaned = _html_to_text(candidate)
        if cleaned:
            return cleaned

    return ""


def make_snippet(text, max_length=220):
    cleaned = sanitize_for_external_output(text, max_length=max_length)
    return cleaned


def format_email_date(date_str):
    try:
        dt = email.utils.parsedate_to_datetime(date_str)
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ""


def is_important(subject, from_):
    subject_keywords = ["urgent", "invoice", "payment", "action required"]
    from_keywords = ["billing@", "accounts@", "support@", "paypal@"]

    subject_lower = (subject or "").lower()
    from_lower = (from_ or "").lower()

    for kw in subject_keywords:
        if kw in subject_lower:
            return True

    for kw in from_keywords:
        if kw in from_lower:
            return True

    return False
