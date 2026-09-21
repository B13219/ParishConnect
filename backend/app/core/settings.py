from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Vinyrd API"
    app_version: str = "1.0.0"
    api_prefix: str = "/api/v1"
    environment: str = "local"
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"
    public_base_url: str = ""
    database_url: str = (
        "postgresql+psycopg://parishconnect:parishconnect@localhost:5432/parishconnect"
    )
    qr_token_secret: str = "local-demo-qr-secret-change-before-production"
    auth_token_secret: str = "local-demo-auth-secret-change-before-production"
    password_salt: str = "local-demo-password-salt-change-before-production"
    access_token_minutes: int = 720
    demo_password: str = "parishconnect"

    bootstrap_admin_name: str = ""
    bootstrap_admin_email: str = ""
    bootstrap_admin_password: str = ""
    bootstrap_branch_name: str = "Vinyrd Pilot Church"
    bootstrap_branch_location: str = ""

    sms_provider: str = "africas_talking"
    sms_mode: str = "simulate"
    sms_username: str = ""
    sms_api_key: str = ""
    sms_sender_id: str = "VINYRD"
    sms_live_username: str = ""
    sms_live_api_key: str = ""
    sms_live_sender_id: str = "VINYRD"
    sms_live_sender_id_approved: bool = False
    sms_default_country_code: str = "255"
    sms_callback_token: str = ""
    sms_request_timeout_seconds: int = 15

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="PARISHCONNECT_",
        extra="ignore",
    )


settings = Settings()
