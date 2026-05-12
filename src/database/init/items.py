import json
from pathlib import Path
from sqlalchemy import delete, select
from database.core import get_session
from database.models import Items
from loguru import logger


async def add_items(items_directory: str = "items") -> bool:
    
    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    ITEMS_DIR = BASE_DIR / items_directory
    
    logger.debug("Путь к предметам: {}", ITEMS_DIR)
    
    if not ITEMS_DIR.exists():
        logger.error("Папка с предметами не найдена")
        raise FileNotFoundError(f"Папка с предметами не найдена по дирректории: {ITEMS_DIR}")
    
    files = sorted(ITEMS_DIR.glob("*.json"))
    
    if not files: 
        logger.error("JSON файлы в папке {} не найдены", ITEMS_DIR)
        raise FileNotFoundError(f"В папке {ITEMS_DIR} не найдены файлы типа JSON")
    else:
        logger.debug("Найдено {} JSON файлов в дирректории {}", len(files), ITEMS_DIR)
        for file in files:
            logger.debug("  {}", file.name)
    
    all_data = []
    for file in files: 
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
            all_data.append(data)
            logger.debug("Загружен: {}", file.name)
        except json.JSONDecodeError as error:
            logger.error("Ошибка {} при парсинге файла {}", error, file.name)
            raise
    
    count_added = 0
    
    async with get_session() as session:
        for data in all_data:
            code = data.get("code")
            
            result = await session.execute(
                    select(Items)
                    .where(Items.code == code)
                )
            
            exiting = result.scalar_one_or_none()
            
            if not exiting:
                item = Items(
                code=code,
                name=data.get("name", code),
                type=data.get("type"),
                slot=data.get("slot"),
                stats=data.get("stats"),
                price=data.get("price"),
            )
            
            session.add(item)
            count_added+=1
            logger.debug("Записан отсутствующий ранее предмет: {}", item.code)
            
        await session.commit()
        logger.info("Загрузка предметов завершена. Всего загружено: {}", count_added)
        
        return True