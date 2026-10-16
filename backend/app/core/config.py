from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Absolute, so settings load the same whether you run from the repo root or backend/.
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    database_url: str = "postgresql+asyncpg://pm:pm@localhost:5432/pm"
    log_level: str = "INFO"
    anthropic_api_key: SecretStr | None = None

    # Links in emails point at the frontend.
    app_base_url: str = "http://localhost:3000"
    # The API as the browser sees it: the frontend proxies /api to this backend, so cookies
    # stay first-party. Google's redirect URI is built from it.
    public_api_url: str = "http://localhost:3000/api"
    # Google sign-in stays off until both are set (Google Cloud Console → OAuth client).
    google_client_id: str | None = None
    google_client_secret: SecretStr | None = None
    cors_origins: list[str] = ["http://localhost:3000"]
    # Browsers accept Secure cookies on http://localhost, so this stays on in development too.
    cookie_secure: bool = True
    session_ttl_days: int = 14
    # Mailpit locally: a fake inbox at http://localhost:8025.
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_starttls: bool = False
    mail_from: str = "Multiagent PM <no-reply@pm.local>"
    # Must produce EMBEDDING_DIM numbers; changing it means re-embedding every ticket.
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_cache_dir: Path | None = None


settings = Settings()
