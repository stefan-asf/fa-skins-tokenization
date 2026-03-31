from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/inventory", tags=["inventory"])

SKIN_NAME = "P250 | Sand Dune (Minimal Wear)"


class AssetItem(BaseModel):
    asset_id: str
    name: str
    market_hash_name: str
    icon_url: str | None
    tradable: bool


class InventoryPayload(BaseModel):
    items: List[AssetItem]


@router.post("")
def submit_inventory(
    payload: InventoryPayload,
    user: User = Depends(get_current_user),
):
    """
    Фронтенд сам запрашивает инвентарь у Steam (браузерный запрос),
    парсит его и отправляет сюда только нужные скины.
    """
    filtered = [i for i in payload.items if i.market_hash_name == SKIN_NAME]
    return {"items": [i.model_dump() for i in filtered], "count": len(filtered)}


@router.get("/steam_id")
def get_steam_id(user: User = Depends(get_current_user)):
    """Возвращает steam_id текущего пользователя для запроса инвентаря на фронте."""
    return {"steam_id": user.steam_id}
