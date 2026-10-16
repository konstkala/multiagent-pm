from pathlib import Path

from app.core.config import ENV_FILE


def test_env_file_is_backend_env_regardless_of_cwd() -> None:
    assert Path(__file__).resolve().parents[1] / ".env" == ENV_FILE
