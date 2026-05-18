from vkbottle import Callback, Keyboard, KeyboardButtonColor, GroupTypes
from loguru import logger
from database.service.user import UserService
from database.service.dungeon import BattleService
from bot.handlers.move import build_move_keyboard
from settings import settings
from database.service.dungeon import DungeonService 
import random

async def snackbar(event, text):
    try:
        await event.ctx_api.messages.sendMessageEventAnswer(
            event_id=event.object.event_id,
            user_id=event.object.user_id,
            peer_id=event.object.peer_id,
            event_data={"type": "show_snackbar", "text": text}
        )
    except Exception as e:
        logger.warning("Snackbar failed: {}", e)
        try:
            await event.ctx_api.messages.send(
                peer_id=event.object.peer_id,
                message=text,
                random_id=0
            )
        except Exception as e2:
            logger.error("Fallback message failed: {}", e2)

async def delete(event):
    """Удаляет сообщение с клавиатурой, к которому привязан callback"""
    try:
        await event.ctx_api.messages.delete(
            peer_id=event.object.peer_id,
            conversation_message_ids=[event.object.conversation_message_id],
            delete_for_all=True
        )
    except Exception:
        pass

def _format_room(room):
    cleared_mark = " ✅" if room.get("cleared") else ""
    return f"📍 {room['name']}{cleared_mark}\n{room['description']}"

def _format_battle_state(battle, extra_msg=""):
    state = battle.state
    lines = [
        f"⚔️ {state['enemy_name']}",
        f"💀 Враг: {state['enemy_health']}/{state['enemy_max_health']} HP",
        f"",
        f"❤️ Вы: {state['player_health']}/{state['player_max_health']} HP",
        f"🛡️ Стойка: {'защита' if state['player_stance'] == 'defend' else 'обычная'}",
    ]
    if state.get("last_action"):
        lines.append(f"\n📝 {state['last_action']}")
    if extra_msg:
        lines.append(f"\n{extra_msg}")
    return "\n".join(lines)

def _get_room_kb(dungeon, room, player):
    kb = Keyboard(inline=True)
    
    # ЛИНЕЙНО: только вперёд (x+1), назад нельзя
    raw_exits = room.get("exits", [])
    forward_exits = []
    
    for exit_coords in raw_exits:
        x, y = map(int, exit_coords.split(","))
        if x > dungeon.pos_x:  # только вперёд
            target = DungeonService.get_room_at_sync(dungeon, x, y)
            if target:
                forward_exits.append({
                    "x": x, "y": y,
                    "name": target.get("name"),
                    "type": target.get("type"),
                })
    
    for ex in forward_exits:
        kb.add(Callback(f"→ {ex['name']}", payload={"cmd": "dungeon_move", "x": ex["x"], "y": ex["y"]}))
        kb.row()
    
    # Действия в комнате
    if room["type"] in ("combat", "boss") and not room.get("cleared"):
        kb.add(Callback("⚔️ В бой!", payload={"cmd": "start_combat"}))
        kb.row()
    elif room["type"] == "treasure" and not room.get("cleared"):
        kb.add(Callback("🎁 Открыть", payload={"cmd": "treasure_open"}))
        kb.row()
    elif room["type"] == "shrine" and not room.get("cleared"):
        kb.add(Callback("✨ Молиться", payload={"cmd": "shrine_use"}))
        kb.row()
    elif room["type"] == "exit":
        kb.add(Callback("🚪 Выйти из данжа", payload={"cmd": "feature", "id": "exit_dungeon"}))
        kb.row()
    
    return kb

