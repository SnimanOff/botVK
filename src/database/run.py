from loguru import logger
from sqlalchemy import text

from database.core import engine, Base
from database.models import *

from database.init.locations import add_locations
from database.init.items import add_items
from database.init.monsters import add_monsters


async def init_db(load_data: bool = False) -> None:
    logger.info("Инициализация базы данных...")

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.success("Подключение к БД успешно")

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        logger.success("Таблицы БД созданы или уже существуют")

        if load_data:
            logger.info("Загрузка стартовых данных...")
            await add_locations()
            await add_items()
            await add_monsters()
            logger.success("Стартовые данные загружены")

    except Exception as error:
        logger.exception("Ошибка при инициализации БД: {}", error)
        raise


async def close_db() -> None:
    logger.info("Закрытие соединений с базой данных...")

    try:
        await engine.dispose()
        logger.success("Соединения с БД закрыты")

    except Exception as error:
        logger.exception("Ошибка при закрытии БД: {}", error)
        raise