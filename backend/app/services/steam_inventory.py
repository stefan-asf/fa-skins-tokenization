"""
Получение инвентаря пользователя через авторизованную сессию бота.
Бот логинится один раз, сессия кешируется на весь процесс.
"""
import logging
import threading

from steampy.client import SteamClient
from steampy.models import GameOptions

from app.config import settings

logger = logging.getLogger(__name__)

_client: SteamClient | None = None
_lock = threading.Lock()

CS2 = GameOptions.CS


def _get_client() -> SteamClient:
    global _client
    with _lock:
        if _client is not None and _client.is_session_alive():
            return _client
        logger.info("Logging in Steam bot: %s", settings.steam_login)
        client = SteamClient(settings.steam_login)
        client.login(
            username=settings.steam_login,
            password=settings.steam_password,
            steam_guard={
                "shared_secret": settings.steam_shared_secret,
                "identity_secret": settings.steam_identity_secret,
            },
        )
        _client = client
        logger.info("Steam bot session established")
        return _client


def fetch_user_inventory(steam_id: str) -> dict:
    """
    Запрашивает инвентарь CS2 пользователя через сессию бота.
    Возвращает dict с ключами assets и descriptions.
    """
    from fastapi import HTTPException

    client = _get_client()
    url = f"https://steamcommunity.com/inventory/{steam_id}/730/2"
    resp = client._session.get(
        url,
        params={"l": "english", "count": 5000},
        timeout=20,
    )

    if resp.status_code == 403:
        raise HTTPException(status_code=403, detail="Steam inventory is private")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Steam returned {resp.status_code}")

    data = resp.json()
    if not data or not data.get("success"):
        raise HTTPException(status_code=403, detail="Steam inventory is private")
    return data
