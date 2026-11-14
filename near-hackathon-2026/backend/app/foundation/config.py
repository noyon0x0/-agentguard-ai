"""Environment based configuration with safe defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_DATABASE_PATH = Path(__file__).resolve().parents[2] / "near_hackathon_agentguard.sqlite3"
_DEFAULT_DATABASE_URL = f"sqlite:///{_DEFAULT_DATABASE_PATH.as_posix()}"
OFFICIAL_NEAR_TESTNET_RPC_URL = "https://rpc.testnet.fastnear.com"
_NEAR_HACKATHON_AGENTGUARD_TESTNET_ACCOUNT = ""
_NEAR_HACKATHON_AGENTGUARD_TESTNET_PUBLIC_KEY = ""
_NEAR_HACKATHON_AGENTGUARD_TESTNET_AUTHORIZED_RECIPIENT = ""
_NEAR_HACKATHON_AGENTGUARD_TESTNET_UNAUTHORIZED_RECIPIENT = "attacker.testnet"


@dataclass(frozen=True)
class Settings:
    app_name: str = "AgentGuard AI API"
    environment: str = "development"
    database_url: str = _DEFAULT_DATABASE_URL
    log_level: str = "INFO"
    # Administrative routes are disabled until the operator configures a
    # unique token. Never ship a known default bearer credential.
    admin_token: str = ""
    near_testnet_rpc_url: str = OFFICIAL_NEAR_TESTNET_RPC_URL
    near_rpc_timeout_seconds: float = 5.0
    near_sender_account: str = _NEAR_HACKATHON_AGENTGUARD_TESTNET_ACCOUNT
    near_authorized_recipient: str = _NEAR_HACKATHON_AGENTGUARD_TESTNET_AUTHORIZED_RECIPIENT
    near_unauthorized_recipient: str = _NEAR_HACKATHON_AGENTGUARD_TESTNET_UNAUTHORIZED_RECIPIENT
    near_testnet_private_key: str = ""
    near_public_key: str = _NEAR_HACKATHON_AGENTGUARD_TESTNET_PUBLIC_KEY
    near_transactions_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    @classmethod
    def from_environment(cls) -> "Settings":
        return cls(
            app_name=os.getenv("NEAR_HACKATHON_AGENTGUARD_APP_NAME", cls.app_name),
            environment=os.getenv("NEAR_HACKATHON_AGENTGUARD_ENVIRONMENT", cls.environment),
            database_url=os.getenv("NEAR_HACKATHON_AGENTGUARD_DATABASE_URL", _DEFAULT_DATABASE_URL),
            log_level=os.getenv("NEAR_HACKATHON_AGENTGUARD_LOG_LEVEL", cls.log_level).upper(),
            admin_token=os.getenv("NEAR_HACKATHON_AGENTGUARD_ADMIN_TOKEN", ""),
            near_testnet_rpc_url=os.getenv("NEAR_HACKATHON_AGENTGUARD_NEAR_TESTNET_RPC_URL", cls.near_testnet_rpc_url),
            near_rpc_timeout_seconds=float(os.getenv("NEAR_HACKATHON_AGENTGUARD_NEAR_RPC_TIMEOUT_SECONDS", "5")),
            near_sender_account=os.getenv("NEAR_HACKATHON_AGENTGUARD_NEAR_SENDER_ACCOUNT", cls.near_sender_account).strip(),
            near_authorized_recipient=os.getenv("NEAR_HACKATHON_AGENTGUARD_NEAR_AUTHORIZED_RECIPIENT", cls.near_authorized_recipient).strip(),
            near_unauthorized_recipient=os.getenv("NEAR_HACKATHON_AGENTGUARD_NEAR_UNAUTHORIZED_RECIPIENT", cls.near_unauthorized_recipient).strip(),
            near_testnet_private_key=os.getenv("NEAR_HACKATHON_AGENTGUARD_NEAR_TESTNET_PRIVATE_KEY", ""),
            near_public_key=os.getenv("NEAR_HACKATHON_AGENTGUARD_NEAR_PUBLIC_KEY", cls.near_public_key).strip(),
            near_transactions_enabled=os.getenv("NEAR_HACKATHON_AGENTGUARD_NEAR_TRANSACTIONS_ENABLED", "false").casefold() == "true",
            telegram_bot_token=os.getenv("NEAR_HACKATHON_AGENTGUARD_TELEGRAM_BOT_TOKEN", ""),
            telegram_chat_id=os.getenv("NEAR_HACKATHON_AGENTGUARD_TELEGRAM_CHAT_ID", ""),
        )
