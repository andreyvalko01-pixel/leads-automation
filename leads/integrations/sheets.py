"""Рядок у Google-таблицю через веб-застосунок Apps Script (див. apps-script/Code.gs).

Так не потрібен сервісний акаунт: скрипт працює від імені власника таблиці.
"""

import httpx

from ..config import settings


def send(lead: dict) -> str | None:
    if settings.dry_run:
        return None

    payload = {
        "id": lead["id"],
        "created_at": lead["created_at"],
        "name": lead["name"],
        "phone": lead["phone"] or lead["raw_phone"],
        "email": lead["email"] or "",
        "message": lead["message"],
        "form": lead["form_name"],
        "page": lead["page_url"],
        "duplicate": bool(lead["duplicate_of"]),
        **{k: lead["utm"].get(k, "") for k in ("utm_source", "utm_medium", "utm_campaign")},
    }
    # Apps Script відповідає редиректом на googleusercontent — його треба пройти
    resp = httpx.post(settings.sheets_webhook_url, json=payload, follow_redirects=True, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Apps Script: {data}")
    return str(data.get("row"))
