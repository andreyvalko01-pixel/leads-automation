"""Картка у воронці KeyCRM + задача менеджеру передзвонити.

Документація: https://docs.keycrm.app/ (pipelines/cards, tasks)
"""

from datetime import datetime, timedelta

import httpx

from ..config import settings

API = "https://openapi.keycrm.app/v1"


def _client() -> httpx.Client:
    return httpx.Client(
        base_url=API,
        headers={"Authorization": f"Bearer {settings.keycrm_api_key}", "Accept": "application/json"},
        timeout=20,
    )


def send(lead: dict) -> str | None:
    if settings.dry_run:
        return None

    utm = lead["utm"]
    card = {
        "title": f"{lead['form_name']}: {lead['name']}",
        "source_id": settings.keycrm_source_id,
        "manager_comment": lead["message"],
        "utm_source": utm.get("utm_source"),
        "utm_medium": utm.get("utm_medium"),
        "utm_campaign": utm.get("utm_campaign"),
        "utm_term": utm.get("utm_term"),
        "utm_content": utm.get("utm_content"),
        "contact": {
            "full_name": lead["name"],
            "phone": lead["phone"] or lead["raw_phone"],
            "email": lead["email"],
        },
    }

    with _client() as client:
        resp = client.post("/pipelines/cards", json=card)
        resp.raise_for_status()
        card_id = resp.json()["id"]

        due = (datetime.now() + timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
        client.post("/tasks", json={
            "title": f"Передзвонити: {lead['name']} {lead['phone'] or ''}",
            "description": f"Заявка #{lead['id']} з {lead['page_url'] or 'сайту'}",
            "due_date": due,
        }).raise_for_status()

    return str(card_id)
