from pathlib import Path

from app.foundation.config import Settings


def test_hackathon_defaults_are_testnet_only_and_do_not_reuse_parent_wallet():
    settings = Settings()
    project_root = Path(__file__).resolve().parents[3]

    assert settings.near_testnet_rpc_url == "https://rpc.testnet.fastnear.com"
    assert settings.near_sender_account == ""
    assert settings.near_public_key == ""
    assert settings.near_testnet_private_key == ""
    assert settings.near_transactions_enabled is False
    assert Path(settings.database_url.removeprefix("sqlite:///")) == (
        project_root / "backend" / "near_hackathon_agentguard.sqlite3"
    )


def test_parent_project_environment_is_not_inherited(monkeypatch):
    monkeypatch.delenv("NEAR_HACKATHON_AGENTGUARD_ADMIN_TOKEN", raising=False)
    monkeypatch.delenv("NEAR_HACKATHON_AGENTGUARD_NEAR_TESTNET_PRIVATE_KEY", raising=False)
    monkeypatch.setenv("AGENTGUARD_ADMIN_TOKEN", "parent-project-test-value")
    monkeypatch.setenv("AGENTGUARD_NEAR_TESTNET_PRIVATE_KEY", "parent-project-test-value")

    settings = Settings.from_environment()

    assert settings.admin_token == ""
    assert settings.near_testnet_private_key == ""
