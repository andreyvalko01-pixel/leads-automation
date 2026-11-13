import html

import httpx

from ..config import settings


def format_message(lead: dict) -> str:
    e = html.escape
    lines = [f"🔔 <b>Нова заявка #{lead['id']}</b>" + (" (повторна)" if lead["duplicate_of"] else "")]
    lines.append(f"👤 {e(lead['name'])}")
    if lead["phone"]:
        lines.append(f"📞 {lead['phone']}")
    elif lead["raw_phone"]:
        lines.append(f"📞 {e(lead['raw_phone'])} ⚠️ номер не розпізнано")
    if lead["email"]:
        lines.append(f"✉️ {e(lead['email'])}")
    if lead["message"]:
        lines.append(f"💬 {e(lead['message'][:500])}")
    lines.append(f"📝 {e(lead['form_name'])}")
    if lead["utm"]:
        lines.append("🏷 " + " / ".join(e(v) for v in lead["utm"].values()))
    return "\n".join(lines)


def send(lead: dict) -> str | None:
    if settings.dry_run:
        return None

    resp = httpx.post(
        f"https://api.telegram.org/bot{settings.telegram_token}/sendMessage",
        json={
            "chat_id": settings.telegram_chat_id,
            "text": format_message(lead),
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return str(resp.json()["result"]["message_id"])