def _get_combat_kb(battle):
    kb = Keyboard(inline=True)
    
    kb.add(Callback("⚔️ Атака", payload={"cmd": "combat_action", "action": "attack"}))
    kb.row()
    kb.add(Callback("🛡️ Защита", payload={"cmd": "combat_action", "action": "defend"}))
    kb.row()
    
    # Зелья из battle state (заполняются при создании боя)
    potions = battle.state.get("player_potions", [])
    for potion in potions[:3]:
        kb.add(Callback(
            f"💊 {potion['name']}",
            payload={"cmd": "combat_action", "action": "potion", "potion_idx": potion["index"]}
        ))
        kb.row()
    
    kb.add(Callback("📊 Статистика", payload={"cmd": "combat_action", "action": "stats"}))
    
    return kb

async def enter_dungeon(event: GroupTypes.MessageEvent, player):
    logger.info("ENTER_DUNGEON: start")
    
    if player.location_id != settings.DUNGEON_LOCATION:
        logger.info("ENTER_DUNGEON: wrong location {}", player.location_id)
        await snackbar(event, "Вы не у входа в данж!")
        return
    
    if await DungeonService.has_active_dungeon(player.vk_id):
        logger.info("ENTER_DUNGEON: already has dungeon")
        await snackbar(event, "У вас уже есть активный данж!")
        return
    
    logger.info("ENTER_DUNGEON: creating dungeon...")
    dungeon = await DungeonService.create_dungeon(player)
    logger.info("ENTER_DUNGEON: dungeon created, id={}", dungeon.id if hasattr(dungeon, 'id') else 'no id')
    
    room = await DungeonService.get_current_room(dungeon)
    logger.info("ENTER_DUNGEON: room={}", room)
    
    msg = _format_room(room)
    kb = _get_room_kb(dungeon, room, player)
    logger.info("ENTER_DUNGEON: kb built")
    
    await _edit_message(event, msg, kb)
    logger.info("ENTER_DUNGEON: message sent")


async def dungeon_move(event, player, payload):
    x = payload.get("x")
    y = payload.get("y")
    
    dungeon = await DungeonService.get_dungeon(player.vk_id)
    if not dungeon:
        await snackbar(event, "Нет активного данжа")
        return
    
    dungeon, moved, reason = await DungeonService.move_to(dungeon, int(x), int(y))
    if not moved:
        await snackbar(event, reason or "Нельзя туда идти")
        return
    
    room = await DungeonService.get_current_room(dungeon)
    msg = _format_room(room)
    kb = _get_room_kb(dungeon, room, player)
    
    await _edit_message(event, msg, kb)

async def _edit_message(event, text, keyboard=None):
    logger.info("_edit_message: text_len={}, has_kb={}", len(text), keyboard is not None)
    api = event.ctx_api
    peer_id = event.object.peer_id
    
    try:
        if hasattr(event.object, 'conversation_message_id') and event.object.conversation_message_id:
            logger.info("_edit_message: deleting msg_id={}", event.object.conversation_message_id)
            await api.messages.delete(
                peer_id=peer_id,
                conversation_message_ids=[event.object.conversation_message_id],
                delete_for_all=True
            )
    except Exception as e:
        logger.warning("_edit_message: delete failed: {}", e)
    
    kwargs = {"peer_id": peer_id, "message": text, "random_id": 0}
    if keyboard:
        kwargs["keyboard"] = keyboard.get_json()
        logger.info("_edit_message: kb_json={}", keyboard.get_json()[:200])
    
    try:
        result = await api.messages.send(**kwargs)
        logger.info("_edit_message: sent, result={}", result)
    except Exception as e:
        logger.error("_edit_message: send failed: {}", e)
        raise

async def treasure_open(event, player, payload):
    dung = await DungeonService.get_dungeon(player.vk_id)
    if dung:
        await DungeonService.mark_room_cleared(dung)
    
    gold = random.randint(20, 60)
    await UserService.add_balance(player, gold)
    
    room = await DungeonService.get_current_room(dung)
    msg = f"🎁 Сундук открыт! +{gold}💰\n\n{_format_room(room)}"
    kb = _get_room_kb(dung, room, player)
    
    await _edit_message(event, msg, kb)


