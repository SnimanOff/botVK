import random
import math
from loguru import logger
from database.service.user import UserService
from database.models import Players, Battles, Dungeons, Monsters
from database.core import get_session
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import select


class DungeonRoom:
    
    def __init__(self, room_data: dict, player: Players, dungeon: Dungeons):
        self.room_data = room_data
        self.player = player
        self.dungeon = dungeon
        self.coords = room_data.get("coords", "?,?")
    
    async def enter(self) -> dict:
        raise NotImplementedError


class CombatRoom(DungeonRoom):
    POWER_MIN = 0.50
    POWER_MAX = 0.80
    
    async def enter(self) -> dict:
        logger.debug("Вход в combat комнату {}, игрок {}", self.coords, self.player.vk_id)
        
        player_stats = await UserService.get_total_stats(self.player)
        power_roll = random.uniform(self.POWER_MIN, self.POWER_MAX)
        
        monster = await self._get_random_monster()
        monster_name = monster.name if monster else "Неизвестный враг"
        
        enemy = {
            "name": monster_name,
            "health": max(int(player_stats["max_health"] * power_roll), 10),
            "max_health": int(player_stats["max_health"] * power_roll),
            "attack": max(int(player_stats["attack"] * power_roll), 2),
            "defense": int(player_stats["protection"] * power_roll),
            "power_percent": int(power_roll * 100),
        }
        
        logger.debug(
            "Враг: {} HP:{} ATK:{} DEF:{} ({}%)",
            enemy["name"], enemy["health"], enemy["attack"],
            enemy["defense"], enemy["power_percent"]
        )
        
        battle = await self._create_battle(enemy)
        self.room_data["cleared"] = True
        
        return {
            "type": "combat",
            "enemy": enemy,
            "battle_id": battle.id,
            "message": (
                f"Боевая комната\n"
                f"{enemy['name']}\n"
                f"HP: {enemy['health']}/{enemy['max_health']} | "
                f"ATK: {enemy['attack']} | DEF: {enemy['defense']}\n"
                f"Сила: {enemy['power_percent']}% от твоей"
            ),
        }
    
    async def _get_random_monster(self) -> Monsters | None:
        async with get_session() as session:
            result = await session.execute(select(Monsters))
            monsters = result.scalars().all()
            
            if not monsters:
                return None
            
            return random.choice(monsters)
    
    async def _create_battle(self, enemy: dict) -> Battles:
        state = {
            "enemy": enemy,
            "player_hp": self.player.health,
            "turn": 1,
            "log": [],
        }
        
        async with get_session() as session:
            battle = Battles(
                vk_id=self.player.vk_id,
                battle_type="dungeon",
                state=state,
                status=True,
            )
            session.add(battle)
            await session.commit()
            await session.refresh(battle)
            
            logger.debug("Бой создан, id={}", battle.id)
            return battle


class BossRoom(DungeonRoom):
    POWER_MIN = 0.80
    POWER_MAX = 1.10
    
    async def enter(self) -> dict:
        logger.debug("Вход в boss комнату {}, игрок {}", self.coords, self.player.vk_id)
        
        player_stats = await UserService.get_total_stats(self.player)
        power_roll = random.uniform(self.POWER_MIN, self.POWER_MAX)
        
        monster = await self._get_boss_monster()
        monster_name = monster.name if monster else "Неизвестный босс"
        
        enemy = {
            "name": monster_name,
            "health": max(int(player_stats["max_health"] * power_roll), 20),
            "max_health": int(player_stats["max_health"] * power_roll),
            "attack": max(int(player_stats["attack"] * power_roll), 5),
            "defense": int(player_stats["protection"] * power_roll),
            "power_percent": int(power_roll * 100),
        }
        
        logger.debug(
            "Босс: {} HP:{} ATK:{} DEF:{} ({}%)",
            enemy["name"], enemy["health"], enemy["attack"],
            enemy["defense"], enemy["power_percent"]
        )
        
        battle = await self._create_battle(enemy)
        self.room_data["cleared"] = True
        
        return {
            "type": "boss",
            "enemy": enemy,
            "battle_id": battle.id,
            "message": (
                f"БОСС\n"
                f"{enemy['name']}\n"
                f"HP: {enemy['health']}/{enemy['max_health']} | "
                f"ATK: {enemy['attack']} | DEF: {enemy['defense']}\n"
                f"Сила: {enemy['power_percent']}% от твоей"
            ),
        }
    
    async def _get_boss_monster(self) -> Monsters | None:
        async with get_session() as session:
            result = await session.execute(
                select(Monsters)
                .where(Monsters.rarity.in_(["rare", "epic", "legendary"]))
            )
            bosses = result.scalars().all()
            
            if bosses:
                return random.choice(bosses)
            
            result = await session.execute(select(Monsters))
            all_monsters = result.scalars().all()
            
            if all_monsters:
                return random.choice(all_monsters)
            
            return None
    
    async def _create_battle(self, enemy: dict) -> Battles:
        state = {
            "enemy": enemy,
            "player_hp": self.player.health,
            "turn": 1,
            "log": [],
        }
        
        async with get_session() as session:
            battle = Battles(
                vk_id=self.player.vk_id,
                battle_type="dungeon_boss",
                state=state,
                status=True,
            )
            session.add(battle)
            await session.commit()
            await session.refresh(battle)
            
            logger.debug("Бой с боссом создан, id={}", battle.id)
            return battle


