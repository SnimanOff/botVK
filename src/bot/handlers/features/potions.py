import random
from loguru import logger
from vkbottle import Callback, Keyboard, KeyboardButtonColor
from database.service.user import UserService
from database.service.dungeon import BattleService, DungeonService
from bot.handlers.features.dungeon import (
    snackbar,
    edit_message,
    format_battle_state,
    get_combat_kb,
    format_room,
    get_room_kb,
)


async def potions_open(event, player):
    battle, has_battle = await BattleService.get_active_battle(player.vk_id)
    if not has_battle:
        await snackbar(event, "Зелья доступны только в бою.")
        return

    bag = player.inventory.get("bag", [])
    potions = {}
    for code in bag:
        item, ok = await UserService.get_item(code)
        if not ok or not item:
            continue
        stats = item.stats or {}
        if "heal" in stats or stats.get("stat") or stats.get("effect"):
            potions.setdefault(code, {"name": item.name, "count": 0})
            potions[code]["count"] += 1

    kb = Keyboard(inline=True)
    if not potions:
        kb.add(Callback("Назад", payload={"cmd": "back_to_combat"}))
        await event.ctx_api.messages.send(
            peer_id=event.object.peer_id,
            message="У вас нет зелий.",
            keyboard=kb.get_json(),
            random_id=0,
        )
        await _confirm_callback(event)
        return

    for code, info in potions.items():
        kb.add(
            Callback(
                f"{info['name']} x{info['count']}",
                payload={"cmd": "use_potion", "code": code},
            ),
            color=KeyboardButtonColor.PRIMARY,
        )
        kb.row()

    kb.add(
        Callback("Назад", payload={"cmd": "back_to_combat"}),
        color=KeyboardButtonColor.SECONDARY,
    )

    await event.ctx_api.messages.send(
        peer_id=event.object.peer_id,
        message="Выберите зелье для использования:",
        keyboard=kb.get_json(),
        random_id=0,
    )
    await _confirm_callback(event)

    try:
        await event.ctx_api.messages.delete(
            peer_id=event.object.peer_id,
            conversation_message_ids=[event.object.conversation_message_id],
            delete_for_all=True,
        )
    except Exception:
        pass


async def use_potion(event, player, payload):
    code = payload.get("code")
    if not code:
        await snackbar(event, "Не указан код зелья.")
        return

    bag = player.inventory.get("bag", [])
    try:
        idx = bag.index(code)
    except ValueError:
        await snackbar(event, "Зелье не найдено в сумке.")
        return

    battle, has_battle = await BattleService.get_active_battle(player.vk_id)
    if not has_battle or not battle:
        player, ok = await UserService.use_item(player, idx)
        if ok:
            await snackbar(event, "Зелье использовано.")
        else:
            await snackbar(event, "Не удалось использовать зелье.")
        return

    battle, success, msg = await BattleService.player_action(
        battle, player, "potion", potion_index=idx
    )
    if not success:
        await snackbar(event, msg)
        return

    try:
        await event.ctx_api.messages.delete(
            peer_id=event.object.peer_id,
            conversation_message_ids=[event.object.conversation_message_id],
            delete_for_all=True,
        )
    except Exception:
        pass

    if battle.state.get("status") == "won":
        gold = random.randint(15, 40)
        await UserService.add_balance(player, gold)
        msg += f"\n\n+{gold} монет"

        dung = await DungeonService.get_dungeon(player.vk_id)
        if dung:
            await DungeonService.mark_room_cleared(dung)

        if dung and await DungeonService.is_completed(dung):
            msg += "\n\nДанж пройден"
            await DungeonService.complete_dungeon(dung, success=True)
            await BattleService.end_battle(battle)
            await edit_message(event, msg)
            return

        room = await DungeonService.get_current_room(dung)
        msg += f"\n\n{format_room(room)}"
        kb = get_room_kb(dung, room, player)
        await BattleService.end_battle(battle)
        await edit_message(event, msg, kb)
        return

    if battle.state.get("status") == "lost":
        dung = await DungeonService.get_dungeon(player.vk_id)
        if dung:
            await DungeonService.complete_dungeon(dung, success=False)
        await BattleService.end_battle(battle)
        msg += "\n\nПоражение"
        await edit_message(event, msg)
        return

    battle, enemy_msg = await BattleService.enemy_action(battle, player)
    msg += f"\n\n{enemy_msg}"

    if battle.state.get("status") == "lost":
        dung = await DungeonService.get_dungeon(player.vk_id)
        if dung:
            await DungeonService.complete_dungeon(dung, success=False)
        await BattleService.end_battle(battle)
        await edit_message(event, msg)
        return

    full_msg = format_battle_state(battle, extra_msg=msg)
    kb = get_combat_kb(battle)
    await edit_message(event, full_msg, kb)


async def _confirm_callback(event):
    try:
        await event.ctx_api.messages.send_message_event_answer(
            event_id=event.object.event_id,
            user_id=event.object.user_id,
            peer_id=event.object.peer_id,
            event_data={"type": "show_snackbar", "text": ""},
        )
    except Exception:
        logger.debug("Не удалось подтвердить callback")

async def back_to_combat(event, player):
    battle, ok = await BattleService.get_active_battle(player.vk_id)
    if not ok or not battle:
        await snackbar(event, "Нет активного боя!")
        return
    
    try:
        await event.ctx_api.messages.delete(
            peer_id=event.object.peer_id,
            conversation_message_ids=[event.object.conversation_message_id],
            delete_for_all=True,
        )
    except Exception:
        pass
    
    full_msg = format_battle_state(battle)
    kb = get_combat_kb(battle)
    
    await event.ctx_api.messages.send(
        peer_id=event.object.peer_id,
        message=full_msg,
        keyboard=kb.get_json(),
        random_id=0
    )