async def shrine_use(event, player, payload):
    dung = await DungeonService.get_dungeon(player.vk_id)
    if dung:
        await DungeonService.mark_room_cleared(dung)
    
    buff = {"stat": "attack", "value": 5, "duration": 3}
    await UserService.add_dungeon_buff(dung, buff)
    
    room = await DungeonService.get_current_room(dung)
    msg = f"✨ Алтарь дарует силу! Атака +5 на 3 боя.\n\n{_format_room(room)}"
    kb = _get_room_kb(dung, room, player)
    
    await _edit_message(event, msg, kb)


async def combat_action(event, player, payload):
    action = payload.get("action")
    potion_idx = payload.get("potion_idx")
    
    battle, ok = await BattleService.get_active_battle(player.vk_id)
    if not ok or not battle:
        await snackbar(event, "Нет активного боя")
        return
    
    # === Просмотр статов — НЕ тратит ход ===
    if action == "stats":
        stats = await UserService.get_total_stats(player)
        msg = (
            f"📊 Характеристики | "
            f"HP: {stats['health']}/{stats['max_health']} | "
            f"⚔️{stats['attack']} 🛡️{stats['protection']} | "
            f"💰{player.balance}"
        )
        await snackbar(event, msg)
        return
    
    # === Основные боевые действия ===
    battle, success, msg = await BattleService.player_action(battle, player, action, potion_idx)
    if not success:
        await snackbar(event, msg)
        return
    
    # --- Бой окончен? ---
    if battle.state.get("status") in ("won", "lost"):
        if battle.state["status"] == "won":
            gold = random.randint(15, 40)
            await UserService.add_balance(player, gold)
            msg += f"\n\n💰 +{gold} монет"
            
            dung = await DungeonService.get_dungeon(player.vk_id)
            if dung:
                await DungeonService.mark_room_cleared(dung)
            
            # Это выход из данжа?
            if dung and await DungeonService.is_completed(dung):
                msg += "\n\n🏆 Данж пройден! Поздравляем!"
                await DungeonService.complete_dungeon(dung, success=True)
                await BattleService.end_battle(battle)
                await _edit_message(event, msg)
                return
            
            # Возвращаемся к исследованию
            room = await DungeonService.get_current_room(dung)
            msg += f"\n\n{_format_room(room)}"
            kb = _get_room_kb(dung, room, player)
            await BattleService.end_battle(battle)
            await _edit_message(event, msg, kb)
            return
        
        else:  # Поражение
            dung = await DungeonService.get_dungeon(player.vk_id)
            if dung:
                await DungeonService.complete_dungeon(dung, success=False)
            await BattleService.end_battle(battle)
            msg += "\n\n💀 Поражение. Вы выброшены из данжа."
            await _edit_message(event, msg)
            return
    
    # --- Ход врага ---
    battle, enemy_msg = await BattleService.enemy_action(battle, player)
    msg += f"\n\n{enemy_msg}"
    
    if battle.state.get("status") == "lost":
        dung = await DungeonService.get_dungeon(player.vk_id)
        if dung:
            await DungeonService.complete_dungeon(dung, success=False)
        await BattleService.end_battle(battle)
        await _edit_message(event, msg)
        return
    
    # --- Новый раунд, обновляем сообщение ---
    full_msg = _format_battle_state(battle, extra_msg=msg)
    kb = _get_combat_kb(battle)
    await _edit_message(event, full_msg, kb)


