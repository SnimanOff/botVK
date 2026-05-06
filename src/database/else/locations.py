import json
from pathlib import Path
from sqlalchemy import delete
from database.core import get_session
from database.models import Locations, Edges
from loguru import logger

async def add_locations(maps_directory: str = "maps") -> bool:

    BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
    MAPS_PATH =  BASE_DIR / maps_directory
    
    logger.debug("Путь к картам: {}", MAPS_PATH)
    
    if not MAPS_PATH.exists():
        logger.error("Папка с картами не найдена")
        raise FileNotFoundError(f"Папка с картами не найдена по дирректории: {MAPS_PATH}")
    
    files = sorted(MAPS_PATH.glob("*.json"))
    
    if not files: 
        logger.error("JSON файлы в папке {} не найдены", MAPS_PATH)
        raise FileNotFoundError(f"В папке {MAPS_PATH} не найдены файлы типа JSON")
    else:
        logger.debug("Найдено {} JSON файлов в дирректории {}", len(files), MAPS_PATH)
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
            edges_deleted = await session.execute(delete(Edges))
            location_deleted = await session.execute(delete(Locations))
            await session.commit()
            
            logger.debug("Удалено рёбер {}", edges_deleted.rowcount)
            logger.debug("Удалено локаций {}", location_deleted.rowcount)
            
            ext_to_pk: dict[int, int] = {}
            
            for data in all_data:
                location_data = data["location"]
                ext_id = int(location_data["id"])
                
                location = Locations(
                    id_location = ext_id,
                    name = location_data["name"],
                    description = location_data["description"],
                )
                session.add(location)
                await session.flush()
                
                ext_to_pk[ext_id] = location.id
                logger.debug("Создано {} локаций", len(ext_to_pk))
                
                total_edges = 0

                for data in all_data:
                    location_data = data["location"]
                    edges_data = data.get("edges", [])

                    from_ext_id = int(location_data["id"])
                    from_pk = ext_to_pk[from_ext_id] 

                    for edge in edges_data:
                        to_ext_id = int(edge["to_id"])
                        to_pk = ext_to_pk.get(to_ext_id)

                        if to_pk is None:
                            logger.error(
                                "Ребро из [{}] указывает на несуществующую локацию [{}]",
                                from_ext_id, to_ext_id
                            )
                            raise ValueError(
                                f"Ребро из локации {from_ext_id} → {to_ext_id}: "
                                f"локация {to_ext_id} не найдена. Проверь JSON-файлы"
                            )

                        session.add(Edges(from_id=from_pk, to_id=to_pk))
                        total_edges += 1

                    logger.debug(
                        "Локация [{}]: {} исходящих рёбер", 
                        from_ext_id, len(edges_data)
                    )

                await session.commit()
                logger.success("Мир пересобран! Локаций: {}, Рёбер: {}", len(ext_to_pk), total_edges)

                return True