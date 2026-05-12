from vkbottle.bot import BotLabeler, Message

labeler = BotLabeler()

@labeler.message(text="/start")
async def start_handler(message: Message):
    await message.answer("Привет!")