from database.models import Players
from loguru import logger

async def heal(player: Players, value: int) -> tuple[Players, bool]:
    heal = min(value, player.max_health - player.health)
    player.health += heal
    logger.debug("Игрок {} восстановил {} HP", player.vk_id, heal)
    return player, True

EFFECTS = {
    "heal": heal,
}