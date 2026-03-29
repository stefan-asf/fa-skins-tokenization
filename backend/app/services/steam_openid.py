import re
from urllib.parse import urlencode

import httpx

STEAM_OPENID_URL = "https://steamcommunity.com/openid/login"


def get_login_redirect_url(callback_url: str, realm: str) -> str:
    params = {
        "openid.ns": "http://specs.openid.net/auth/2.0",
        "openid.mode": "checkid_setup",
        "openid.return_to": callback_url,
        "openid.realm": realm,
        "openid.identity": "http://specs.openid.net/auth/2.0/identifier_select",
        "openid.claimed_id": "http://specs.openid.net/auth/2.0/identifier_select",
    }
    return f"{STEAM_OPENID_URL}?{urlencode(params)}"


async def verify_and_get_steam_id(params: dict) -> str | None:
    verify_params = {**params, "openid.mode": "check_authentication"}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(STEAM_OPENID_URL, data=verify_params)
    if "is_valid:true" not in resp.text:
        return None
    claimed_id = params.get("openid.claimed_id", "")
    match = re.search(r"/openid/id/(\d+)$", claimed_id)
    return match.group(1) if match else None
