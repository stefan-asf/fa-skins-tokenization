"""
Получение инвентаря пользователя через авторизованную сессию бота.
Бот логинится один раз, сессия кешируется на весь процесс.
"""
import json
import logging
import os
import threading

from steampy.client import SteamClient

from app.config import settings

logger = logging.getLogger(__name__)

_client: SteamClient | None = None
_lock = threading.Lock()


def _get_steam_guard() -> dict:
    """
    Возвращает dict с shared_secret и identity_secret.
    Если задан STEAM_MAFILE_PATH — читает из реального mafile.
    Иначе берёт из STEAM_SHARED_SECRET / STEAM_IDENTITY_SECRET.
    """
    if settings.steam_mafile_path and os.path.exists(settings.steam_mafile_path):
        with open(settings.steam_mafile_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {
            "shared_secret": data["shared_secret"],
            "identity_secret": data["identity_secret"],
        }
    return {
        "shared_secret": settings.steam_shared_secret,
        "identity_secret": settings.steam_identity_secret,
    }


def _get_client() -> SteamClient:
    global _client
    with _lock:
        if _client is not None and _client.is_session_alive():
            return _client
        logger.info("Logging in Steam bot: %s", settings.steam_login)
        client = SteamClient(settings.steam_api_key or "")
        client.login(
            username=settings.steam_login,
            password=settings.steam_password,
            steam_guard=_get_steam_guard(),
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
