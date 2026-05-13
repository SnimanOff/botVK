from vkbottle.bot import BotLabeler, Message
from loguru import logger
from bot.handlers.move import build_move_keyboard
from database.service.user import UserService

labeler = BotLabeler()

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
    logger.debug("Успешный вывод /start, для пользователя: {}", player.vk_id)