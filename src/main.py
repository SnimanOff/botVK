import asyncio

from vkbottle.bot import Bot
from loguru import logger

from settings import settings
from logger import setup_logger
from database.run import init_db, close_db
from bot.handlers.start import labeler as start_labeler
from bot.middleware.check_user import UserCheckMiddleware

bot = Bot(token=settings.VK_TOKEN)

bot.labeler.load(start_labeler)
bot.labeler.message_view.register_middleware(UserCheckMiddleware)

def main() -> None:
    setup_logger()

    try:
        logger.info("Запуск приложения...")
        asyncio.run(init_db(load_data=True))

        logger.info("Бот запущен")
        bot.run_forever()

    except KeyboardInterrupt:
        logger.warning("Бот остановлен вручную")

    except Exception as error:
        logger.exception("Ошибка при запуске: {}", error)

    finally:
        asyncio.run(close_db())


if __name__ == "__main__":
    main()