"""Small additive SQLite schema upgrades for foundation deployments."""

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def upgrade_schema(engine: Engine) -> None:
    """Add columns introduced after the initial foundation schema, if absent."""
    inspector = inspect(engine)
    if "security_evaluations" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("security_evaluations")}
        additions = {
            "tool_name": "VARCHAR(64)",
            "contract_account": "VARCHAR(128)",
            "review_expires_at": "DATETIME",
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
        }
        with engine.begin() as connection:
            for name, declaration in additions.items():
                if name not in columns:
                    connection.execute(text(f"ALTER TABLE policy_configuration ADD COLUMN {name} {declaration}"))
