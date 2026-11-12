"""SQLAlchemy engine and session setup."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


def create_database_engine(database_url: str) -> Engine:
    if not database_url.startswith("sqlite:"):
        raise ValueError("AgentGuard foundation supports SQLite database URLs only")
    options = {"check_same_thread": False}
    poolclass = StaticPool if database_url in {"sqlite://", "sqlite:///:memory:"} else None
    return create_engine(database_url, connect_args=options, pool_pre_ping=True, poolclass=poolclass)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """Dependency placeholder replaced by the configured app dependency."""
    raise RuntimeError("Database dependency was not configured")
