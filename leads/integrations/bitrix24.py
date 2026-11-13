"""Лід і задача в Bitrix24 через вхідний вебхук (crm.lead.add, tasks.task.add)."""

from datetime import datetime, timedelta

import httpx

from ..config import settings


def _call(method: str, params: dict) -> dict:
    url = settings.bitrix_webhook_url.rstrip("/") + f"/{method}.json"
    resp = httpx.post(url, json=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"Bitrix24 {method}: {data.get('error_description') or data['error']}")
    return data


def send(lead: dict) -> str | None:
    if settings.dry_run:
        return None

    utm = lead["utm"]
    fields = {
        "TITLE": f"{lead['form_name']}: {lead['name']}",
        "NAME": lead["name"],
        "COMMENTS": lead["message"],
        "SOURCE_ID": "WEB",
        "SOURCE_DESCRIPTION": lead["page_url"],
        "ASSIGNED_BY_ID": settings.bitrix_responsible_id,
        "UTM_SOURCE": utm.get("utm_source"),
        "UTM_MEDIUM": utm.get("utm_medium"),
        "UTM_CAMPAIGN": utm.get("utm_campaign"),
        "UTM_CONTENT": utm.get("utm_content"),
        "UTM_TERM": utm.get("utm_term"),
    }
    if lead["phone"] or lead["raw_phone"]:
        fields["PHONE"] = [{"VALUE": lead["phone"] or lead["raw_phone"], "VALUE_TYPE": "WORK"}]
    if lead["email"]:
        fields["EMAIL"] = [{"VALUE": lead["email"], "VALUE_TYPE": "WORK"}]

    lead_id = _call("crm.lead.add", {"fields": fields, "params": {"REGISTER_SONET_EVENT": "Y"}})["result"]

    deadline = (datetime.now() + timedelta(minutes=15)).isoformat(timespec="seconds")
    _call("tasks.task.add", {"fields": {
        "TITLE": f"Передзвонити: {lead['name']}",
        "RESPONSIBLE_ID": settings.bitrix_responsible_id,
        "DEADLINE": deadline,
        "UF_CRM_TASK": [f"L_{lead_id}"],
    }})
    return str(lead_id)