class TreasureRoom(DungeonRoom):
    REWARD_PERCENT = 0.20
    
    async def enter(self) -> dict:
        logger.debug("Вход в treasure комнату {}, игрок {}", self.coords, self.player.vk_id)
        
        equip_value = await UserService.get_equipment_value(self.player)
        gold_reward = max(math.floor(equip_value * self.REWARD_PERCENT), 5)
        
        logger.debug("Стоимость экипировки: {}, награда: {}", equip_value, gold_reward)
        
        updated_player, ok = await UserService.add_balance(self.player, gold_reward)
        
        self.room_data["cleared"] = True
        
        return {
            "type": "treasure",
            "gold": gold_reward,
            "message": (
                f"Сокровищница\n"
                f"Найдено {gold_reward} золота\n"
                f"Баланс: {updated_player.balance}"
            ),
        }


class ShrineRoom(DungeonRoom):
    BUFF_STAT = "attack"
    BUFF_PERCENT = 15
    BUFF_DURATION = 99999
    
    async def enter(self) -> dict:
        logger.debug("Вход в shrine комнату {}, игрок {}", self.coords, self.player.vk_id)
        
        old_hp = self.player.health
        self.player.health = self.player.max_health
        
        buff = {
            "stat": self.BUFF_STAT,
            "modifier": self.BUFF_PERCENT,
            "duration": self.BUFF_DURATION,
            "source": "shrine",
        }
        
        buffs = self.dungeon.map_data.setdefault("active_buffs", [])
        buffs = [b for b in buffs if b.get("source") != "shrine"]
        buffs.append(buff)
        self.dungeon.map_data["active_buffs"] = buffs
        
        async with get_session() as session:
            flag_modified(self.dungeon, "map_data")
            await session.commit()
        
        self.room_data["cleared"] = True
        
        return {
            "type": "shrine",
            "healed": self.player.max_health - old_hp,
            "buff": buff,
            "message": (
                f"Святилище\n"
                f"Исцеление: +{self.player.max_health - old_hp} HP\n"
                f"Благословение: атака +{self.BUFF_PERCENT}% — бесконечно\n"
                f"HP: {self.player.health}/{self.player.max_health}"
            ),
        }


class StartRoom(DungeonRoom):
    async def enter(self) -> dict:
        logger.debug("Вход в start комнату {}, игрок {}", self.coords, self.player.vk_id)
        return {
            "type": "start",
            "message": "Вход в подземелье",
        }


class ExitRoom(DungeonRoom):
    async def enter(self) -> dict:
        logger.debug("Вход в exit комнату {}, игрок {}", self.coords, self.player.vk_id)
        return {
            "type": "exit",
            "message": "Выход из подземелья",
        }


class RoomFactory:
    
    ROOMS = {
        "start": StartRoom,
        "combat": CombatRoom,
        "treasure": TreasureRoom,
        "shrine": ShrineRoom,
        "boss": BossRoom,
        "exit": ExitRoom,
    }
    
    @staticmethod
    def create(room_data: dict, player: Players, dungeon: Dungeons) -> DungeonRoom:
        room_type = room_data.get("type", "combat")
        room_class = RoomFactory.ROOMS.get(room_type, CombatRoom)
        return room_class(room_data, player, dungeon)