"""
Получение инвентаря пользователя.

Приоритет методов:
1. partnerinventory (бот-сессия + trade URL пользователя) — основной
2. access_token пользователя — если сохранён
3. Web API key — если задан в .env
4. Community endpoint (fallback, VPS IP скорее всего заблокирован)
"""
import json
import logging
import os
import tempfile
import threading
from urllib.parse import urlparse, parse_qs

import requests
from steampy.client import SteamClient

from app.config import settings

logger = logging.getLogger(__name__)

_session: requests.Session | None = None
_client: SteamClient | None = None
_lock = threading.Lock()
_mafile_path: str | None = None

STEAM_ID_BASE = 76561197960265728


def _get_mafile_path() -> str:
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
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        sess_data = data.get("Session", {})
        login_secure = sess_data.get("steamLoginSecure")
        session_id = sess_data.get("SessionID")
        if not login_secure:
            return None
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
    global _session, _client
    with _lock:
        if _session is not None:
            return _session

        mafile_path = settings.steam_mafile_path
        if mafile_path and os.path.exists(mafile_path):
            s = _session_from_mafile(mafile_path)
            if s is not None:
                _session = s
                return _session

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


def _get_bot_session_id() -> str | None:
    """Extract sessionid from bot's requests.Session."""
    sess = _get_session()
    # Try cookie jar
    for cookie in sess.cookies:
        if cookie.name == "sessionid":
            return cookie.value
    # Try Cookie header (set directly in _session_from_mafile)
    cookie_header = sess.headers.get("Cookie", "")
    for part in cookie_header.split(";"):
        part = part.strip()
        if part.startswith("sessionid="):
            return part[len("sessionid="):]
    return None


def _normalize_partner_inventory(data: dict) -> dict:
    """Convert partnerinventory response to standard assets/descriptions format."""
    assets = []
    for asset_id, asset in data.get("rgInventory", {}).items():
        assets.append({
            "assetid": asset.get("id", asset_id),
            "classid": asset.get("classid", ""),
            "instanceid": asset.get("instanceid", "0"),
            "amount": asset.get("amount", "1"),
            "appid": 730,
            "contextid": "2",
        })

    descriptions = list(data.get("rgDescriptions", {}).values())

    return {
        "assets": assets,
        "descriptions": descriptions,
        "success": 1,
    }


def fetch_user_inventory(
    steam_id: str,
    user_token: str | None = None,
    trade_url: str | None = None,
) -> dict:
    """
    Запрашивает инвентарь CS2 пользователя.
    Возвращает dict с ключами assets и descriptions.
    """
    if trade_url:
        return _fetch_via_partner_inventory(steam_id, trade_url)
    if user_token:
        return _fetch_via_user_token(steam_id, user_token)
    if settings.steam_api_key:
        return _fetch_via_webapi(steam_id)
    return _fetch_via_community(steam_id)


def _fetch_via_partner_inventory(steam_id: str, trade_url: str) -> dict:
    """
    Использует Steam trade window AJAX endpoint через бот-сессию.
    URL: steamcommunity.com/tradeoffer/new/partnerinventory/
    Бот должен иметь валидную сессию (steamLoginSecure + sessionid).
    """
    from fastapi import HTTPException

    # Parse trade URL
    parsed = urlparse(trade_url)
    params = parse_qs(parsed.query)
    partner = params.get("partner", [None])[0]
    token = params.get("token", [None])[0]

    if not partner:
        raise HTTPException(status_code=400, detail="Invalid trade URL: missing partner")

    # Verify partner matches logged-in user
    try:
        account_id = int(steam_id) - STEAM_ID_BASE
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid steam_id")

    if str(account_id) != partner:
        raise HTTPException(
            status_code=400,
            detail=f"Trade URL partner ({partner}) does not match your account ({account_id})",
        )

    session_id = _get_bot_session_id()
    if not session_id:
        logger.warning("Bot session has no sessionid — falling back to community endpoint")
        return _fetch_via_community(steam_id)

    sess = _get_session()
    referer = f"https://steamcommunity.com/tradeoffer/new/?partner={partner}"
    if token:
        referer += f"&token={token}"

    proxies = {"https": settings.steam_proxy, "http": settings.steam_proxy} if settings.steam_proxy else None

    resp = sess.get(
        "https://steamcommunity.com/tradeoffer/new/partnerinventory/",
        params={
            "sessionid": session_id,
            "partner": partner,
            "appid": 730,
            "contextid": 2,
            "l": "english",
        },
        headers={
            "Referer": referer,
            "X-Prototype-Version": "1.7",
            "X-Requested-With": "XMLHttpRequest",
        },
        proxies=proxies,
        timeout=20,
    )

    logger.info("partnerinventory: status=%s body=%s", resp.status_code, resp.text[:300])

    if resp.status_code == 403:
        raise HTTPException(status_code=403, detail="Steam inventory is private")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Steam returned {resp.status_code}")

    data = resp.json()
    if not data or not data.get("success"):
        raise HTTPException(status_code=403, detail="Steam inventory is private or empty")

    return _normalize_partner_inventory(data)


def _fetch_via_user_token(steam_id: str, access_token: str) -> dict:
    from fastapi import HTTPException

    resp = requests.get(
        "https://api.steampowered.com/IEconService/GetInventoryItemsWithDescriptions/v1/",
        params={
            "access_token": access_token,
            "steamid": steam_id,
            "appid": 730,
            "contextid": 2,
            "count": 5000,
            "get_descriptions": 1,
            "language": "english",
        },
        timeout=20,
    )
    logger.info("User-token inventory: status=%s body=%s", resp.status_code, resp.text[:200])
    if resp.status_code == 403:
        raise HTTPException(status_code=403, detail="Steam inventory is private")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Steam API returned {resp.status_code}")

    data = resp.json().get("response", {})
    if not data:
        raise HTTPException(status_code=403, detail="Steam inventory is private or empty")
    return data


def _fetch_via_webapi(steam_id: str) -> dict:
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
    logger.warning("Steam Web API inventory: status=%s body=%s", resp.status_code, resp.text[:300])
    if resp.status_code == 403:
        raise HTTPException(status_code=403, detail="Steam inventory is private")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Steam API returned {resp.status_code}")

    data = resp.json().get("response", {})
    if not data:
        raise HTTPException(status_code=403, detail="Steam inventory is private or empty")
    return data


def _fetch_via_community(steam_id: str) -> dict:
    from fastapi import HTTPException

    sess = _get_session()
    url = f"https://steamcommunity.com/inventory/{steam_id}/730/2"
    proxies = {"https": settings.steam_proxy, "http": settings.steam_proxy} if settings.steam_proxy else None
    resp = sess.get(
        url,
        params={"l": "english", "count": 5000},
        proxies=proxies,
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
