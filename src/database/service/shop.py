from database.service.user import UserService
from database.models import Players

class ShopService:
    
    CATEGORIES = {
        "weapon": "Оружие",
        "armor": "Броня",
        "ring": "Кольца",
        "else": "Расходники",
    }
    
    @staticmethod
    async def GA_items(player: Players, category: str)-> tuple[list[dict], bool]:
        player_codes = set()
        if category in ["weapon", "armor", "ring"]:
            equipped = player.inventory.get(category)
            if equipped:
                player_codes.add(equipped)
        else:
            player_codes.update(player.inventory.get("bag", []))
        
        available_codes, ok = await UserService.Go_items(player, category)
        if not ok or not available_codes:
            return [], False
        
        items = []
        for code in available_codes:
            item, found = await UserService.get_item(code)
            if found and item:
                items.append({
                    "code": item.code,
                    "name": item.name,
                    "price": item.price,
                    "type": item.type,
                    "stats": item.stats,
                })
        
        items.sort(key=lambda x: x["price"])
        return items, True

    @staticmethod
    async def buy_item(player: Players, item_code: str) -> tuple[Players, str, bool]:
        item, ok = await UserService.get_item(item_code)
        if not ok:
            return player, "❌ Предмет не найден", False
        
        if item.type in ["weapon", "armor", "ring"]:
            current = player.inventory.get(item.type)
            if current == item_code:
                return player, "❌ У вас уже экипирован этот предмет", False
            
        updated_player, ok = await UserService.buy_item(player, item_code)
        
        if not ok:
            if player.balance < item.price:
                return player, f"❌ Недостаточно монет ({player.balance}/{item.price}💰)", False
            return player, "❌ Не удалось купить предмет", False
        
        return updated_player, f"✅ Куплено: {item.name} за {item.price}💰", True
    
    @staticmethod
    def get_category_name(category: str) -> str:
        return ShopService.CATEGORIES.get(category, category)