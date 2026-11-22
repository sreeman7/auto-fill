"""Environment configuration; no credentials are bundled with the extension."""

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


@dataclass(frozen=True)
class Settings:
    supabase_url: str = os.getenv("SUPABASE_URL", "").rstrip("/")
    supabase_publishable_key: str = os.getenv("SUPABASE_PUBLISHABLE_KEY", "")
    supabase_secret_key: str = os.getenv("SUPABASE_SECRET_KEY", "")
    database_url: str = os.getenv("DATABASE_URL", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    tailor_signing_key: str = os.getenv("TAILOR_SIGNING_KEY", "")
    allowed_origins: tuple[str, ...] = tuple(
        origin.strip() for origin in os.getenv("ALLOWED_ORIGINS", "").split(",") if origin.strip()
    )

    def __post_init__(self) -> None:
        if self.supabase_url:
            url = urlparse(self.supabase_url)
            if url.scheme != "https" and not (url.scheme == "http" and url.hostname in {"127.0.0.1", "localhost"}):
                raise ValueError("SUPABASE_URL must use HTTPS except for loopback development")
        if "*" in self.allowed_origins:
            raise ValueError("ALLOWED_ORIGINS must list exact origins")


settings = Settings()
