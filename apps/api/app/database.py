"""PostgreSQL sessions run as the authenticated role with per-request RLS claims."""

from collections.abc import Generator

from fastapi import Depends, HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from .auth import AuthUser, get_current_user
from .config import settings


def make_session_factory(url: str) -> sessionmaker[Session]:
    connect_args = {"connect_timeout": 3} if url.startswith("postgresql") else {}
    engine = create_engine(url, pool_pre_ping=True, connect_args=connect_args)
    return sessionmaker(bind=engine, expire_on_commit=False)


_session_factory: sessionmaker[Session] | None = None


def database_ready() -> bool:
    global _session_factory
    if not settings.database_url:
        return False
    try:
        if _session_factory is None:
            _session_factory = make_session_factory(settings.database_url)
        with _session_factory() as session:
            session.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False


def get_db(user: AuthUser = Depends(get_current_user)) -> Generator[Session, None, None]:
    global _session_factory
    if not settings.database_url:
        raise HTTPException(503, "Database is not configured")
    if _session_factory is None:
        _session_factory = make_session_factory(settings.database_url)
    with _session_factory() as session:
        # The connection role must be allowed to SET ROLE authenticated. These
        # settings are transaction-local and reset automatically on completion.
        session.execute(text("SET LOCAL ROLE authenticated"))
        session.execute(text("SELECT set_config('request.jwt.claim.sub', :user_id, true)"), {"user_id": str(user.id)})
        yield session
