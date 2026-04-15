"""
Получение инвентаря пользователя через сессию бота.

Если задан STEAM_MAFILE_PATH и mafile содержит Session.steamLoginSecure —
используем куки из mafile напрямую (без логина через username/password).
Это надёжнее, чем логин с VPS-IP, который Steam часто блокирует.
"""
import json
import logging
import os
import tempfile
import threading
import requests
from steampy.client import SteamClient

from app.config import settings

logger = logging.getLogger(__name__)

_session: requests.Session | None = None
_client: SteamClient | None = None
_lock = threading.Lock()
_mafile_path: str | None = None


def _get_mafile_path() -> str:
    """
    Возвращает путь к mafile.
    Если задан STEAM_MAFILE_PATH — использует его напрямую.
    Иначе создаёт временный mafile из env-переменных.
    """
    global _mafile_path

    if settings.steam_mafile_path and os.path.exists(settings.steam_mafile_path):
        return settings.steam_mafile_path

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


def _session_from_mafile(path: str) -> requests.Session | None:
    """
    Создаёт requests.Session с куками из mafile (без логина).
    Возвращает None если в mafile нет данных сессии.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        sess = data.get("Session", {})
        login_secure = sess.get("steamLoginSecure")
        session_id = sess.get("SessionID")
        if not login_secure:
            return None
        # Передаём куки напрямую в заголовке — обходим проблемы domain matching в requests
        cookie_str = f"steamLoginSecure={login_secure}"
        if session_id:
            cookie_str += f"; sessionid={session_id}"
        s = requests.Session()
        s.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Cookie": cookie_str,
            "Referer": "https://steamcommunity.com/",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
        })
        logger.info("Steam session loaded from mafile cookies")
        return s
    except Exception as e:
        logger.warning("Failed to load session from mafile: %s", e)
        return None


def _get_session() -> requests.Session:
    """
    Возвращает аутентифицированную сессию.
    Приоритет: куки из mafile → steampy login.
    """
    global _session, _client
    with _lock:
        # 1. Уже есть живая сессия — используем
        if _session is not None:
            return _session

        # 2. Пробуем загрузить куки из mafile
        mafile_path = settings.steam_mafile_path
        if mafile_path and os.path.exists(mafile_path):
            s = _session_from_mafile(mafile_path)
            if s is not None:
                _session = s
                return _session

        # 3. Fallback: полный логин через steampy
        if _client is None or not _client.is_session_alive():
            logger.info("Logging in Steam bot via username/password: %s", settings.steam_login)
            client = SteamClient(settings.steam_api_key or "")
            client.login(
                username=settings.steam_login,
                password=settings.steam_password,
                steam_guard=_get_mafile_path(),
            )
            _client = client
            logger.info("Steam bot session established via login")

        _session = _client._session
        return _session


def fetch_user_inventory(steam_id: str) -> dict:
    """
    Запрашивает инвентарь CS2 пользователя.
    Использует официальный Steam Web API если задан STEAM_API_KEY,
    иначе fallback на community endpoint через сессию бота.
    Возвращает dict с ключами assets и descriptions.
    """
    if settings.steam_api_key:
        return _fetch_via_webapi(steam_id)
    return _fetch_via_community(steam_id)


def _fetch_via_webapi(steam_id: str) -> dict:
    """Steam Web API — работает с серверных IP без ограничений."""
    from fastapi import HTTPException

    resp = requests.get(
        "https://api.steampowered.com/IEconService/GetInventoryItemsWithDescriptions/v1/",
        params={
            "key": settings.steam_api_key,
            "steamid": steam_id,
            "appid": 730,
            "contextid": 2,
            "count": 5000,
            "get_descriptions": 1,
        },
        timeout=20,
    )
    logger.info("Steam Web API inventory: status=%s", resp.status_code)
    if resp.status_code == 403:
        raise HTTPException(status_code=403, detail="Steam inventory is private")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Steam API returned {resp.status_code}")

    data = resp.json().get("response", {})
    if not data:
        raise HTTPException(status_code=403, detail="Steam inventory is private or empty")
    return data


def _fetch_via_community(steam_id: str) -> dict:
    """Fallback: community endpoint через аутентифицированную сессию бота."""
    from fastapi import HTTPException

    sess = _get_session()
    url = f"https://steamcommunity.com/inventory/{steam_id}/730/2"
    resp = sess.get(
        url,
        params={"l": "english", "count": 5000},
        timeout=20,
    )
    logger.warning("Community inventory: status=%s body=%s", resp.status_code, resp.text[:300])
    if resp.status_code == 403:
        raise HTTPException(status_code=403, detail="Steam inventory is private")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Steam returned {resp.status_code}")

    data = resp.json()
    if not data or not data.get("success"):
        raise HTTPException(status_code=403, detail="Steam inventory is private")
    return data
