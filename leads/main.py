import asyncio
import json
import logging
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates

from . import db
from .cleaning import clean_lead
from .config import settings
from .dispatcher import process_due
from .integrations import enabled_targets
from .report import send_daily_report

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("leads")

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
security = HTTPBasic()


async def retry_loop():
    """Кожні 30 секунд пробуємо доставити все, що зависло через збої."""
    while True:
        try:
            await asyncio.to_thread(process_due)
        except Exception:
            log.exception("Помилка в циклі повторів")
        await asyncio.sleep(30)


async def daily_report_loop():
    tz = ZoneInfo(settings.report_timezone)
    while True:
        now = datetime.now(tz)
        next_run = now.replace(hour=settings.report_hour, minute=0, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)
        await asyncio.sleep((next_run - now).total_seconds())
        try:
            await asyncio.to_thread(send_daily_report)
        except Exception:
            log.exception("Не вдалося надіслати щоденний звіт")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    tasks = [asyncio.create_task(retry_loop()), asyncio.create_task(daily_report_loop())]
    yield
    for task in tasks:
        task.cancel()


app = FastAPI(title="Обробка заявок", lifespan=lifespan)


async def read_payload(request: Request) -> dict:
    """WordPress-плагіни шлють хто JSON, хто form-data — приймаємо обидва."""
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        data = await request.json()
        # Elementor кладе поля у {"fields": {"name": {"value": ...}}}
        if isinstance(data.get("fields"), dict):
            data = {k: (v.get("value") if isinstance(v, dict) else v) for k, v in data["fields"].items()} | data
        return data
    form = await request.form()
    return dict(form)


@app.post("/webhook/wordpress")
async def wordpress_webhook(request: Request, token: str = Query(...)):
    if not secrets.compare_digest(token, settings.webhook_token):
        raise HTTPException(403, "Bad token")

    lead = clean_lead(await read_payload(request))
    if not lead["phone"] and not lead["email"]:
        # без контактів заявка нікому не потрібна, але все одно пишемо в лог
        log.warning("Заявка без контактів: %s", lead)
        raise HTTPException(422, "Потрібен телефон або email")

    with db.connect() as conn:
        duplicate_of = db.find_duplicate(conn, lead["phone"], lead["email"])
        lead_id = db.insert_lead(conn, lead, duplicate_of)

        targets = enabled_targets()
        for target in targets:
            # дубль у CRM не створюємо, але в таблицю і в Telegram він потрапляє з позначкою
            if duplicate_of and target in ("keycrm", "bitrix24"):
                continue
            db.add_delivery(conn, lead_id, target)

    # перша спроба одразу, не чекаючи циклу повторів — менеджер побачить заявку за секунди
    await asyncio.to_thread(process_due)
    return {"ok": True, "lead_id": lead_id, "duplicate_of": duplicate_of}


def check_admin(credentials: HTTPBasicCredentials = Depends(security)):
    ok_user = secrets.compare_digest(credentials.username, settings.admin_user)
    ok_pass = secrets.compare_digest(credentials.password, settings.admin_password)
    if not (ok_user and ok_pass):
        raise HTTPException(401, headers={"WWW-Authenticate": "Basic"})


@app.get("/admin", dependencies=[Depends(check_admin)])
def admin(request: Request):
    with db.connect() as conn:
        leads = [dict(r) for r in conn.execute("SELECT * FROM leads ORDER BY id DESC LIMIT 50")]
        deliveries = conn.execute("SELECT * FROM deliveries WHERE lead_id >= ? ORDER BY id",
                                  (leads[-1]["id"] if leads else 0,)).fetchall()
        today = datetime.now().date().isoformat()
        stats = conn.execute(
            """SELECT COUNT(*) AS total,
                      SUM(duplicate_of IS NOT NULL) AS dups,
                      SUM(phone IS NULL) AS bad_phones
               FROM leads WHERE created_at >= ?""",
            (today,),
        ).fetchone()
        failed = conn.execute("SELECT COUNT(*) FROM deliveries WHERE status = 'failed'").fetchone()[0]
        pending = conn.execute("SELECT COUNT(*) FROM deliveries WHERE status = 'pending'").fetchone()[0]

    by_lead: dict[int, list] = {}
    for d in deliveries:
        by_lead.setdefault(d["lead_id"], []).append(dict(d))
    for lead in leads:
        lead["utm"] = json.loads(lead["utm"] or "{}")
        lead["deliveries"] = by_lead.get(lead["id"], [])

    return templates.TemplateResponse(request, "admin.html", {
        "leads": leads,
        "stats": stats,
        "failed": failed,
        "pending": pending,
        "targets": list(enabled_targets()),
        "dry_run": settings.dry_run,
    })


@app.post("/admin/retry/{delivery_id}", dependencies=[Depends(check_admin)])
def retry_now(delivery_id: int):
    with db.connect() as conn:
        conn.execute(
            "UPDATE deliveries SET status = 'pending', next_retry_at = ? WHERE id = ?",
            (db.now(), delivery_id),
        )
    process_due()
    return {"ok": True}


@app.get("/health")
def health():
    return {"status": "ok"}
