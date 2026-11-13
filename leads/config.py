from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_path: str = "data/leads.sqlite"
    # секрет у URL вебхука: /webhook/wordpress?token=...
    webhook_token: str = "change-me"
    # логін/пароль для сторінки /admin
    admin_user: str = "admin"
    admin_password: str = "admin"

    # true — інтеграції нічого не надсилають назовні, лише пишуть у журнал (для локальної перевірки)
    dry_run: bool = True

    # Google Sheets через веб-застосунок Apps Script (apps-script/Code.gs)
    sheets_webhook_url: str = ""

    # CRM: "keycrm", "bitrix24" або "" (вимкнено)
    crm: str = "keycrm"
    keycrm_api_key: str = ""
    keycrm_source_id: int = 1
    bitrix_webhook_url: str = ""   # https://xxx.bitrix24.ua/rest/1/abc123/
    bitrix_responsible_id: int = 1

    telegram_token: str = ""
    telegram_chat_id: str = ""

    # щоденний звіт
    report_hour: int = 9
    report_timezone: str = "Europe/Kyiv"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    report_to: str = ""

    # скільки разів пробувати доставити лід у зовнішній сервіс
    max_attempts: int = 5


settings = Settings()
