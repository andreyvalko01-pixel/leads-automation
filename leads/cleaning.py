"""Очищення даних із форм: телефон, ім'я, email, UTM-мітки."""

import re
from urllib.parse import parse_qs, urlparse

UTM_KEYS = ("utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term")

# як різні плагіни форм називають однакові поля
FIELD_ALIASES = {
    "name": ("name", "your-name", "fio", "ім'я", "імя", "first_name", "form_fields[name]"),
    "phone": ("phone", "tel", "your-phone", "телефон", "form_fields[phone]"),
    "email": ("email", "your-email", "mail", "form_fields[email]"),
    "message": ("message", "your-message", "comment", "коментар", "form_fields[message]"),
    "page_url": ("page_url", "url", "referer", "_wpcf7_container_post_url", "page"),
    "form_name": ("form_name", "form", "_wpcf7", "form_id"),
}


def pick(data: dict, field: str) -> str:
    for alias in FIELD_ALIASES[field]:
        value = data.get(alias)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def normalize_phone(raw: str) -> str | None:
    """Приводимо до +380XXXXXXXXX. Повертаємо None, якщо це не схоже на український мобільний."""
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("80") and len(digits) == 11:      # 80671234567
        digits = "3" + digits
    elif digits.startswith("0") and len(digits) == 10:     # 0671234567
        digits = "38" + digits
    elif len(digits) == 9:                                 # 671234567
        digits = "380" + digits

    if len(digits) == 12 and digits.startswith("380"):
        return "+" + digits
    return None


def normalize_name(raw: str) -> str:
    name = re.sub(r"\s+", " ", raw or "").strip()
    # "ІВАН петренко" -> "Іван Петренко"
    return " ".join(part[:1].upper() + part[1:].lower() for part in name.split(" ")) if name else ""


def normalize_email(raw: str) -> str | None:
    email = (raw or "").strip().lower()
    return email if re.fullmatch(r"[^@\s]+@[^@\s]+\.[a-z]{2,}", email) else None


def extract_utm(data: dict, page_url: str) -> dict:
    """UTM беремо з окремих полів форми, а якщо їх немає — з адреси сторінки."""
    utm = {key: str(data[key]).strip() for key in UTM_KEYS if data.get(key)}
    if page_url:
        query = parse_qs(urlparse(page_url).query)
        for key in UTM_KEYS:
            if key not in utm and query.get(key):
                utm[key] = query[key][0]
    return utm


def clean_lead(data: dict) -> dict:
    page_url = pick(data, "page_url")
    raw_phone = pick(data, "phone")
    return {
        "name": normalize_name(pick(data, "name")) or "Без імені",
        "phone": normalize_phone(raw_phone),
        "raw_phone": raw_phone,
        "email": normalize_email(pick(data, "email")),
        "message": pick(data, "message")[:2000],
        "form_name": pick(data, "form_name") or "Форма на сайті",
        "page_url": page_url.split("?")[0] if page_url else "",
        "utm": extract_utm(data, page_url),
    }
