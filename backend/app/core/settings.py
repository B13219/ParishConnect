from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ParishConnect API"
    app_version: str = "0.1.0"
    api_prefix: str = "/api/v1"
    environment: str = "local"
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"
    database_url: str = "postgresql+psycopg://parishconnect:parishconnect@localhost:5432/parishconnect"
    qr_token_secret: str = "local-demo-qr-secret-change-before-production"
    auth_token_secret: str = "local-demo-auth-secret-change-before-production"
    password_salt: str = "local-demo-password-salt-change-before-production"
    access_token_minutes: int = 720
    demo_password: str = "parishconnect"

    model_config = SettingsConfigDict(env_file=".env", env_prefix="PARISHCONNECT_")


settings = Settings()
