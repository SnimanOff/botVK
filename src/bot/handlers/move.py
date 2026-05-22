from loguru import logger
from vkbottle import Callback, Keyboard, KeyboardButtonColor
from database.service.user import UserService

async def build_move_keyboard(location_id: int):
    paths, ok = await UserService.get_paths(location_id)
    keyboard = Keyboard(inline=True)
    
    if ok:
        for loc in paths:
            keyboard.add(
                Callback(
                    f"{loc.name}",
                    payload={"cmd": "move", "to": loc.id_location}
                ),
                color=KeyboardButtonColor.PRIMARY
            )
            keyboard.row()
    
    location, ok = await UserService.get_location(location_id)
    if ok and location and location.features:
        for feature_id, label in location.features.items():
            keyboard.add(
                Callback(
                    label,
                    payload={"cmd": "feature", "id": feature_id}
                ),
                color=KeyboardButtonColor.SECONDARY
            )
            keyboard.row()
    
    return keyboard.get_json()

async def handle_move(event, player, payload):
    to_id = payload.get("to")
    user_id = event.object.user_id
    
    player, ok = await UserService.player_move(player, to_id)
    
    if ok:
        new_keyboard = await build_move_keyboard(to_id)
        
        try:
            await event.ctx_api.messages.delete(
                peer_id=event.object.peer_id,
                conversation_message_ids=[event.object.conversation_message_id],
                delete_for_all=True
            )
        except Exception as e:
            logger.warning("Не удалось удалить сообщение: {}", e)
        
        await event.ctx_api.messages.send(
            peer_id=event.object.peer_id,
            message=(
                f"Вы в локации {to_id}\n"
                f"Здоровье {player.health}/{player.max_health}\n"
                f"Баланс {player.balance} монет\n\n"
                f"Куда дальше?"
            ),
            keyboard=new_keyboard,
            random_id=0
        )
        
        try:
            await event.ctx_api.messages.send_message_event_answer(
                event_id=event.object.event_id,
                user_id=user_id,
                peer_id=event.object.peer_id,
                event_data={"type": "show_snackbar", "text": f"Перемещение в {to_id}"}
            )
        except Exception as e:
            logger.warning("Не удалось показать snackbar: {}", e)
        
        logger.info(f"Игрок {user_id} переместился в {to_id}")
    else:
        try:
            await event.ctx_api.messages.send_message_event_answer(
                event_id=event.object.event_id,
                user_id=user_id,
                peer_id=event.object.peer_id,
                event_data={"type": "show_snackbar", "text": "Туда не пройти"}
            )
        except Exception as e:
            logger.warning("Не удалось показать snackbar: {}", e)