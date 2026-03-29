import logging
from steampy.client import SteamClient
from steampy.models import GameOptions
from app.config import settings

logger = logging.getLogger(__name__)

GAME = GameOptions.CS


def get_client() -> SteamClient:
    """Создаёт и возвращает авторизованный SteamClient."""
    client = SteamClient(settings.steam_login)
    client.login(
        username=settings.steam_login,
        password=settings.steam_password,
        steam_guard={
            "shared_secret": settings.steam_shared_secret,
            "identity_secret": settings.steam_identity_secret,
        },
    )
    logger.info("Steam bot logged in as %s", settings.steam_login)
    return client


def get_bot_inventory(client: SteamClient) -> list[dict]:
    """Возвращает список предметов CS2 в инвентаре бота."""
    raw = client.get_my_inventory(GAME)
    items = []
    for asset_id, item in raw.items():
        items.append({
            "asset_id": asset_id,
            "name": item.get("market_hash_name", "Unknown"),
            "tradable": bool(item.get("tradable", 0)),
        })
    return items


def send_trade_offer(
    client: SteamClient,
    trade_url: str,
    asset_ids: list[str],
    message: str = "FA Skins withdrawal",
) -> str:
    """
    Отправляет трейд-оффер пользователю с указанными скинами.
    Возвращает trade_offer_id.
    """
    my_inventory = client.get_my_inventory(GAME)

    my_items = []
    for asset_id in asset_ids:
        if asset_id in my_inventory:
            my_items.append(my_inventory[asset_id])
        else:
            raise ValueError(f"Asset {asset_id} not found in bot inventory")

    offer = client.make_offer_with_url(
        items_from_me=my_items,
        items_from_them=[],
        trade_offer_url=trade_url,
        message=message,
    )
    trade_offer_id = offer["tradeofferid"]
    logger.info("Trade offer sent: %s", trade_offer_id)
    return trade_offer_id


def get_incoming_trade_offers(client: SteamClient) -> list[dict]:
    """Возвращает список входящих трейд-офферов."""
    offers = client.get_trade_offers(merge=False)
    incoming = offers.get("response", {}).get("trade_offers_received", [])
    return incoming


def accept_trade_offer(client: SteamClient, trade_offer_id: str) -> bool:
    """Принимает входящий трейд-оффер. Возвращает True при успехе."""
    try:
        client.accept_trade_offer(trade_offer_id)
        logger.info("Trade offer %s accepted", trade_offer_id)
        return True
    except Exception as e:
        logger.error("Failed to accept trade offer %s: %s", trade_offer_id, e)
        return False
