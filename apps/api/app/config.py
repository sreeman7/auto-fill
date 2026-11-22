"""Environment configuration; no credentials are bundled with the extension."""

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "development")
    supabase_url: str = os.getenv("SUPABASE_URL", "").rstrip("/")
    supabase_publishable_key: str = os.getenv("SUPABASE_PUBLISHABLE_KEY", "")
    supabase_secret_key: str = os.getenv("SUPABASE_SECRET_KEY", "")
    database_url: str = os.getenv("DATABASE_URL", "")
    allowed_origins: tuple[str, ...] = tuple(
        origin.strip() for origin in os.getenv("ALLOWED_ORIGINS", "").split(",") if origin.strip()
    )

    def __post_init__(self) -> None:
        if self.app_env not in {"development", "staging", "production"}:
            raise ValueError("APP_ENV must be development, staging or production")
        if self.supabase_url:
            url = urlparse(self.supabase_url)
            if not url.hostname or url.username or url.password or url.path or url.query or url.fragment or (url.scheme != "https" and not (url.scheme == "http" and url.hostname in {"127.0.0.1", "localhost"})):
                raise ValueError("SUPABASE_URL must use HTTPS except for loopback development")
        if "*" in self.allowed_origins:
            raise ValueError("ALLOWED_ORIGINS must list exact origins")
        if self.app_env in {"staging", "production"}:
            if not self.supabase_url.startswith("https://") or not self.supabase_publishable_key or not self.supabase_secret_key:
                raise ValueError("Hosted environments need HTTPS Supabase and both server-side keys")
            if not self.database_url or parse_qs(urlparse(self.database_url).query).get("sslmode", [""])[0] not in {"require", "verify-ca", "verify-full"}:
                raise ValueError("Hosted DATABASE_URL must require TLS with sslmode")
            if not self.allowed_origins or any(
                (parsed := urlparse(origin)).scheme != "chrome-extension" or not parsed.hostname or
                parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password
                for origin in self.allowed_origins
            ):
                raise ValueError("Hosted ALLOWED_ORIGINS must list exact extension origins")


settings = Settings()
