import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

from .config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
    id           INTEGER PRIMARY KEY,
    created_at   TEXT NOT NULL,
    name         TEXT NOT NULL,
    phone        TEXT,
    raw_phone    TEXT,
    email        TEXT,
    message      TEXT,
    form_name    TEXT,
    page_url     TEXT,
    utm          TEXT,
    duplicate_of INTEGER REFERENCES leads(id)
);
CREATE INDEX IF NOT EXISTS idx_leads_phone ON leads (phone, created_at);

-- кожна відправка ліда в зовнішній сервіс — окремий рядок; звідси ж беруться повтори
CREATE TABLE IF NOT EXISTS deliveries (
    id            INTEGER PRIMARY KEY,
    lead_id       INTEGER NOT NULL REFERENCES leads(id),
    target        TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'pending',   -- pending / done / failed
    attempts      INTEGER NOT NULL DEFAULT 0,
    last_error    TEXT,
    external_id   TEXT,
    next_retry_at TEXT,
    updated_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_deliveries_status ON deliveries (status, next_retry_at);
"""

DUPLICATE_WINDOW = timedelta(hours=24)


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


@contextmanager
def connect():
    Path(settings.database_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with connect() as conn:
        conn.executescript(SCHEMA)


def find_duplicate(conn, phone: str | None, email: str | None) -> int | None:
    """Та сама людина за останню добу (за телефоном або email) — дубль."""
    since = (datetime.now() - DUPLICATE_WINDOW).isoformat(timespec="seconds")
    row = conn.execute(
        """SELECT id FROM leads
           WHERE created_at >= ? AND duplicate_of IS NULL
             AND ((phone IS NOT NULL AND phone = ?) OR (email IS NOT NULL AND email = ?))
           ORDER BY id LIMIT 1""",
        (since, phone, email),
    ).fetchone()
    return row["id"] if row else None


def insert_lead(conn, lead: dict, duplicate_of: int | None) -> int:
    cur = conn.execute(
        """INSERT INTO leads (created_at, name, phone, raw_phone, email, message, form_name, page_url, utm, duplicate_of)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (now(), lead["name"], lead["phone"], lead["raw_phone"], lead["email"], lead["message"],
         lead["form_name"], lead["page_url"], json.dumps(lead["utm"], ensure_ascii=False), duplicate_of),
    )
    return cur.lastrowid


def get_lead(conn, lead_id: int) -> dict:
    row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    lead = dict(row)
    lead["utm"] = json.loads(lead["utm"] or "{}")
    return lead


def add_delivery(conn, lead_id: int, target: str):
    conn.execute(
        "INSERT INTO deliveries (lead_id, target, updated_at, next_retry_at) VALUES (?, ?, ?, ?)",
        (lead_id, target, now(), now()),
    )


def due_deliveries(conn):
    return conn.execute(
        "SELECT * FROM deliveries WHERE status = 'pending' AND next_retry_at <= ? ORDER BY id",
        (now(),),
    ).fetchall()


def mark_delivery(conn, delivery_id: int, status: str, attempts: int, error: str | None = None,
                  external_id: str | None = None, retry_in: timedelta | None = None):
    next_retry = (datetime.now() + retry_in).isoformat(timespec="seconds") if retry_in else None
    conn.execute(
        """UPDATE deliveries SET status = ?, attempts = ?, last_error = ?, external_id = COALESCE(?, external_id),
           next_retry_at = ?, updated_at = ? WHERE id = ?""",
        (status, attempts, error, external_id, next_retry, now(), delivery_id),
    )
