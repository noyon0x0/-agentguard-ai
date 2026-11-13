"""Environment based configuration with safe defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass

_LOCAL_DEMO_ADMIN_TOKEN = "agentguard-local-demo-token"


@dataclass(frozen=True)
class Settings:
    app_name: str = "AgentGuard AI API"
    environment: str = "development"
    database_url: str = "sqlite:///./agentguard_foundation.db"
    log_level: str = "INFO"
    admin_token: str = _LOCAL_DEMO_ADMIN_TOKEN
    near_testnet_rpc_url: str = "https://rpc.testnet.near.org"
    near_rpc_timeout_seconds: float = 5.0
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    @classmethod
    def from_environment(cls) -> "Settings":
        return cls(
            app_name=os.getenv("AGENTGUARD_APP_NAME", cls.app_name),
            environment=os.getenv("AGENTGUARD_ENVIRONMENT", cls.environment),
            database_url=os.getenv("AGENTGUARD_DATABASE_URL", cls.database_url),
            log_level=os.getenv("AGENTGUARD_LOG_LEVEL", cls.log_level).upper(),
            # Keep operator-only read endpoints available in a fresh local demo.
            # Deployments should always supply their own secret via the environment.
            admin_token=os.getenv("AGENTGUARD_ADMIN_TOKEN", cls.admin_token),
            near_testnet_rpc_url=os.getenv("AGENTGUARD_NEAR_TESTNET_RPC_URL", cls.near_testnet_rpc_url),
            near_rpc_timeout_seconds=float(os.getenv("AGENTGUARD_NEAR_RPC_TIMEOUT_SECONDS", "5")),
            telegram_bot_token=os.getenv("AGENTGUARD_TELEGRAM_BOT_TOKEN", ""),
            telegram_chat_id=os.getenv("AGENTGUARD_TELEGRAM_CHAT_ID", ""),
        )
