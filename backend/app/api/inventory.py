from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models.user import User
from app.services.steam_inventory import fetch_user_inventory

router = APIRouter(prefix="/inventory", tags=["inventory"])

SKIN_NAME = "P250 | Sand Dune (Minimal Wear)"


@router.get("")
def get_inventory(user: User = Depends(get_current_user)):
    data = fetch_user_inventory(user.steam_id)
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
