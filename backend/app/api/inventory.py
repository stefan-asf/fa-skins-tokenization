import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user
from app.config import settings
from app.models.user import User

router = APIRouter(prefix="/inventory", tags=["inventory"])

SKIN_NAME = "P250 | Sand Dune (Minimal Wear)"
CS2_APP_ID = 730
CS2_CONTEXT_ID = 2


async def _fetch_inventory(steam_id: str) -> dict:
    inv_url = f"https://steamcommunity.com/inventory/{steam_id}/{CS2_APP_ID}/{CS2_CONTEXT_ID}"
    params = {"l": "english", "count": 5000}
    if settings.steam_api_key:
        params["key"] = settings.steam_api_key

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": f"https://steamcommunity.com/profiles/{steam_id}/inventory/",
    }

    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        resp = await client.get(inv_url, params=params, headers=headers)

    if resp.status_code == 403:
        raise HTTPException(status_code=403, detail="Steam inventory is private")
    if resp.status_code != 200 or not resp.text or resp.text == "null":
        raise HTTPException(status_code=502, detail=f"Steam API error: {resp.status_code}")

    data = resp.json()
    if not data or not data.get("assets"):
        return {"assets": [], "descriptions": []}
    return data


@router.get("")
async def get_inventory(user: User = Depends(get_current_user)):
    data = await _fetch_inventory(user.steam_id)
    descriptions = {
        (d["classid"], d["instanceid"]): d
        for d in data.get("descriptions", [])
    }

    items = []
    for asset in data.get("assets", []):
        desc = descriptions.get((asset["classid"], asset["instanceid"]))
        if not desc:
            continue
        if desc.get("market_hash_name") != SKIN_NAME:
            continue
        items.append({
            "asset_id": asset["assetid"],
            "name": desc.get("name", SKIN_NAME),
            "market_hash_name": SKIN_NAME,
            "icon_url": "https://community.cloudflare.steamstatic.com/economy/image/"
                        + desc.get("icon_url", ""),
            "tradable": desc.get("tradable", 0) == 1,
        })

    return {"items": items, "count": len(items)}


@router.get("/debug")
async def debug_inventory(user: User = Depends(get_current_user)):
    data = await _fetch_inventory(user.steam_id)
    descriptions = {
        (d["classid"], d["instanceid"]): d
        for d in data.get("descriptions", [])
    }
    names = []
    for asset in data.get("assets", []):
        desc = descriptions.get((asset["classid"], asset["instanceid"]))
        if desc:
            names.append({
                "asset_id": asset["assetid"],
                "market_hash_name": desc.get("market_hash_name"),
                "tradable": desc.get("tradable"),
            })
    return {"items": names}
