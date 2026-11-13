import os
import tempfile

os.environ["DATABASE_PATH"] = os.path.join(tempfile.mkdtemp(), "test.sqlite")
os.environ["WEBHOOK_TOKEN"] = "secret"
os.environ["DRY_RUN"] = "true"

import pytest
from fastapi.testclient import TestClient

from leads import db
from leads.cleaning import clean_lead, normalize_name, normalize_phone
from leads.dispatcher import process_due
from leads.main import app


@pytest.fixture(autouse=True)
def fresh_db():
    if os.path.exists(os.environ["DATABASE_PATH"]):
        os.remove(os.environ["DATABASE_PATH"])
    db.init_db()


@pytest.mark.parametrize("raw, expected", [
    ("+38 (067) 123-45-67", "+380671234567"),
    ("067 123 45 67", "+380671234567"),
    ("80671234567", "+380671234567"),
    ("671234567", "+380671234567"),
    ("12345", None),
    ("", None),
])
def test_normalize_phone(raw, expected):
    assert normalize_phone(raw) == expected


def test_normalize_name():
    assert normalize_name("  ІВАН   петренко ") == "Іван Петренко"


def test_contact_form7_payload_and_utm():
    lead = clean_lead({
        "your-name": "олена",
        "your-phone": "0501112233",
        "your-email": " Olena@Mail.COM ",
        "_wpcf7_container_post_url": "https://site.ua/poslugy/?utm_source=google&utm_campaign=autumn",
    })
    assert lead["name"] == "Олена"
    assert lead["phone"] == "+380501112233"
    assert lead["email"] == "olena@mail.com"
    assert lead["page_url"] == "https://site.ua/poslugy/"
    assert lead["utm"] == {"utm_source": "google", "utm_campaign": "autumn"}


def test_webhook_rejects_bad_token():
    with TestClient(app) as client:
        assert client.post("/webhook/wordpress?token=nope", json={"phone": "0671234567"}).status_code == 403


def test_webhook_creates_lead_and_deliveries():
    with TestClient(app) as client:
        resp = client.post("/webhook/wordpress?token=secret", data={"name": "Іван", "phone": "0671234567"})
        assert resp.status_code == 200
        lead_id = resp.json()["lead_id"]

    with db.connect() as conn:
        rows = conn.execute("SELECT target, status FROM deliveries WHERE lead_id = ?", (lead_id,)).fetchall()
    assert {r["target"] for r in rows} == {"sheets", "keycrm", "telegram"}
    assert all(r["status"] == "done" for r in rows)


def test_duplicate_skips_crm():
    with TestClient(app) as client:
        first = client.post("/webhook/wordpress?token=secret", json={"name": "Іван", "phone": "0671234567"}).json()
        second = client.post("/webhook/wordpress?token=secret", json={"name": "Іван", "phone": "+380671234567"}).json()

    assert second["duplicate_of"] == first["lead_id"]
    with db.connect() as conn:
        targets = {r["target"] for r in conn.execute("SELECT target FROM deliveries WHERE lead_id = ?", (second["lead_id"],))}
    assert "keycrm" not in targets


def test_elementor_json_payload():
    payload = {"form": {"name": "Консультація"}, "fields": {"name": {"value": "Марія"}, "phone": {"value": "0931234567"}}}
    with TestClient(app) as client:
        resp = client.post("/webhook/wordpress?token=secret", json=payload)
    assert resp.status_code == 200


def test_retry_after_failure():
    calls = {"n": 0}

    def flaky(lead):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ConnectionError("CRM недоступна")
        return "42"

    with db.connect() as conn:
        lead_id = db.insert_lead(conn, clean_lead({"name": "Тест", "phone": "0671234567"}), None)
        db.add_delivery(conn, lead_id, "keycrm")

    assert process_due({"keycrm": flaky}) == 0
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM deliveries").fetchone()
        assert row["status"] == "pending" and row["attempts"] == 1
        # робимо вигляд, що час повтору настав
        conn.execute("UPDATE deliveries SET next_retry_at = '2000-01-01'")

    assert process_due({"keycrm": flaky}) == 1
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM deliveries").fetchone()
    assert row["status"] == "done" and row["external_id"] == "42"
