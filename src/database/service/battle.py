
from typing import Dict
from database.models import Players, Battles
from database.core import get_session
from service.user import UserService

class BattleService:
    
    @staticmethod
    async def get_stats_player(player: Players, battle: Battles) -> Dict[str, int]:
        base_attack = player.attack
        base_protection = player.protection
        base_max_health = player.max_health

        equip_attack = 0
        equip_protection_flat = 0
        equip_protection_percent = 0

        inventory = player.inventory
        for slot in ['weapon', 'armor', 'ring']:
            item_code = inventory.get(slot)
            if item_code:
                item, success = await UserService.get_item(item_code)
                if success and item.stats:
                    stats = item.stats
                    if 'damage' in stats:
                        equip_attack += stats['damage']
                    if 'defense_percent' in stats:
                        equip_protection_percent += stats['defense_percent']

        total_attack = base_attack + equip_attack

        total_protection = base_protection + equip_protection_flat
        if equip_protection_percent:
            total_protection = int(total_protection * (100 + equip_protection_percent) / 100)

        total_max_health = base_max_health
        state = battle.state
        player_buffs = state.get("player_buffs", [])
        for buff in player_buffs:
            stat = buff.get("stat")
            mod = buff.get("modifier", 0)
            if stat == "attack":
                total_attack += mod
            elif stat == "protection":
                total_protection += mod
            elif stat == "max_health":
                total_max_health += mod

        total_attack = max(total_attack, 0)
        total_protection = max(total_protection, 0)
        total_max_health = max(total_max_health, 1)

        return {
            "attack": total_attack,
            "protection": total_protection,
            "max_health": total_max_health,
        }