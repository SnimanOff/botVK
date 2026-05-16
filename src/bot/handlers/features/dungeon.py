from vkbottle import Callback, Keyboard, KeyboardButtonColor
from loguru import logger
from database.service.user import UserService
from bot.handlers.move import build_move_keyboard

async def enter_dungeon(event, player):
    logger.debug("Вход в данж, пользователь: {}", player.vk_id)
    dungeon, ok = await UserService.create_dungeon(player)
    if not ok:
        await snackbar(event, "Не удалось создать данж")
        return
    
    result = await UserService.enter_dungeon_room(dungeon, player)
    keyboard = await build_dungeon_room_kb(dungeon, {"type": result.get("type")})
    
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
    
    keyboard = await build_dungeon_room_kb(dungeon, {"type": room_type})
    
    await event.ctx_api.messages.send(
        peer_id=event.object.peer_id,
        message=result["message"],
        keyboard=keyboard,
        random_id=0,
    )
    await delete(event)


async def treasure_open(event, player, payload):
    dungeon, ok = await UserService.get_active_dungeon(player.vk_id)
    if not ok:
        await snackbar(event, "Нет активного данжа")
        return
    
    key = f"{dungeon.pos_x},{dungeon.pos_y}"
    room = dungeon.map_data.get("rooms", {}).get(key, {})
    if room.get("cleared"):
        await snackbar(event, "Сундук уже открыт")
        return
    
    equipment = await UserService.get_equipment_price(player)
    networth = player.balance + equipment
    bonus = int(networth * 0.15)
    
    await UserService.add_balance(player, bonus)
    await UserService.mark_room_cleared(dungeon)
    
    result = await UserService.enter_dungeon_room(dungeon, player)
    keyboard = await build_dungeon_room_kb(dungeon, {"type": result.get("type")})
    
    await event.ctx_api.messages.send(
        peer_id=event.object.peer_id,
        message=f"{result['message']}\n\nСундук открыт! +{bonus} монет",
        keyboard=keyboard,
        random_id=0,
    )
    await delete(event)


async def shrine_use(event, player, payload):
    dungeon, ok = await UserService.get_active_dungeon(player.vk_id)
    if not ok:
        await snackbar(event, "Нет активного данжа")
        return
    
    key = f"{dungeon.pos_x},{dungeon.pos_y}"
    room = dungeon.map_data.get("rooms", {}).get(key, {})
    if room.get("cleared"):
        await snackbar(event, "Алтарь уже использован")
        return
    
    await UserService.heal_player(player)
    
    buff = {"stat": "attack", "modifier": 0.25, "duration": 9999, "source": "shrine"}
    await UserService.add_dungeon_buff(dungeon, buff)
    await UserService.mark_room_cleared(dungeon)
    
    result = await UserService.enter_dungeon_room(dungeon, player)
    keyboard = await build_dungeon_room_kb(dungeon, {"type": result.get("type")})
    
    await event.ctx_api.messages.send(
        peer_id=event.object.peer_id,
        message=f"{result['message']}\n\nАлтарь исцелил вас и даровал +25% урона",
        keyboard=keyboard,
        random_id=0,
    )
    await delete(event)


async def combat_action(event, player, payload):
    battle_id = payload.get("battle_id")
    action = payload.get("action")
    
    logger.debug("Боевое действие: {}, пользователь: {}", action, player.vk_id)
    
    if action == "attack":
        await snackbar(event, "Удар нанесён")
    elif action == "defend":
        await snackbar(event, "Защитная стойка")
    elif action == "potion":
        await snackbar(event, "Зелье выпито")
        
        # TODO: Логика боя


async def build_dungeon_room_kb(dungeon, room_data):
    room_type = room_data.get("type")
    exits, _ = await UserService.get_available_exits(dungeon)
    
    keyboard = Keyboard(inline=True)
    
    key = f"{dungeon.pos_x},{dungeon.pos_y}"
    current_room = dungeon.map_data.get("rooms", {}).get(key, {})
    is_cleared = current_room.get("cleared", False)
    
    if room_type == "treasure" and not is_cleared:
        keyboard.add(
            Callback("Открыть", payload={"cmd": "treasure_open"}),
            color=KeyboardButtonColor.POSITIVE
        )
        keyboard.row()
        return keyboard.get_json()
    
    elif room_type == "shrine" and not is_cleared:
        keyboard.add(
            Callback("Использовать", payload={"cmd": "shrine_use"}),
            color=KeyboardButtonColor.POSITIVE
        )
        keyboard.row()
        return keyboard.get_json()
    
    elif room_type in ("combat", "boss") and not is_cleared:
        battle, ok = await UserService.get_active_battle(dungeon.vk_id)
        battle_id = battle.id if ok else 0
        keyboard.add(
            Callback("Атаковать", payload={"cmd": "combat_action", "battle_id": battle_id, "action": "attack"}),
            color=KeyboardButtonColor.POSITIVE
        )
        keyboard.add(
            Callback("Блок", payload={"cmd": "combat_action", "battle_id": battle_id, "action": "defend"}),
            color=KeyboardButtonColor.SECONDARY
        )
        keyboard.row()
        keyboard.add(
            Callback("Зелье", payload={"cmd": "combat_action", "battle_id": battle_id, "action": "potion"}),
            color=KeyboardButtonColor.PRIMARY
        )
        keyboard.row()
        return keyboard.get_json()
    
    if room_type != "exit":
        for exit_data in exits:
            x, y = exit_data["x"], exit_data["y"]
            cleared = "(✓)" if exit_data["cleared"] else ""
            keyboard.add(
                Callback(
                    f"Комната {x} Этажа {y} {cleared}",
                    payload={"cmd": "dungeon_move", "x": x, "y": y}
                ),
                color=KeyboardButtonColor.PRIMARY
            )
            keyboard.row()
    
    return keyboard.get_json()


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