async def show_battle_state(event, battle, action_message=""):
    """Отправить текущее состояние боя"""
    state = battle.state
    
    # Визуализация HP
    player_bar = create_hp_bar(state["player_health"], state["player_max_health"])
    enemy_bar = create_hp_bar(state["enemy_health"], state["enemy_max_health"])
    
    message = f"""
⚔️ БОЕВАЯ СИСТЕМА ⚔️

🛡️ ВЫ
{player_bar} {state['player_health']}/{state['player_max_health']} HP
Стойка: {'Защита 🛡️' if state['player_stance'] == 'defend' else 'Атака ⚔️'}

👹 {state['enemy_name'].upper()}
{enemy_bar} {state['enemy_health']}/{state['enemy_max_health']} HP
Стойка: {'Защита 🛡️' if state['enemy_stance'] == 'defend' else 'Атака ⚔️'}

{'=' * 40}
Раунд: {state['round']}
"""
    
    if action_message:
        message += f"\n{action_message}\n"
    
    message += f"\n{'=' * 40}"
    if state['turn'] == "player":
        message += "\n📍 ВАШ ХОД"
    elif state['turn'] == "enemy":
        message += "\n⏳ ХОД ПРОТИВНИКА..."
    else:
        message += "\n⚰️ БОЙ ЗАВЕРШЁН"
    
    keyboard = await build_combat_kb(battle) if state['turn'] == "player" else None
    
    await event.ctx_api.messages.send(
        peer_id=event.object.peer_id,
        message=message,
        keyboard=keyboard,
        random_id=0,
    )


async def start_combat(event, player, dungeon):
    battle, ok = await BattleService.create_battle(player, dungeon)
    if not ok:
        await _edit_message(event, "❌ Не удалось начать бой.")
        return
    
    msg = _format_battle_state(battle)
    kb = _get_combat_kb(battle)
    
    await _edit_message(event, msg, kb)


def create_hp_bar(current_hp: int, max_hp: int, length: int = 10) -> str:
    """Создать визуальную полоску HP"""
    filled = int((current_hp / max_hp) * length)
    empty = length - filled
    
    if current_hp > max_hp * 0.5:
        color = "🟩"  # Зелёный
    elif current_hp > max_hp * 0.25:
        color = "🟨"  # Жёлтый
    else:
        color = "🟥"  # Красный
    
    bar = color * filled + "⬜" * empty
    return f"[{bar}]"


async def build_combat_kb(battle: "Battles"):
    """Построить клавиатуру для боя"""
    keyboard = Keyboard(inline=True)
    
    battle_id = battle.id
    
    # Кнопка атаки
    keyboard.add(
        Callback(
            "⚔️ Атака",
            payload={"cmd": "combat_action", "battle_id": battle_id, "action": "attack"}
        ),
        color=KeyboardButtonColor.POSITIVE
    )
    
    # Кнопка защиты
    keyboard.add(
        Callback(
            "🛡️ Блок",
            payload={"cmd": "combat_action", "battle_id": battle_id, "action": "defend"}
        ),
        color=KeyboardButtonColor.SECONDARY
    )
    keyboard.row()
    
    # Кнопка зелья
    keyboard.add(
        Callback(
            "💊 Зелье",
            payload={"cmd": "combat_action", "battle_id": battle_id, "action": "potion"}
        ),
        color=KeyboardButtonColor.PRIMARY
    )
    
    return keyboard.get_json()


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
        # Проверяем, есть ли активный бой
        battle, has_battle = await UserService.get_active_battle(dungeon.vk_id)
        
        if has_battle:
            # Бой уже идёт - показываем боевые команды
            keyboard.add(
                Callback("⚔️ Атака", payload={"cmd": "combat_action", "battle_id": battle.id, "action": "attack"}),
                color=KeyboardButtonColor.POSITIVE
            )
            keyboard.add(
                Callback("🛡️ Блок", payload={"cmd": "combat_action", "battle_id": battle.id, "action": "defend"}),
                color=KeyboardButtonColor.SECONDARY
            )
            keyboard.row()
            keyboard.add(
                Callback("💊 Зелье", payload={"cmd": "combat_action", "battle_id": battle.id, "action": "potion"}),
                color=KeyboardButtonColor.PRIMARY
            )
        else:
            # Бой не начался - предложить начать
            keyboard.add(
                Callback("⚔️ АТАКОВАТЬ!", payload={"cmd": "start_combat"}),
                color=KeyboardButtonColor.POSITIVE
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

