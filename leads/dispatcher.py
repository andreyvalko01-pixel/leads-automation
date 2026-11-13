"""Розсилка лідів по інтеграціях з повторами при збоях."""

import logging
from datetime import timedelta

from . import db
from .config import settings
from .integrations import enabled_targets

log = logging.getLogger(__name__)


def retry_delay(attempt: int) -> timedelta:
    # 1, 2, 4, 8... хвилин, але не більше години
    return timedelta(minutes=min(2 ** (attempt - 1), 60))


def process_due(targets: dict | None = None) -> int:
    """Пробує доставити все, що чекає черги. Повертає кількість успішних доставок."""
    targets = targets or enabled_targets()
    done = 0

    with db.connect() as conn:
        for delivery in db.due_deliveries(conn):
            send = targets.get(delivery["target"])
            attempts = delivery["attempts"] + 1

            if not send:
                db.mark_delivery(conn, delivery["id"], "failed", attempts, error="Інтеграцію вимкнено")
                continue

            lead = db.get_lead(conn, delivery["lead_id"])
            try:
                external_id = send(lead)
            except Exception as e:  # будь-яка помилка зовнішнього сервісу = повтор пізніше
                error = f"{type(e).__name__}: {e}"[:500]
                if attempts >= settings.max_attempts:
                    log.error("Лід #%s -> %s: здаюсь після %d спроб (%s)", lead["id"], delivery["target"], attempts, error)
                    db.mark_delivery(conn, delivery["id"], "failed", attempts, error=error)
                else:
                    log.warning("Лід #%s -> %s: спроба %d не вдалась (%s)", lead["id"], delivery["target"], attempts, error)
                    db.mark_delivery(conn, delivery["id"], "pending", attempts, error=error, retry_in=retry_delay(attempts))
                continue

            db.mark_delivery(conn, delivery["id"], "done", attempts, external_id=external_id)
            done += 1
            log.info("Лід #%s -> %s: ок", lead["id"], delivery["target"])

    return done
