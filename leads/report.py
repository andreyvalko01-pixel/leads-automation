"""Щоденний звіт керівнику на пошту."""

import json
import logging
import smtplib
from collections import Counter
from datetime import date, timedelta
from email.message import EmailMessage

from . import db
from .config import settings

log = logging.getLogger(__name__)


def collect_stats(day: date) -> dict:
    start, end = day.isoformat(), (day + timedelta(days=1)).isoformat()
    with db.connect() as conn:
        leads = conn.execute("SELECT * FROM leads WHERE created_at >= ? AND created_at < ?", (start, end)).fetchall()
        failed = conn.execute(
            "SELECT COUNT(*) FROM deliveries d JOIN leads l ON l.id = d.lead_id "
            "WHERE d.status = 'failed' AND l.created_at >= ? AND l.created_at < ?",
            (start, end),
        ).fetchone()[0]

    unique = [lead for lead in leads if lead["duplicate_of"] is None]
    sources = Counter(json.loads(lead["utm"] or "{}").get("utm_source", "без мітки") for lead in unique)
    forms = Counter(lead["form_name"] for lead in unique)

    return {
        "day": day,
        "total": len(leads),
        "unique": len(unique),
        "duplicates": len(leads) - len(unique),
        "bad_phones": sum(1 for lead in unique if not lead["phone"]),
        "sources": sources.most_common(),
        "forms": forms.most_common(),
        "failed_deliveries": failed,
    }


def render(stats: dict) -> str:
    lines = [
        f"Заявки за {stats['day'].strftime('%d.%m.%Y')}",
        "",
        f"Усього: {stats['total']} (унікальних {stats['unique']}, дублів {stats['duplicates']})",
        f"Без коректного телефону: {stats['bad_phones']}",
        "",
        "Джерела:",
        *[f"  {name}: {count}" for name, count in stats["sources"]],
        "",
        "Форми:",
        *[f"  {name}: {count}" for name, count in stats["forms"]],
    ]
    if stats["failed_deliveries"]:
        lines += ["", f"⚠ Не доставлено в зовнішні сервіси: {stats['failed_deliveries']} (див. /admin)"]
    return "\n".join(lines)


def send_daily_report(day: date | None = None):
    day = day or date.today() - timedelta(days=1)
    text = render(collect_stats(day))

    if settings.dry_run or not settings.smtp_host:
        log.info("Щоденний звіт (не надсилаю, dry run):\n%s", text)
        return text

    msg = EmailMessage()
    msg["Subject"] = f"Заявки за {day.strftime('%d.%m')}"
    msg["From"] = settings.smtp_user
    msg["To"] = settings.report_to
    msg.set_content(text)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(msg)
    log.info("Звіт за %s надіслано на %s", day, settings.report_to)
    return text
