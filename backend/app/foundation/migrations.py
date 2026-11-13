"""Small additive SQLite schema upgrades for foundation deployments."""

import json
from datetime import datetime, timezone
from types import SimpleNamespace

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from .audit_chain import GENESIS_HASH, calculate_event_hash


def upgrade_schema(engine: Engine) -> None:
    """Add columns introduced after the initial foundation schema, if absent."""
    inspector = inspect(engine)
    if "security_evaluations" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("security_evaluations")}
        additions = {
            "tool_name": "VARCHAR(64)",
            "contract_account": "VARCHAR(128)",
            "review_expires_at": "DATETIME",
            "network": "VARCHAR(16) NOT NULL DEFAULT 'testnet'",
            "policy_version": "INTEGER NOT NULL DEFAULT 1",
        }
        with engine.begin() as connection:
            for name, declaration in additions.items():
                if name not in columns:
                    connection.execute(text(f"ALTER TABLE security_evaluations ADD COLUMN {name} {declaration}"))

    if "policy_configuration" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("policy_configuration")}
        additions = {
            "allowed_tools": "JSON NOT NULL DEFAULT '[\"view_account\",\"view_contract\",\"evaluate_policy\"]'",
            "allowed_contracts": "JSON NOT NULL DEFAULT '[]'",
            "policy_version": "INTEGER NOT NULL DEFAULT 1",
            "global_kill_switch": "BOOLEAN NOT NULL DEFAULT 0",
        }
        with engine.begin() as connection:
            for name, declaration in additions.items():
                if name not in columns:
                    connection.execute(text(f"ALTER TABLE policy_configuration ADD COLUMN {name} {declaration}"))

    if "audit_events" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("audit_events")}
        additions = {
            "agent_id": "VARCHAR(64)",
            "policy_version": "INTEGER NOT NULL DEFAULT 1",
            "previous_hash": "VARCHAR(64)",
            "event_hash": "VARCHAR(64)",
        }
        with engine.begin() as connection:
            for name, declaration in additions.items():
                if name not in columns:
                    connection.execute(text(f"ALTER TABLE audit_events ADD COLUMN {name} {declaration}"))
            rows = connection.execute(
                text("SELECT id, request_id, event_type, decision, agent_id, policy_version, details, created_at, previous_hash, event_hash FROM audit_events ORDER BY id")
            ).mappings().all()
            if any(row["previous_hash"] is None or row["event_hash"] is None for row in rows):
                previous_hash = GENESIS_HASH
                for row in rows:
                    created_at = row["created_at"]
                    if isinstance(created_at, str):
                        created_at = datetime.fromisoformat(created_at)
                    if created_at.tzinfo is None:
                        created_at = created_at.replace(tzinfo=timezone.utc)
                    details = row["details"]
                    if isinstance(details, str):
                        details = json.loads(details)
                    event = SimpleNamespace(
                        request_id=row["request_id"], event_type=row["event_type"],
                        decision=row["decision"], agent_id=row["agent_id"],
                        policy_version=row["policy_version"] or 1, details=details,
                        created_at=created_at,
                    )
                    event_hash = calculate_event_hash(previous_hash, event)
                    connection.execute(
                        text("UPDATE audit_events SET previous_hash=:previous_hash, event_hash=:event_hash WHERE id=:id"),
                        {"previous_hash": previous_hash, "event_hash": event_hash, "id": row["id"]},
                    )
                    previous_hash = event_hash
