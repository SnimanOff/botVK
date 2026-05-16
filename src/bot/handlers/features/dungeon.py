from vkbottle import Callback, Keyboard, KeyboardButtonColor
from loguru import logger
from database.service.user import UserService
from bot.handlers.move import build_move_keyboard

async def enter_dungeon(event, player):
    logger.debug("Вход в данж, пользователь: {}", player.vk_id)
    
    # Создаём данж
    dungeon, ok = await UserService.create_dungeon(player)
    if not ok:
        await snackbar(event, "Не удалось создать данж")
        return
    
    result = await UserService.enter_dungeon_room(dungeon, player)
    exits, _ = await UserService.get_available_exits(dungeon)
    keyboard = build_navigation_kb(exits)
    
    await event.ctx_api.messages.send(
        peer_id=event.object.peer_id,
        message=result["message"],
        keyboard=keyboard,
        random_id=0,
    )
    
    await delete(event)


async def dungeon_move(event, player, payload):
    dungeon, ok = await UserService.get_active_dungeon(player.vk_id)
    if not ok:
        await snackbar(event, "Нет активного данжа")
        return
    
    new_x = payload.get("x")
    new_y = payload.get("y")
    
    dungeon, moved, msg = await UserService.move_in_dungeon(dungeon, new_x, new_y)
    if not moved:
        await snackbar(event, msg)
        return
    
    result = await UserService.enter_dungeon_room(dungeon, player)
    
    room_type = result.get("type")
    
    if room_type == "exit":
        await UserService.complete_dungeon(dungeon, player, success=True)
        keyboard = await build_move_keyboard(player.location_id)
        await event.ctx_api.messages.send(
            peer_id=event.object.peer_id,
            message=f"{result['message']}\n\nПодземелье пройдено!",
            keyboard=keyboard,
            random_id=0,
        )
        await delete(event)
        return
    
    if room_type in ("start", "shrine", "treasure"):
        exits, _ = await UserService.get_available_exits(dungeon)
        keyboard = build_navigation_kb(exits)
    elif room_type in ("combat", "boss"):
        keyboard = build_combat_kb(result.get("battle_id"))
    else:
        keyboard = None
    
    await event.ctx_api.messages.send(
        peer_id=event.object.peer_id,
        message=result["message"],
        keyboard=keyboard,
        random_id=0,
    )
    
    await delete(event)


async def combat_action(event, player, payload):
    battle_id = payload.get("battle_id")
    action = payload.get("action")  # "attack", "defend", "potion"
    
    logger.debug("Боевое действие: {}, пользователь: {}", action, player.vk_id)
    
    # Заглушка — пока просто отвечаем
    if action == "attack":
        await snackbar(event, "Удар нанесён")
    elif action == "defend":
        await snackbar(event, "Защитная стойка")
    elif action == "potion":
        await snackbar(event, "Зелье выпито")
    
    # TODO: полная логика боя позже

def build_navigation_kb(exits: list[dict]) -> str:
    keyboard = Keyboard(inline=True)
    
    for exit_data in exits:
        x, y = exit_data["x"], exit_data["y"]
        cleared = "(пройдено)" if exit_data["cleared"] else ""
        
        label = {
            "start": "[Вход]",
            "combat": "[Бой]",
            "treasure": "[Сокр]",
            "shrine": "[Шрн]",
            "boss": "[БОСС]",
            "exit": "[Выход]",
        }.get(exit_data["type"], "[?]")
        
        keyboard.add(
            Callback(
                f"> {label} {exit_data['name']} {cleared}",
                payload={"cmd": "dungeon_move", "x": x, "y": y}
            ),
            color=KeyboardButtonColor.PRIMARY
        )
        keyboard.row()
    
    return keyboard.get_json()


def build_combat_kb(battle_id: int) -> str:
    keyboard = Keyboard(inline=True)
    
    keyboard.add(
        Callback(
            "Атаковать",
            payload={"cmd": "combat_action", "battle_id": battle_id, "action": "attack"}
        ),
        color=KeyboardButtonColor.POSITIVE
    )
    keyboard.add(
        Callback(
            "Блок",
            payload={"cmd": "combat_action", "battle_id": battle_id, "action": "defend"}
        ),
        color=KeyboardButtonColor.SECONDARY
    )
    keyboard.row()
    
    keyboard.add(
        Callback(
            "Зелье",
            payload={"cmd": "combat_action", "battle_id": battle_id, "action": "potion"}
        ),
        color=KeyboardButtonColor.PRIMARY
    )
    
    return keyboard.get_json()


async def build_dungeon_room_kb(dungeon, room_data):
    room_type = room_data.get("type")
    
    if room_type in ("start", "shrine", "treasure"):
        exits, _ = await UserService.get_available_exits(dungeon)
        return build_navigation_kb(exits)
    elif room_type in ("combat", "boss"):
        # ищем активный бой
        # TODO: получить battle_id из состояния
        return build_combat_kb(0)
    
    return Keyboard(inline=True).get_json()



async def snackbar(event, text: str):
    try:
        await event.ctx_api.messages.send_message_event_answer(
            event_id=event.object.event_id,
            user_id=event.object.user_id,
            peer_id=event.object.peer_id,
            event_data={"type": "show_snackbar", "text": text}
        )
    except Exception as error:
        logger.warning("Snackbar: {}", error)


async def delete(event):
    try:
        await event.ctx_api.messages.delete(
            peer_id=event.object.peer_id,
            conversation_message_ids=[event.object.conversation_message_id],
            delete_for_all=True
        )
    except Exception as error:
        logger.warning("Delete: {}", error)