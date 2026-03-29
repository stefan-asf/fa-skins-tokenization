"""
Скрипт для ручного тестирования Steam бота (Этап 5).
Запуск: python test_steam_bot.py

Тест 1 — логин и инвентарь бота
Тест 2 — список входящих трейдов (запускать ПОСЛЕ того как отправил трейд боту)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.config import settings
from steampy.client import SteamClient
from steampy.models import GameOptions

def test_login_and_inventory():
    print("=== Тест 1: Логин и инвентарь бота ===")
    print(f"Логин: {settings.steam_login}")

    if not settings.steam_shared_secret:
        print("WARN: STEAM_SHARED_SECRET не задан в .env")
        print("Бот требует Steam Guard — добавь shared_secret и identity_secret")
        return

    client = SteamClient(settings.steam_login)
    client.login(
        username=settings.steam_login,
        password=settings.steam_password,
        steam_guard={
            "shared_secret": settings.steam_shared_secret,
            "identity_secret": settings.steam_identity_secret,
        },
    )
    print("✓ Логин успешен")

    inventory = client.get_my_inventory(GameOptions.CS)
    print(f"✓ Предметов в инвентаре бота: {len(inventory)}")
    for asset_id, item in list(inventory.items())[:5]:
        print(f"  [{asset_id}] {item.get('market_hash_name', 'Unknown')}")

    return client


def test_incoming_offers(client):
    print("\n=== Тест 2: Входящие трейды ===")
    offers_data = client.get_trade_offers(merge=False)
    incoming = offers_data.get("response", {}).get("trade_offers_received", [])
    active = [o for o in incoming if o.get("trade_offer_state") == 2]
    print(f"Активных входящих офферов: {len(active)}")
    for offer in active:
        print(f"  offer_id={offer['tradeofferid']}  от partner={offer.get('accountid_other')}")
    return active


if __name__ == "__main__":
    client = test_login_and_inventory()
    if client:
        test_incoming_offers(client)
