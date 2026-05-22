from vkbottle.bot import BotLabeler, Message
from loguru import logger

from database.service.user import UserService
from bot.handlers.features.move import build_move_keyboard
from database.service.dungeon import DungeonService

labeler = BotLabeler()


@labeler.message(text="/start")
async def start_handler(message: Message):
    player = await UserService.GoC_user(message.from_id)
    dungeon, has_dungeon = await UserService.get_active_dungeon(player.vk_id)
    if has_dungeon and dungeon:
        room = await DungeonService.get_current_room(dungeon)
        if room:

            from bot.handlers.features.dungeon import format_room, get_room_kb, edit_message
            
            class FakeEvent:
                def __init__(self, message):
                    self.ctx_api = message.ctx_api
                    self.object = message
            
            fake_event = FakeEvent(message)
            msg = format_room(room)
            kb = get_room_kb(dungeon, room, player)
            await edit_message(fake_event, msg, kb)
            return
    
    loc_id = player.location_id
    keyboard = await build_move_keyboard(loc_id)
    await message.answer(
        f"Добро пожаловать!\n"
        f"Локация {loc_id}\n"
        f"Здоровье {player.health}/{player.max_health}\n"
        f"Баланс {player.balance} монет",
        keyboard=keyboard
    )