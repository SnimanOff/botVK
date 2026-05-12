from vkbottle import Callback, Keyboard, KeyboardButtonColor
from vkbottle.bot import BotLabeler, Message
from vkbottle import GroupEventType, GroupTypes
from loguru import logger

from database.service.user import UserService

labeler = BotLabeler()


async def build_move_keyboard(location_id: int):
    paths, ok = await UserService.get_paths(location_id)
    keyboard = Keyboard(inline=True)
    
    if ok:
        for loc in paths:
            keyboard.add(
                Callback(
                    f"➡ {loc.name}",
                    payload={"cmd": "move", "to": loc.id_location}
                ),
                color=KeyboardButtonColor.PRIMARY
            )
            keyboard.row()
    
    return keyboard.get_json()


@labeler.message(text="/start")
async def start_handler(message: Message):
    player = await UserService.GoC_user(message.from_id)
    loc_id = player.location_id
    keyboard = await build_move_keyboard(loc_id)
    
    await message.answer(
        f"👋 Добро пожаловать!\n"
        f"📍 Локация: {loc_id}\n"
        f"❤️ HP: {player.health}/{player.max_health}\n"
        f"💰 {player.balance} монет",
        keyboard=keyboard
    )


@labeler.raw_event(GroupEventType.MESSAGE_EVENT, dataclass=GroupTypes.MessageEvent)
async def handle_callback(event: GroupTypes.MessageEvent):
    payload = event.object.payload
    cmd = payload.get("cmd")
    user_id = event.object.user_id
    
    if cmd == "move":
        to_id = payload.get("to")
        player = await UserService.GoC_user(user_id)
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
                    f"📍 Ты в локации {to_id}\n"
                    f"❤️ HP: {player.health}/{player.max_health}\n"
                    f"💰 {player.balance} монет\n\n"
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
                    event_data={"type": "show_snackbar", "text": f"✅ Перемещение в {to_id}"}
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
                    event_data={"type": "show_snackbar", "text": "❌ Туда не пройти!"}
                )
            except Exception as e:
                logger.warning("Не удалось показать snackbar: {}", e)