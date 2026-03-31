"""
Получение инвентаря пользователя через авторизованную сессию бота.
Бот логинится один раз, сессия кешируется на весь процесс.
"""
import json
import logging
import os
import tempfile
import threading

from steampy.client import SteamClient

from app.config import settings

logger = logging.getLogger(__name__)

_client: SteamClient | None = None
_lock = threading.Lock()
_mafile_path: str | None = None


def _get_mafile_path() -> str:
    global _mafile_path
    if _mafile_path and os.path.exists(_mafile_path):
        return _mafile_path
    data = {
        "shared_secret": settings.steam_shared_secret,
        "identity_secret": settings.steam_identity_secret,
        "account_name": settings.steam_login,
        "Session": {
            "SteamID": int(settings.steam_steam_id) if settings.steam_steam_id else 0,
        },
    }
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".mafile", delete=False)
    json.dump(data, tmp)
    tmp.close()
    _mafile_path = tmp.name
    return _mafile_path


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
            steam_guard=_get_mafile_path(),
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
