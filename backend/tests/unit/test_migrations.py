from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url

from app.foundation.config import Settings
from app.foundation.database import create_database_engine
from app.foundation.migrations import upgrade_schema


def test_default_database_path_is_project_relative_not_working_directory(monkeypatch):
    monkeypatch.delenv("NEAR_HACKATHON_AGENTGUARD_DATABASE_URL", raising=False)

    configured_path = Path(make_url(Settings.from_environment().database_url).database)
    expected_path = Path(__file__).resolve().parents[2] / "near_hackathon_agentguard.sqlite3"

    assert configured_path.resolve() == expected_path.resolve()


def test_file_database_initialization_creates_missing_parent_directories():
    repository_root = Path(__file__).resolve().parents[3]
    with TemporaryDirectory(prefix="agentguard-db-init-", dir=repository_root) as temporary_directory:
        database_path = Path(temporary_directory) / "nested" / "storage" / "agentguard.sqlite3"
        engine = create_database_engine(f"sqlite:///{database_path.as_posix()}")
        try:
            with engine.connect() as connection:
                assert connection.execute(text("SELECT 1")).scalar_one() == 1
        finally:
            engine.dispose()
        assert database_path.is_file()


def test_non_sqlite_database_url_is_rejected():
    with pytest.raises(ValueError, match="SQLite database URLs only"):
        create_database_engine("postgresql://localhost/agentguard")


def test_migrations_add_new_simulation_and_policy_columns_to_legacy_sqlite():
    engine = create_database_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE security_evaluations (id INTEGER PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE policy_configuration (id INTEGER PRIMARY KEY)"))

    upgrade_schema(engine)
    inspector = inspect(engine)
    evaluation_columns = {item["name"] for item in inspector.get_columns("security_evaluations")}
    policy_columns = {item["name"] for item in inspector.get_columns("policy_configuration")}

    assert {"tool_name", "contract_account", "review_expires_at", "network", "policy_version"} <= evaluation_columns
    assert {"allowed_tools", "allowed_contracts", "policy_version", "global_kill_switch"} <= policy_columns
    engine.dispose()
