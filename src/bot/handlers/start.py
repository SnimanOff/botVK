# bot/labelers/main.py

from vkbottle.bot import BotLabeler, Message
from loguru import logger

from database.service.user import UserService
from bot.handlers.move import build_move_keyboard
from bot.handlers.features.dungeon import build_dungeon_room_kb

labeler = BotLabeler()


@labeler.message(text="/start")
async def start_handler(message: Message):
    player = await UserService.GoC_user(message.from_id)
    dungeon, has_dungeon = await UserService.get_active_dungeon(player.vk_id)
    if has_dungeon and dungeon:
        room_data, ok = await UserService.get_dungeon_room(dungeon)
        if ok and room_data:
            keyboard = await build_dungeon_room_kb(dungeon, room_data)
            await message.answer(
                f"Подземелье\n"
                f"Комната: {room_data.get('name', '???')}\n"
                f"{room_data.get('description', '')}\n\n"
                f"HP: {player.health}/{player.max_health}\n"
                f"💰 {player.balance} монет",
                keyboard=keyboard
            )
            logger.debug("Вывод данжа для пользователя: {}", player.vk_id)
            return
        
    loc_id = player.location_id
    keyboard = await build_move_keyboard(loc_id)
    await message.answer(
        f"Добро пожаловать!\n"
        f"Локация: {loc_id}\n"
        f"HP: {player.health}/{player.max_health}\n"
        f"💰 {player.balance} монет",
        keyboard=keyboard
    )
    logger.debug("Успешный вывод /start, для пользователя: {}", player.vk_id)