from sqlalchemy import select, insert
from database.core import get_session
from database.models import Players, Items, Locations, Edges
from loguru import logger
from sqlalchemy.orm.attributes import flag_modified

class UserService:
    
    @staticmethod
    async def GoC_user(vk_id: int) -> Players:
        """
        get or create user 
        
        Ищет профиль пользователя в базе данных по vk_id
        При ненаходе создаёт профиль 
        
        Возвращает модель игрока
        """
        async with get_session() as session:
            result = await session.execute(
                select(Players)
                .where(Players.vk_id == vk_id)
            )
            player = result.scalar_one_or_none()
            
            if player:
                logger.debug("Игрок vk_id={} уже существует, id={}", player.vk_id, player.id)
                return player
            
            player = Players(
                vk_id = vk_id,
            )
            
            session.add(player)
            await session.commit()
            await session.refresh(player)
            
            logger.debug("Создан игрок id={}, vk_id={}", player.id, vk_id)
            return player
        
    @staticmethod
    async def get_item(code: str) -> tuple[Items | None, bool]:
        """
        get item 

        Получение предмета из SQL бд

        Возвращает модель предмета и результат операции
        """
        async with get_session() as session:
            result = await session.execute(
                select(Items)
                .where(Items.code == code)
            )
            
            item = result.scalar_one_or_none()
            
            if not item:
                logger.debug("Запрашиваемый предмет не найден, код искуемого: {}", code)
                return item, False
            else:
                logger.debug("Запрашиваемый предмет найден и передан: {}", code)
                return item, True
                

    @staticmethod
    async def give_item(player: Players, item_code: str) -> tuple[Players, bool]:
        """
        give item

        Выдача предмета по модели и коду предмета

        Возвращает или изменённое или неизменённый профиль и результат операции
        """
        async with get_session() as session:
            item = await UserService.get_item(item_code)

            if not item:
                logger.error("Предмет с кодом {} не найден", item_code)
                return player, False
            
            if item.type == "weapon":
                player.inventory["weapon"] = item.code
            elif item.type == "armor":
                player.inventory["armor"] = item.code
            elif item.type == "ring":
                player.inventory["ring"] = item.code
            else:
                player.inventory["bag"].append(item.code)

            flag_modified(player, "inventory")
            
            session.add(player)
            await session.commit()
            await session.refresh(player)
            
            logger.debug("Предмет {} успешно выдан игроку vk_id={}", item_code, player.vk_id)

            return player, True
        
    @staticmethod
    async def GP_item(player: Players, slot: str) -> tuple[str, bool]:
        """
        get player item 
        
        Возвращает предмет в передаваемом слоте и результат операции
        """
        code = player.inventory.get(slot)
        
        if not code: 
            logger.debug("Слот {}, пуст у игрока {}", slot, player.vk_id)
            return code, False
        
        logger.debug("Найден предмет {} в слоте {}", code, slot)
        return code, True
    
    @staticmethod
    async def get_paths(location_id: int) -> list[Locations| None, bool]:
        """
        get paths 
        
        Возвращает список локаций куда можно попасть и результат операции
        """
        async with get_session() as session:
            result = await session.execute(
                select(Locations)
                .join(Edges, Edges.to_id == Locations.id)
                .where(Edges.from_id == location_id)
            )
            
            locations = result.scalars().all()
            
            if not locations:
                logger.error("Путей из локации {}, нет", location_id)
                return None, False
            
            logger.debug("Из локации {} доступно {} путей", location_id, len(locations))
            return list(locations), True
        
    @staticmethod
    async def player_move(player: Players, move: int) -> tuple[Players, bool]:
        """
        player move 
        
        Метод получая модель игрока и ход, проверяет возможность хода
        После чего если ход возможен перемещает игрока
        
        Возвращает модель игрока и результат операции
        """
        location = player.location_id
        async with get_session() as session:
            paths = await UserService.get_paths(location)
            
            available_ids = [loc.id_location for loc in paths]
            
            if move not in available_ids:
                logger.debug("Путь {} недоступен из локации {}", move, location)
                return player, False
            
            player.location_id = move
            await session.commit()
            await session.refresh(player)
            
            logger.debug("Игрок {} перемещён в {}", player.vk_id, move)
            return player, True