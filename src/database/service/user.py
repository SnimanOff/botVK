from sqlalchemy import select, insert
from database.core import get_session
from database.models import Players, Items
from loguru import logger

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
            
            logger.info("Создан игрок id={}, vk_id={}", player.id, vk_id)
            return player
        
        @staticmethod
        async def get_item(code: str) -> Items:
            """
            get item 

            Получение предмета из SQL бд

            Возвращает модель предмета
            """
            async with get_session() as session:
                result = await session.execute(
                    select(Items)
                    .where(Items.code == code)
                )
                
                item = result.scalar_one_or_none()
                
                if not item:
                    logger.debug("Запрашиваемый предмет не найден, код искуемого: {}", code)
                    return item
                else:
                    logger.debug("Запрашиваемый предмет найден и передан: {}", code)
                    return item