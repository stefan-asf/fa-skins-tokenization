import logging
import requests
from steampy.client import SteamClient
from steampy.models import GameOptions
from app.config import settings

logger = logging.getLogger(__name__)

GAME = GameOptions.CS

# Steam trade offer states
_STATE_ACCEPTED = 3
_STATE_TERMINAL = {4, 5, 6, 7, 8, 10}  # Countered/Expired/Canceled/Declined/InvalidItems/NoLongerValid


def get_client() -> SteamClient:
    """Создаёт и возвращает авторизованный SteamClient."""
    from app.services.steam_inventory import _get_mafile_path
    client = SteamClient(settings.steam_api_key or "")
    client.login(
        username=settings.steam_login,
        password=settings.steam_password,
        steam_guard=_get_mafile_path(),
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


def request_items_from_user(
    client: SteamClient,
    trade_url: str,
    user_steam_id: str,
    asset_ids: list[str],
    message: str = "FA Skins — deposit your skins",
) -> str:
    """
    Отправляет трейд-оффер пользователю, запрашивая у него скины.
    Bot отдаёт ничего (items_from_me=[]), получает скины (items_from_them).
    Возвращает trade_offer_id.
    """
    # Fetch user inventory from Node microservice to resolve asset details
    resp = requests.get(
        "http://127.0.0.1:8081/inventory",
        params={"steamid": user_steam_id},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    # Build lookup: asset_id → {appid, contextid, assetid, amount}
    asset_map: dict[str, dict] = {}
    for asset in data.get("assets", []):
        asset_map[str(asset["assetid"])] = {
            "appid": int(asset["appid"]),
            "contextid": str(asset["contextid"]),
            "assetid": str(asset["assetid"]),
            "amount": int(asset.get("amount", 1)),
        }

    items_to_receive = []
    for aid in asset_ids:
        if aid not in asset_map:
            raise ValueError(f"Asset {aid} not found in user inventory")
        items_to_receive.append(asset_map[aid])

    offer = client.make_offer_with_url(
        items_from_me=[],
        items_from_them=items_to_receive,
        trade_offer_url=trade_url,
        message=message,
    )
    trade_offer_id = offer["tradeofferid"]
    logger.info("Deposit trade offer sent to %s: %s", user_steam_id, trade_offer_id)
    return trade_offer_id


def get_trade_offer_state(trade_offer_id: str) -> int:
    """
    Запрашивает состояние трейд-оффера через Steam Web API (без логина бота).
    Возвращает целочисленный trade_offer_state.
    Возможные состояния:
      1=Invalid, 2=Active, 3=Accepted, 4=Countered, 5=Expired,
      6=Canceled, 7=Declined, 8=InvalidItems, 9=CreatedNeedsConfirmation,
      10=CanceledBySecondFactor, 11=InEscrow
    """
    resp = requests.get(
        "https://api.steampowered.com/IEconService/GetTradeOffer/v1/",
        params={
            "key": settings.steam_api_key,
            "tradeofferid": trade_offer_id,
            "language": "en",
        },
        timeout=15,
    )
    resp.raise_for_status()
    offer = resp.json().get("response", {}).get("offer", {})
    state = int(offer.get("trade_offer_state", 1))
    logger.debug("Trade offer %s state: %d", trade_offer_id, state)
    return state
