"""Зовнішні сервіси, куди потрапляє заявка. Кожна інтеграція — функція send(lead) -> external_id | None."""

from ..config import settings
from . import bitrix24, keycrm, sheets, telegram


def enabled_targets() -> dict:
    targets = {}
    if settings.sheets_webhook_url or settings.dry_run:
        targets["sheets"] = sheets.send
    if settings.crm == "keycrm" and (settings.keycrm_api_key or settings.dry_run):
        targets["keycrm"] = keycrm.send
    if settings.crm == "bitrix24" and (settings.bitrix_webhook_url or settings.dry_run):
        targets["bitrix24"] = bitrix24.send
    if settings.telegram_token or settings.dry_run:
        targets["telegram"] = telegram.send
    return targets
