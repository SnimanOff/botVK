import json
from pathlib import Path
from sqlalchemy import delete
from database.core import get_session
from database.models import Locations, Edges
from loguru import logger


async def add_locations(maps_directory: str = "maps") -> bool:

    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    MAPS_PATH = BASE_DIR / maps_directory
    
    logger.debug("Путь к картам: {}", MAPS_PATH)
    
    if not MAPS_PATH.exists():
        logger.error("Папка с картами не найдена")
        raise FileNotFoundError(f"Папка с картами не найдена: {MAPS_PATH}")
    
    files = list(MAPS_PATH.glob("*.json"))
    
    if not files:
        logger.error("JSON файлы не найдены")
        raise FileNotFoundError(f"В папке {MAPS_PATH} нет JSON файлов")
    
    all_data = []
    for file in files:
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
            all_data.append(data)
            logger.debug("Загружен: {}", file.name)
        except json.JSONDecodeError as error:
            logger.error("Ошибка в {}: {}", file.name, error)
            raise
    
    async with get_session() as session:
        await session.execute(delete(Edges))
        await session.execute(delete(Locations))
        await session.commit()
        
        ext_to_pk = {}
        for data in all_data:
            loc_data = data["location"]
            ext_id = int(loc_data["id"])
            
            location = Locations(
                id_location=ext_id,
                name=loc_data["name"],
                description=loc_data["description"],
            )
            session.add(location)
            await session.flush()
            
            ext_to_pk[ext_id] = location.id_location
        
        await session.commit()
        logger.debug("Создано {} локаций", len(ext_to_pk))
        
        total_edges = 0
        for data in all_data:
            loc_data = data["location"]
            edges_data = data.get("edges", [])
            from_ext_id = int(loc_data["id"])
            from_pk = ext_to_pk[from_ext_id]
            
            for edge in edges_data:
                to_ext_id = int(edge["to_id"])
                to_pk = ext_to_pk.get(to_ext_id)
                
                if to_pk is None:
                    logger.error("Ребро из [{}] → [{}]: локация не найдена", from_ext_id, to_ext_id)
                    raise ValueError(f"Локация {to_ext_id} не найдена")
                
                session.add(Edges(from_id=from_pk, to_id=to_pk))
                total_edges += 1
            
            logger.debug("Локация [{}]: {} рёбер", from_ext_id, len(edges_data))
        
        await session.commit()
        logger.success("Мир пересобран! Локаций: {}, Рёбер: {}", len(ext_to_pk), total_edges)
        return True