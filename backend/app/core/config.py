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
    # Must produce EMBEDDING_DIM numbers; changing it means re-embedding every ticket.
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_cache_dir: Path | None = None


settings = Settings()
