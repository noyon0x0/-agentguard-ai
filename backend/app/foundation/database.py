"""SQLAlchemy engine and session setup."""

from __future__ import annotations

from collections.abc import Generator

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


def create_database_engine(database_url: str) -> Engine:
    url = make_url(database_url)
    if url.drivername != "sqlite":
        raise ValueError("AgentGuard foundation supports SQLite database URLs only")
    if url.database not in (None, "", ":memory:") and url.query.get("mode") != "memory":
        database_path = Path(url.database).expanduser()
        database_path.parent.mkdir(parents=True, exist_ok=True)
    options = {"check_same_thread": False}
    poolclass = StaticPool if url.database in (None, "", ":memory:") else None
    return create_engine(database_url, connect_args=options, pool_pre_ping=True, poolclass=poolclass)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """Dependency placeholder replaced by the configured app dependency."""
    raise RuntimeError("Database dependency was not configured")
