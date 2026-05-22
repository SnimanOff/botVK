from database.models import Players, Battles
from loguru import logger

async def apply_heal(player: Players, value: int) -> tuple[Players, bool]:
    heal = min(value, player.max_health - player.health)
    player.health += heal
    logger.debug("Игрок {} восстановил {} HP", player.vk_id, heal)
    return player, True

async def apply_combat_heal(battle: Battles, value: int) -> tuple[Battles, bool, str]:
    state = battle.state
    old_hp = state["player_health"]
    state["player_health"] = min(state["player_max_health"], state["player_health"] + value)
    actual_heal = state["player_health"] - old_hp
    msg = f"восстановил {actual_heal} HP"
    return battle, True, msg

async def apply_combat_buff(battle: Battles, stat: str, modifier: int, duration: int) -> tuple[Battles, bool, str]:
    state = battle.state
    buffs = state.setdefault("player_buffs", [])
    
    buffs.append({
        "stat": stat,
        "modifier": modifier,
        "duration": duration
    })
    
    stat_names = {
        "attack": "атаку ⚔️",
        "protection": "защиту 🛡️",
        "max_health": "макс. HP ❤️"
    }
    translated_stat = stat_names.get(stat, stat)
    msg = f"увеличил {translated_stat} на {modifier} на {duration} раунда(ов)"
    return battle, True, msg

EFFECTS = {
    "heal": apply_heal,
    "combat_heal": apply_combat_heal,
    "combat_buff": apply_combat_buff,
}