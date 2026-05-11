import asyncio

from vkbottle.bot import Bot
from loguru import logger

from settings import settings
from logger import setup_logger
from database.run import init_db, close_db
from bot.handlers import labeler


bot = Bot(token=settings.VK_TOKEN)
bot.labeler.load(labeler)


async def main() -> None:
    setup_logger()

    try:
        logger.info("Запуск приложения...")
        await init_db()

        logger.info("Бот запущен")
        await bot.run_polling()

    except KeyboardInterrupt:
        logger.warning("Бот остановлен вручную")

    except Exception as error:
        logger.exception("Ошибка при запуске: {}", error)

    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())