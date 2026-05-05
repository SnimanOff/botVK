from sqlalchemy import select, insert
from database.core import get_session
from database.models import Players
from loguru import logger

class UserService:
    
    @staticmethod
    async def create_user(vk_id: int) -> Players:
        async with get_session() as session:
            result = await session.execute(
                select(Players)
                .where(Players.vk_id == vk_id)
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                logger.debug("Игрок vk_id={} уже существует, id={}", existing.vk_id, existing.id)
                return existing
            
            player = Players(
                vk_id = vk_id,
            )
            
            session.add(player)
            await session.commit()
            await session.refresh(player)
            
            logger.info("Создан игрок id={}, vk_id={}", player.id, vk_id)
            return player