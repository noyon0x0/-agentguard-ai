"""Optional server-side Telegram alerts with sanitized failures and short timeouts."""

from __future__ import annotations

import requests

from .config import Settings


def telegram_configured(settings: Settings) -> bool:
    return bool(settings.telegram_bot_token and settings.telegram_chat_id)


def send_telegram(settings: Settings, event: str, message: str) -> dict:
    if not telegram_configured(settings):
        return {"enabled": False, "delivered": False, "status": "not_configured"}
    token = settings.telegram_bot_token
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": settings.telegram_chat_id, "text": f"AgentGuard {event}: {message}"},
            timeout=3.0,
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict) or data.get("ok") is not True:
            return {"enabled": True, "delivered": False, "status": "delivery_failed"}
        return {"enabled": True, "delivered": True, "status": "delivered"}
    except (requests.RequestException, ValueError):
        return {"enabled": True, "delivered": False, "status": "delivery_failed"}
