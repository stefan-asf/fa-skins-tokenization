import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/inventory", tags=["inventory"])

SKIN_NAME = "P250 | Sand Dune (Minimal Wear)"
CS2_APP_ID = 730
CS2_CONTEXT_ID = 2

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}


@router.get("")
async def get_inventory(user: User = Depends(get_current_user)):
    url = f"https://steamcommunity.com/inventory/{user.steam_id}/{CS2_APP_ID}/{CS2_CONTEXT_ID}"
    headers = {
        **_HEADERS,
        "Referer": f"https://steamcommunity.com/profiles/{user.steam_id}/inventory/",
    }
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        resp = await client.get(url, params={"l": "english", "count": 5000}, headers=headers)

    if resp.status_code == 403:
        raise HTTPException(status_code=403, detail="Steam inventory is private")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Steam returned {resp.status_code}")

    data = resp.json()
    if not data or not data.get("success"):
        raise HTTPException(status_code=403, detail="Steam inventory is private")

    desc_map = {
        (d["classid"], d["instanceid"]): d
        for d in data.get("descriptions", [])
    }

    items = []
    for asset in data.get("assets", []):
        desc = desc_map.get((asset["classid"], asset["instanceid"]))
        if not desc or desc.get("market_hash_name") != SKIN_NAME:
            continue
        items.append({
            "asset_id": asset["assetid"],
            "name": desc.get("name", SKIN_NAME),
            "market_hash_name": SKIN_NAME,
            "icon_url": "https://community.akamai.steamstatic.com/economy/image/" + desc["icon_url"]
                        if desc.get("icon_url") else None,
            "tradable": desc.get("tradable", 0) == 1,
        })

    return {"items": items, "count": len(items)}


@router.get("/debug")
async def debug_inventory(user: User = Depends(get_current_user)):
    url = f"https://steamcommunity.com/inventory/{user.steam_id}/{CS2_APP_ID}/{CS2_CONTEXT_ID}"
    headers = {
        **_HEADERS,
        "Referer": f"https://steamcommunity.com/profiles/{user.steam_id}/inventory/",
    }
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        resp = await client.get(url, params={"l": "english", "count": 5000}, headers=headers)

    return {
        "status": resp.status_code,
        "body_preview": resp.text[:500],
    }
