import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/inventory", tags=["inventory"])

SKIN_NAME = "P250 | Sand Dune (Minimal Wear)"
CS2_APP_ID = 730
CS2_CONTEXT_ID = 2


@router.get("")
async def get_inventory(user: User = Depends(get_current_user)):
    url = f"https://steamcommunity.com/inventory/{user.steam_id}/{CS2_APP_ID}/{CS2_CONTEXT_ID}"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, params={"l": "english", "count": 5000})

    if resp.status_code == 403:
        raise HTTPException(status_code=403, detail="Steam inventory is private")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Steam API unavailable")

    data = resp.json()
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
    url = f"https://steamcommunity.com/inventory/{user.steam_id}/{CS2_APP_ID}/{CS2_CONTEXT_ID}"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, params={"l": "english", "count": 5000})
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Steam returned {resp.status_code}")
    data = resp.json()
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
