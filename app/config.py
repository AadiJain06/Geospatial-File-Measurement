"""Application configuration."""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings, overridable via environment variables."""

    model_config = SettingsConfigDict(env_prefix="GEO_", env_file=".env", extra="ignore")

    app_name: str = "Geospatial File Measurement API"
    app_version: str = "1.0.0"

    # Where uploaded files and extracted contents are kept.
    storage_dir: Path = Path("storage")

    # Maximum accepted upload size in bytes (default 50 MB).
    max_upload_bytes: int = 50 * 1024 * 1024

    @property
    def uploads_dir(self) -> Path:
        return self.storage_dir / "uploads"

    def ensure_dirs(self) -> None:
        self.uploads_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
