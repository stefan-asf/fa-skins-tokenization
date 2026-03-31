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
    url = f"https://steamcommunity.com/profiles/{steam_id}/inventory/json/{CS2_APP_ID}/{CS2_CONTEXT_ID}/"
    params = {"l": "english"}
    if settings.steam_api_key:
        params["key"] = settings.steam_api_key

    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        resp = await client.get(url, params=params)

    if resp.status_code == 403:
        raise HTTPException(status_code=403, detail="Steam inventory is private")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Steam returned {resp.status_code}")

    data = resp.json()
    if not data or not data.get("success"):
        raise HTTPException(status_code=403, detail="Steam inventory is private")
    return data


@router.get("")
async def get_inventory(user: User = Depends(get_current_user)):
    data = await _fetch_inventory(user.steam_id)

    rg_inv = data.get("rgInventory", {})
    rg_desc = data.get("rgDescriptions", {})

    items = []
    for asset in rg_inv.values():
        key = f"{asset['classid']}_{asset['instanceid']}"
        desc = rg_desc.get(key, {})
        if desc.get("market_hash_name") != SKIN_NAME:
            continue
        items.append({
            "asset_id": asset["id"],
            "name": desc.get("name", SKIN_NAME),
            "market_hash_name": SKIN_NAME,
            "icon_url": "https://community.akamai.steamstatic.com/economy/image/" + desc["icon_url"]
                        if desc.get("icon_url") else None,
            "tradable": desc.get("tradable", 0) == 1,
        })

    return {"items": items, "count": len(items)}
