from loguru import logger
from vkbottle import Callback, Keyboard, KeyboardButtonColor
from database.service.user import UserService
from database.service.shop import ShopService
from bot.handlers.features.move import build_move_keyboard

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
        Callback("Назад", payload={"cmd": "feature", "id": "back_to_location"}),
        color=KeyboardButtonColor.SECONDARY
    )
    
    return keyboard.get_json()


def shop_category_kb(items: list[dict], player_balance: int) -> str:
    keyboard = Keyboard(inline=True)
    
    for item in items:
        label = f"{item['name']} - {item['price']}"
        keyboard.add(
            Callback(
                label,
                payload={"cmd": "shop_buy", "item_code": item["code"], "category": item["type"]}
            ),
            color=KeyboardButtonColor.POSITIVE
        )
        keyboard.row()
    
    keyboard.add(
        Callback("К категориям", payload={"cmd": "feature", "id": "shop"}),
        color=KeyboardButtonColor.SECONDARY
    )
    
    return keyboard.get_json()


def shop_confirm_kb(item_code: str, category: str, quantity: int = 1) -> str:
    keyboard = Keyboard(inline=True)
    
    keyboard.add(
        Callback(
            f"Купить {quantity} шт.",
            payload={"cmd": "shop_confirm", "item_code": item_code, "category": category, "quantity": quantity}
        ),
        color=KeyboardButtonColor.POSITIVE
    )
    keyboard.add(
        Callback(
            "Отмена",
            payload={"cmd": "shop_category", "category": category}
        ),
        color=KeyboardButtonColor.NEGATIVE
    )
    keyboard.row()
    
    if category in ("potion", "else"):
        for q in [1, 5, 10]:
            if q != quantity:
                keyboard.add(
                    Callback(
                        f"Выбрать x{q}",
                        payload={"cmd": "shop_buy", "item_code": item_code, "category": category, "quantity": q}
                    ),
                    color=KeyboardButtonColor.PRIMARY
                )
        keyboard.row()
    
    return keyboard.get_json()


async def shop_open(event, player):
    keyboard = shop_main_kb()
    
    await event.ctx_api.messages.send(
        peer_id=event.object.peer_id,
        message=(
            f"Добро пожаловать в магазин\n"
            f"Баланс {player.balance} монет\n\n"
            f"Выберите категорию"
        ),
        keyboard=keyboard,
        random_id=0
    )
    logger.debug("Вызвано открытие магазина пользователем: {}", event.object.peer_id)
    await snackbar(event, "Магазин открыт")
    await delete(event)
    

async def shop_category(event, player, payload):
    category = payload.get("category")
    items, ok = await ShopService.GA_items(player, category)
    category_name = ShopService.get_category_name(category)
    
    if not ok or not items:
        keyboard = shop_main_kb()
        message = f"{category_name}\n\nВ этой категории нет доступных товаров"
        logger.debug("Пользователь: {} не имеет доступных товаров", event.object.peer_id)
    else:
        keyboard = shop_category_kb(items, player.balance)
        message = (
            f"{category_name}\n"
            f"Баланс: {player.balance} монет\n\n"
            f"Доступно {len(items)} товаров:"
        )
        
    await event.ctx_api.messages.send(
        peer_id=event.object.peer_id,
        message=message,
        keyboard=keyboard,
        random_id=0
    )
    
    logger.debug("Пользователь: {} успешно открыл категорию: {}", event.object.peer_id, category_name)
    
    await delete(event)
    await snackbar(event, f"{category_name}")


async def shop_buy(event, player, payload):
    item_code = payload.get("item_code")
    category = payload.get("category")
    quantity = int(payload.get("quantity", 1))
    
    item, ok = await UserService.get_item(item_code)
    if not ok:
        await snackbar(event, "Предмет не найден")
        logger.debug("Пользователь: {} попытался купить несуществующий предмет: {}", event.object.peer_id, item_code)
        return
    
    total_price = item.price * quantity
    balance_after = player.balance - total_price
    
    keyboard = shop_confirm_kb(item_code, category, quantity)
    
    await event.ctx_api.messages.send(
        peer_id=event.object.peer_id,
        message=(
            f"Покупка {item.name} (x{quantity})\n"
            f"Цена за шт: {item.price} монет\n"
            f"Общая стоимость: {total_price} монет\n"
            f"Ваш баланс: {player.balance} монет\n"
            f"Баланс после покупки: {balance_after} монет\n\n"
            f"Подтвердите покупку"
        ),
        keyboard=keyboard,
        random_id=0
    )
    
    logger.debug("Пользователь: {} начал процесс покупки предмета: {} (x{})", event.object.peer_id, item_code, quantity)
    
    await delete(event)


async def shop_confirm(event, player, payload):
    item_code = payload.get("item_code")
    quantity = int(payload.get("quantity", 1))
    
    success_count = 0
    current_player = player
    last_msg = "Не удалось совершить покупку"

    for _ in range(quantity):
        updated_player, msg, ok = await ShopService.buy_item(current_player, item_code)
        if ok:
            current_player = updated_player
            success_count += 1
            last_msg = msg
        else:
            if success_count > 0:
                last_msg = f"Куплено {success_count} шт. На большее количество не хватает золота!"
            else:
                last_msg = msg
            break
            
    if success_count > 0:
        item, okk = await UserService.get_item(item_code)
        if okk:
            logger.debug("Пользователь: {} приобрёл предмет: {} (x{})", event.object.peer_id, item_code, success_count)
            display_msg = f"Успешно куплено {success_count} шт." if quantity > 1 else last_msg
            await snackbar(event, display_msg)   
            await shop_category(event, current_player, {"category": item.type})
        else:
            await snackbar(event, "Неизвестная ошибка")
            logger.error("Пользователь: {} не смог купить предмет {} из-за ошибки в get_item", event.object.peer_id, item_code)
    else:
        await snackbar(event, last_msg)
        logger.debug("Пользователь: {} не смог приобрести предмет из-за: {}", event.object.peer_id, last_msg)


async def back_to_location(event, player):
    keyboard = await build_move_keyboard(player.location_id)
    loc, ok = await UserService.get_location(player.location_id)
    loc_name = loc.name if ok else f"Локация {player.location_id}"
    
    await event.ctx_api.messages.send(
        peer_id=event.object.peer_id,
        message=(
            f"{loc_name}\n"
            f"Здоровье {player.health}/{player.max_health}\n"
            f"Баланс {player.balance} монет"
        ),
        keyboard=keyboard,
        random_id=0
    )
    
    logger.debug("Пользователь: {} вернулся к локациям", event.object.peer_id)
    
    await delete(event)
    await snackbar(event, "К локациям")


async def delete(event):
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