from sqlalchemy import inspect, text

from app.foundation.database import create_database_engine
from app.foundation.migrations import upgrade_schema


def test_migrations_add_new_simulation_and_policy_columns_to_legacy_sqlite():
    engine = create_database_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE security_evaluations (id INTEGER PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE policy_configuration (id INTEGER PRIMARY KEY)"))

    upgrade_schema(engine)
    inspector = inspect(engine)
    evaluation_columns = {item["name"] for item in inspector.get_columns("security_evaluations")}
    policy_columns = {item["name"] for item in inspector.get_columns("policy_configuration")}

    assert {"tool_name", "contract_account", "review_expires_at"} <= evaluation_columns
    assert {"allowed_tools", "allowed_contracts"} <= policy_columns
    engine.dispose()
