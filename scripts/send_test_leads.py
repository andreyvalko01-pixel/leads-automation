"""Надсилає кілька тестових заявок у локальний сервіс — зручно перевірити весь ланцюжок.

    python scripts/send_test_leads.py --url http://127.0.0.1:8000 --token change-me
"""

import argparse

import httpx

LEADS = [
    # Contact Form 7 шле form-data
    ("form", {"your-name": "олена коваль", "your-phone": "067 123 45 67", "your-email": "olena@gmail.com",
              "your-message": "Цікавить монтаж під ключ", "_wpcf7": "Консультація",
              "_wpcf7_container_post_url": "https://site.ua/montazh/?utm_source=google&utm_medium=cpc&utm_campaign=autumn"}),
    # Elementor — JSON з полями всередині fields
    ("json", {"form": {"name": "Розрахунок"}, "form_name": "Розрахунок вартості",
              "fields": {"name": {"value": "Андрій"}, "phone": {"value": "+38 (093) 555-12-34"},
                         "message": {"value": "Будинок 120 м²"}},
              "page_url": "https://site.ua/?utm_source=facebook&utm_medium=paid&utm_campaign=lead_form"}),
    ("form", {"name": "Ірина", "phone": "0501234", "email": "irina@ukr.net", "form_name": "Зворотний дзвінок",
              "page_url": "https://site.ua/kontakty/"}),
    # повторна заявка від тієї ж людини
    ("json", {"name": "Олена", "phone": "+380671234567", "message": "Забула уточнити терміни", "form_name": "Консультація",
              "page_url": "https://site.ua/montazh/"}),
    ("form", {"your-name": "МАКСИМ", "your-phone": "80739998877", "_wpcf7": "Зворотний дзвінок",
              "_wpcf7_container_post_url": "https://site.ua/?utm_source=instagram&utm_campaign=stories"}),
]

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--token", default="change-me")
    args = ap.parse_args()

    endpoint = f"{args.url}/webhook/wordpress?token={args.token}"
    for kind, payload in LEADS:
        resp = httpx.post(endpoint, json=payload) if kind == "json" else httpx.post(endpoint, data=payload)
        print(resp.status_code, resp.json())
