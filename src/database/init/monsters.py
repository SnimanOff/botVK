import json
from pathlib import Path
from sqlalchemy import delete
from database.core import get_session
from database.models import Monsters
from loguru import logger


async def add_monsters(monsters_directory: str = "monsters") -> bool:
    
    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    MONSTERS_DIR = BASE_DIR / monsters_directory
    
    logger.debug("Путь к монстрам: {}", MONSTERS_DIR)
    
    if not MONSTERS_DIR.exists():
        logger.error("Папка с монстрами не найдена")
        raise FileNotFoundError(f"Папка с монстрами не найдена по директории: {MONSTERS_DIR}")
    
    files = sorted(MONSTERS_DIR.glob("*.json"))
    
    if not files: 
        logger.error("JSON файлы в папке {} не найдены", MONSTERS_DIR)
        raise FileNotFoundError(f"В папке {MONSTERS_DIR} не найдены файлы типа JSON")
    else:
        logger.debug("Найдено {} JSON файлов в директории {}", len(files), MONSTERS_DIR)
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
    
    async with get_session() as session:
        deleted = await session.execute(delete(Monsters))
        await session.commit()
        logger.debug("Удалено монстров: {}", deleted.rowcount)
        
        count_added = 0
        for data in all_data:
            monster = Monsters(
                code=data.get("code"),
                name=data.get("name", data.get("code")),
                description=data.get("description", ""),
                rarity=data.get("rarity", "common"),
            )
            
            session.add(monster)
            count_added += 1
            logger.debug("Добавлен монстр: {}", monster.code)
        
        await session.commit()
        logger.info("Загрузка монстров завершена. Всего загружено: {}", count_added)
        
        return True
