"""
Получение инвентаря пользователя.

Основной метод: Node.js микросервис (порт 8081), использующий
steam-inventory-api-ng с retry-логикой и поддержкой проксей.

Fallback-методы (если Node.js сервис недоступен):
1. access_token пользователя
2. Web API key (из .env)
"""
import logging

import requests

from app.config import settings

logger = logging.getLogger(__name__)

_NODE_INVENTORY_URL = "http://127.0.0.1:8081/inventory"
_NODE_TIMEOUT = 20  # seconds


def fetch_user_inventory(
    steam_id: str,
    user_token: str | None = None,
    trade_url: str | None = None,
) -> dict:
    """
    Запрашивает инвентарь CS2 пользователя.
    Возвращает dict с ключами assets и descriptions.
    """
    # Primary: Node.js inventory microservice
    try:
        return _fetch_via_node(steam_id)
    except _NodeServiceUnavailable:
        logger.warning("Node inventory service unavailable, falling back to Python methods")

    # Fallback 1: user access token
    if user_token:
        return _fetch_via_user_token(steam_id, user_token)

    # Fallback 2: Steam Web API key
    if settings.steam_api_key:
        return _fetch_via_webapi(steam_id)

    from fastapi import HTTPException
    raise HTTPException(
        status_code=503,
        detail="Inventory service unavailable. Please try again later.",
    )


class _NodeServiceUnavailable(Exception):
    pass


def _fetch_via_node(steam_id: str) -> dict:
    """Call Node.js inventory microservice on 127.0.0.1:8081."""
    from fastapi import HTTPException

    try:
        resp = requests.get(
            _NODE_INVENTORY_URL,
            params={"steamid": steam_id},
            timeout=_NODE_TIMEOUT,
        )
    except requests.exceptions.ConnectionError:
        raise _NodeServiceUnavailable("Node service connection refused")
    except requests.exceptions.Timeout:
        raise _NodeServiceUnavailable("Node service timeout")

    if resp.status_code == 403:
        raise HTTPException(status_code=403, detail="Steam inventory is private")
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="Steam profile not found")
    if resp.status_code != 200:
        # 502/5xx from Node = Steam API issue, try fallback methods
        data = resp.json() if resp.content else {}
        detail = data.get("error", f"Inventory service returned {resp.status_code}")
        raise _NodeServiceUnavailable(detail)

    return resp.json()


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
    logger.warning("Web API inventory: status=%s body=%s", resp.status_code, resp.text[:300])

    if resp.status_code == 403:
        raise HTTPException(status_code=403, detail="Steam inventory is private")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Steam API returned {resp.status_code}")

    data = resp.json().get("response", {})
    if not data:
        raise HTTPException(status_code=403, detail="Steam inventory is private or empty")
    return data
