import requests


def get_cs2_inventory(steam_id: str, count: int = 100) -> dict:
    """
    Получает инвентарь CS2 пользователя Steam.

    :param steam_id: 64-битный Steam ID пользователя
    :param count: количество предметов за запрос (макс. 5000)
    :return: словарь с данными инвентаря
    """
    url = f"https://steamcommunity.com/inventory/{steam_id}/730/2"
    params = {
        "l": "russian",
        "count": count,
    }

    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()

    data = response.json()

    if not data.get("success"):
        raise ValueError("Не удалось получить инвентарь. Возможно, профиль приватный.")

    return data


def parse_inventory(data: dict) -> list[dict]:
    """
    Парсит ответ API и возвращает список предметов с основными полями.
    """
    assets = data.get("assets", [])
    descriptions = data.get("descriptions", [])

    # Индексируем описания по (classid, instanceid)
    desc_map = {
        (d["classid"], d["instanceid"]): d
        for d in descriptions
    }

    items = []
    for asset in assets:
        key = (asset["classid"], asset["instanceid"])
        desc = desc_map.get(key, {})
        items.append({
            "assetid": asset["assetid"],
            "name": desc.get("market_hash_name", "Unknown"),
            "type": desc.get("type", ""),
            "tradable": bool(desc.get("tradable", 0)),
            "marketable": bool(desc.get("marketable", 0)),
            "icon_url": f"https://community.akamai.steamstatic.com/economy/image/{desc['icon_url']}"
                        if desc.get("icon_url") else None,
        })

    return items


# --- Пример использования ---
if __name__ == "__main__":
    STEAM_ID = "76561198131049642"  # ← подставь свой реальный Steam ID

    data = get_cs2_inventory(STEAM_ID, count=50)

    print(f"Всего предметов в инвентаре: {data.get('total_inventory_count', '?')}")

    items = parse_inventory(data)
    for item in items[:10]:  # первые 10
        print(f"  [{item['icon_url']}] [{item['assetid']}] {item['name']}  |  tradable={item['tradable']}")