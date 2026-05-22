from vkbottle import BaseMiddleware
from vkbottle.bot import Message
from database.service.user import UserService
from loguru import logger


class UserCheckMiddleware(BaseMiddleware[Message]):
    async def pre(self):
        vk_id = self.event.from_id
        player = await UserService.GoC_user(vk_id)
        self.send({"player": player})
        logger.debug(f"Пользователь {vk_id} проверен, id={player.id}")

    async def post(self):
        pass