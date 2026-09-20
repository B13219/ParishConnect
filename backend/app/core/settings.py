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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="PARISHCONNECT_",
        extra="ignore",
    )


settings = Settings()
