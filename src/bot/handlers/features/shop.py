from loguru import logger
from vkbottle import Callback, Keyboard, KeyboardButtonColor
from database.service.user import UserService
from database.service.shop import ShopService
from bot.handlers.move import build_move_keyboard

def shop_main_kb() -> str:
    keyboard = Keyboard(inline=True)
    categories = [
        ("Оружие", "weapon"),
        ("Броня", "armor"),
        ("Кольца", "ring"),
        ("Расходники", "else"),
    ]
    
    for label, category in categories:
        keyboard.add(
            Callback(label, payload={"cmd": "shop_category", "category": category}),
            color=KeyboardButtonColor.PRIMARY
        )
        keyboard.row()
    
    keyboard.add(
        Callback("🔙 Назад", payload={"cmd": "feature", "id": "back_to_location"}),
        color=KeyboardButtonColor.SECONDARY
    )
    
    return keyboard.get_json()


def shop_category_kb(items: list[dict], player_balance: int) -> str:
    keyboard = Keyboard(inline=True)
    
    for item in items:
        label = f"{item['name']} — {item['price']}💰"
        keyboard.add(
            Callback(
                label,
                payload={"cmd": "shop_buy", "item_code": item["code"], "category": item["type"]}
            ),
            color=KeyboardButtonColor.POSITIVE
        )
        keyboard.row()
    
    keyboard.add(
        Callback("🔙 К категориям", payload={"cmd": "feature", "id": "shop"}),
        color=KeyboardButtonColor.SECONDARY
    )
    
    return keyboard.get_json()


def shop_confirm_kb(item_code: str, category: str) -> str:
    keyboard = Keyboard(inline=True)
    
    keyboard.add(
        Callback(
            "✅ Купить",
            payload={"cmd": "shop_confirm", "item_code": item_code, "category": category}
        ),
        color=KeyboardButtonColor.POSITIVE
    )
    keyboard.add(
        Callback(
            "❌ Отмена",
            payload={"cmd": "shop_category", "category": category}
        ),
        color=KeyboardButtonColor.NEGATIVE
    )
    
    return keyboard.get_json()

async def shop_open(event, player):
    keyboard = shop_main_kb()
    
    await event.ctx_api.messages.send(
        peer_id=event.object.peer_id,
        message=(
            f"🏪 Добро пожаловать в магазин!\n"
            f"💰 Ваш баланс: {player.balance} монет\n\n"
            f"Выберите категорию:"
        ),
        keyboard=keyboard,
        random_id=0
    )
    logger.debug("Вызвано открытие магазина пользователем: {}", event.object.peer_id)
    await snackbar(event, "🏪 Магазин открыт")
    await safe_delete(event)
    


async def shop_category(event, player, payload):
    category = payload.get("category")
    items, ok = await ShopService.GA_items(player, category)
    category_name = ShopService.get_category_name(category)
    
    if not ok or not items:
        keyboard = shop_main_kb()
        message = f"🏪 {category_name}\n\n😕 В этой категории нет доступных товаров"
        logger.debug("Пользователь: {} не имеет доступных товаров", event.object.peer_id)
    else:
        keyboard = shop_category_kb(items, player.balance)
        message = (
            f"🏪 {category_name}\n"
            f"💰 Баланс: {player.balance} монет\n\n"
            f"Доступно {len(items)} товаров:"
        )
        
    await event.ctx_api.messages.send(
        peer_id=event.object.peer_id,
        message=message,
        keyboard=keyboard,
        random_id=0
    )
    
    logger.debug("Пользователь: {} успешно открыл категорию: {}", event.object.peer_id, category_name)
    
    await safe_delete(event)
    await snackbar(event, f"📂 {category_name}")


async def shop_buy(event, player, payload):
    item_code = payload.get("item_code")
    category = payload.get("category")
    
    item, ok = await UserService.get_item(item_code)
    if not ok:
        await snackbar(event, "❌ Предмет не найден")
        logger.debug("Пользователь: {} попытался купить несуществующий предмет: {}", event.object.peer_id, item_code)
        return
    
    keyboard = shop_confirm_kb(item_code, category)
    
    await event.ctx_api.messages.send(
        peer_id=event.object.peer_id,
        message=(
            f"🛒 Покупка: {item.name}\n"
            f"💰 Цена: {item.price} монет\n"
            f"📊 Баланс после: {player.balance - item.price} монет\n\n"
            f"Подтвердите покупку:"
        ),
        keyboard=keyboard,
        random_id=0
    )
    
    logger.debug("Пользователь: {} начал процесс покупки предмета: {}", event.object.peer_id, item_code)
    
    await safe_delete(event)


async def shop_confirm(event, player, payload):
    item_code = payload.get("item_code")
    
    updated_player, msg, ok = await ShopService.buy_item(player, item_code)
    
    if ok:
        item, okk = await UserService.get_item(item_code)
        if okk:
            logger.debug("Пользователь: {} приобрёл предмет: {}", event.object.peer_id, item_code)
            await snackbar(event, msg)   
            await shop_category(event, updated_player, {"category": item.type})
        else:
            await snackbar(event, "Неизвестная ошибка")
            logger.error("Пользователь: {} не смог купить предмет {} из-за ошибки в get_item", event.object.peer_id, item_code)
    else:
        await snackbar(event, msg)
        logger.debug("Пользователь: {} не смог приобрести предмет из-за: {}", event.object.peer_id, msg)


async def back_to_location(event, player):
    keyboard = await build_move_keyboard(player.location_id)
    loc, ok = await UserService.get_location(player.location_id)
    loc_name = loc.name if ok else f"Локация {player.location_id}"
    
    await event.ctx_api.messages.send(
        peer_id=event.object.peer_id,
        message=(
            f"📍 {loc_name}\n"
            f"❤️ HP: {player.health}/{player.max_health}\n"
            f"💰 {player.balance} монет"
        ),
        keyboard=keyboard,
        random_id=0
    )
    
    logger.debug("Пользователь: {} вернулся к локациям", event.object.peer_id)
    
    await safe_delete(event)
    await snackbar(event, "🔙 Возврат к локации")


async def safe_delete(event):
    try:
        await event.ctx_api.messages.delete(
            peer_id=event.object.peer_id,
            conversation_message_ids=[event.object.conversation_message_id],
            delete_for_all=True
        )
        logger.debug("Успешное удаление сообщения: {}", event.object.conversation_message_id)
    except Exception as error:
        logger.warning("Не удалось удалить сообщение: {} из-за ошибки: {}", event.object.conversation_message_id, error)


async def snackbar(event, text: str):
    try:
        await event.ctx_api.messages.send_message_event_answer(
            event_id=event.object.event_id,
            user_id=event.object.user_id,
            peer_id=event.object.peer_id,
            event_data={"type": "show_snackbar", "text": text}
        )
        logger.debug("Snackbar успешно показан пользователю {}", event.object.user_id, text)
    except Exception as error:
        logger.warning("Snackbar не показан пользователю: {}, из-за ошибки: {}", event.object.user_id, error)